#pragma once
#include "jpeg_decoder.h"
#include "logging_config.h"
#include <math.h>
#include "freertos/semphr.h"
#include "neuralnet/nn_pipeline.h"
#if __has_include("neuralnet/nn_model.h")
#include "neuralnet/nn_model.h"
#define AI_HAS_MODEL 1
#endif

// No pin/power changes. Camera ownership remains exclusively in streamVideo().
static SemaphoreHandle_t aiSlot;
static TaskHandle_t aiTask;
static uint8_t *aiJpeg, *aiBgr;
static int8_t *aiA,*aiB;
static const size_t AI_JPEG_CAPACITY=64*1024;
static size_t aiJpegSize;
static bool aiPending=false,aiReady=false;
static int64_t aiSampleTime=0;
static portMUX_TYPE aiMux=portMUX_INITIALIZER_UNLOCKED;
static nn_box aiBoxes[8];
static int aiCount=0;
static int64_t aiResultTime=0;
static float aiLatency=0,aiMaxScore=-1,aiStreamFps=-1,aiIps=-1,aiCpu0=-1,aiCpu1=-1,aiRamUsed=-1,aiPsramUsed=-1;
static const float AI_THRESHOLD=.3f;
static const char *aiStatus="waiting_for_frame";
static bool aiRunning=false;
static uint32_t aiCompleted=0,aiErrors=0,aiSkipped=0;
static httpd_handle_t aiHttp=nullptr;

// Protected by aiMux; reportMetrics snapshots/resets the entire window.
struct AiLogWindow {
  uint32_t samples,errors,offered;
  uint64_t total;
#if LOG_PROFILE && defined(AI_HAS_MODEL)
  uint64_t jpeg,pre,post,yield,layers[NN_LAYER_COUNT];
#endif
};
static AiLogWindow aiLog={};
static const char *aiLastError="none";

static void aiYield() { vTaskDelay(1); }
static void aiWorker(void *) {
#ifdef AI_HAS_MODEL
  // Scratch is static to keep the task stack small; only this worker accesses it.
  static nn_box scratch[NN_CANDIDATES], boxes[8];
  for(;;) {
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    xSemaphoreTake(aiSlot,portMAX_DELAY);
    portENTER_CRITICAL(&aiMux);aiRunning=true;portEXIT_CRITICAL(&aiMux);
    const char *stage="jpeg_info_error";
    float maxScore=-1;
    esp_jpeg_image_cfg_t cfg={};
    cfg.indata=aiJpeg;cfg.indata_size=aiJpegSize;
    cfg.outbuf=aiBgr;cfg.outbuf_size=320*240*3;
    cfg.out_format=JPEG_IMAGE_FORMAT_RGB888;cfg.out_scale=JPEG_IMAGE_SCALE_0;
    // esp_jpeg's default RGB888 output is BGR byte order, matching OpenCV.
    cfg.flags.swap_color_bytes=0;
    uint64_t layerUs[NN_LAYER_COUNT]={};
    uint64_t preUs=0,postUs=0,yieldUs=0;
    int64_t phaseStart=esp_timer_get_time();
    esp_jpeg_image_output_t info={};
    bool ok=esp_jpeg_get_image_info(&cfg,&info)==ESP_OK && info.width==320 && info.height==240;
    if(ok) {stage="jpeg_decode_error";ok=esp_jpeg_decode(&cfg,&info)==ESP_OK;}
    uint64_t jpegUs=esp_timer_get_time()-phaseStart;
    int count=0;
    if(ok) {
      phaseStart=esp_timer_get_time();
      stage="preprocess_error";ok=nn_preprocess_bgr(aiBgr,320,240,aiA)==0;
      preUs=esp_timer_get_time()-phaseStart;
    }
    if(ok) {
      lightObserve(aiA,NN_INPUT_SIZE,aiSampleTime);
      int8_t *head=aiA,*output=aiB;
      for(int i=0;i<NN_LAYER_COUNT;i++) {
        phaseStart=esp_timer_get_time();
        nn_conv(nn_layers+i,head,output);
        layerUs[i]=esp_timer_get_time()-phaseStart;
        int8_t *swap=head;head=output;output=swap;
        phaseStart=esp_timer_get_time();
        aiYield();
        yieldUs+=esp_timer_get_time()-phaseStart;
      }
      phaseStart=esp_timer_get_time();
      int peak=head[0];
      for(int i=1;i<NN_CANDIDATES;i++) if(head[i]>peak) peak=head[i];
      maxScore=1.0f/(1.0f+expf(-peak*nn_output_scales[0]));
      stage="box_decode_error";
      count=nn_decode(head,nn_output_scales,AI_THRESHOLD,.3f,scratch,boxes,8);
      ok=count>=0;
      postUs=esp_timer_get_time()-phaseStart;
    }
    int64_t now=esp_timer_get_time();
    portENTER_CRITICAL(&aiMux);
    aiCount=ok?count:0;
    aiRunning=false;aiMaxScore=maxScore;
    aiStatus=ok?(count?"detected":(maxScore<AI_THRESHOLD?"below_threshold":"no_valid_boxes")):stage;
    aiLatency=(now-aiSampleTime)/1000.0f;
    if(ok) {
      memcpy(aiBoxes,boxes,count*sizeof(nn_box));aiCompleted++;
      aiResultTime=aiSampleTime;aiLatency=(now-aiSampleTime)/1000.0f;
    } else {aiErrors++;aiResultTime=0;}
    if(ok) {
      aiLog.samples++;aiLog.total+=now-aiSampleTime;
#if LOG_PROFILE
      aiLog.jpeg+=jpegUs;aiLog.pre+=preUs;aiLog.post+=postUs;aiLog.yield+=yieldUs;
      for(int i=0;i<NN_LAYER_COUNT;i++) aiLog.layers[i]+=layerUs[i];
#endif
    } else {aiLog.errors++;aiLastError=stage;}
    portEXIT_CRITICAL(&aiMux);
    aiPending=false;
    xSemaphoreGive(aiSlot);
    vTaskDelay(1);
  }
#endif
  vTaskDelete(nullptr);
}
static void aiSubmit(const camera_fb_t *frame) {
  portENTER_CRITICAL(&aiMux);aiLog.offered++;portEXIT_CRITICAL(&aiMux);
  if(!aiReady) return;
  int64_t now=esp_timer_get_time();
  // Try each streamed frame without waiting; the single slot prevents a backlog.
  if(frame->format!=PIXFORMAT_JPEG || frame->width!=320 || frame->height!=240 || frame->len>AI_JPEG_CAPACITY || xSemaphoreTake(aiSlot,0)!=pdTRUE) {
    portENTER_CRITICAL(&aiMux);aiSkipped++;portEXIT_CRITICAL(&aiMux);return;
  }
  bool submitted=false;
  if(!aiPending) {
    memcpy(aiJpeg,frame->buf,frame->len);aiJpegSize=frame->len;
    aiSampleTime=now;aiPending=true;submitted=true;
  }
  xSemaphoreGive(aiSlot);
  if(submitted) xTaskNotifyGive(aiTask);
  else {portENTER_CRITICAL(&aiMux);aiSkipped++;portEXIT_CRITICAL(&aiMux);}
}
static esp_err_t aiDetections(httpd_req_t *req) {
  nn_box boxes[8];int count;int64_t timestamp;float latency,maxScore,streamFps,ips,ramUsed,psramUsed,cpu0,cpu1;bool running;const char *state;uint32_t completed,errors,skipped;
  portENTER_CRITICAL(&aiMux);
  count=aiCount;memcpy(boxes,aiBoxes,count*sizeof(nn_box));timestamp=aiResultTime;
  ramUsed=aiRamUsed;psramUsed=aiPsramUsed;ips=aiIps;cpu0=aiCpu0;cpu1=aiCpu1;streamFps=aiStreamFps;maxScore=aiMaxScore;running=aiRunning;state=aiStatus;
  latency=aiLatency;completed=aiCompleted;errors=aiErrors;skipped=aiSkipped;
  portEXIT_CRITICAL(&aiMux);
  int64_t age=timestamp?(esp_timer_get_time()-timestamp)/1000:-1;
  int detectedCount=count;
  if(age<0 || age>2000) count=0;
  // This server handles requests serially; keep its response off the task stack.
  static char response[1800];
  int used=snprintf(response,sizeof(response),"{\"fps\":%.2f,\"ips\":%.2f,\"ram_used_pct\":%.1f,\"psram_used_pct\":%.1f,\"cpu0_busy\":%.1f,\"cpu1_busy\":%.1f,\"enabled\":%s,\"running\":%s,\"status\":\"%s\",\"max_score\":%.4f,\"threshold\":%.2f,\"detected_count\":%d,\"age_ms\":%lld,\"latency_ms\":%.1f,\"completed\":%lu,\"errors\":%lu,\"skipped\":%lu,\"boxes\":[",streamFps,ips,ramUsed,psramUsed,cpu0,cpu1,aiReady?"true":"false",running?"true":"false",state,maxScore,AI_THRESHOLD,detectedCount,(long long)age,latency,(unsigned long)completed,(unsigned long)errors,(unsigned long)skipped);
  if(used<0 || (size_t)used>=sizeof(response)) return ESP_FAIL;
  for(int i=0;i<count;i++) {
    int n=snprintf(response+used,sizeof(response)-used,"%s[%.5f,%.5f,%.5f,%.5f,%.4f]",i?",":"",boxes[i].x1,boxes[i].y1,boxes[i].x2,boxes[i].y2,boxes[i].score);
    if(n<0 || (size_t)n>=sizeof(response)-used) return ESP_FAIL;
    used+=n;
  }
  snprintf(response+used,sizeof(response)-used,"]}");
  httpd_resp_set_hdr(req,"Access-Control-Allow-Origin","*");
  httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");
  return httpd_resp_send(req,response,HTTPD_RESP_USE_STRLEN);
}
static const char AI_PAGE[] PROGMEM=R"HTML(<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI camera</title><style>body{font-family:system-ui;background:#15191e;color:#eee;margin:24px}#view{position:relative;width:min(100%,640px)}img,canvas{width:100%;display:block}canvas{position:absolute;top:0;left:0;pointer-events:none}p{max-width:640px}.metrics{display:grid;grid-template-columns:minmax(0,1fr);gap:2px;width:min(100%,360px);margin:10px 0;font-family:ui-monospace,monospace;font-size:14px;line-height:1.5}.metric{display:grid;grid-template-columns:minmax(0,1fr) 8ch;align-items:baseline;min-width:0}.label{color:#aab5c1}.value{font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}#status{height:3em;line-height:1.5em;overflow:auto;margin:0;color:#ffcc80}#view{aspect-ratio:4/3}</style><h2>Object detection</h2><div id="view"><img id="video" alt="Camera stream"><canvas id="overlay" width="320" height="240"></canvas></div><div class="metrics"><div class="metric"><span class="label">Stream FPS · 5 s avg</span><span class="value" id="fps">—</span></div><div class="metric"><span class="label">IPS · 5 s avg</span><span class="value" id="ips">—</span></div><div class="metric"><span class="label">Max score</span><span class="value" id="score">—</span></div><div class="metric"><span class="label">CPU0 · % · 5 s avg</span><span class="value" id="cpu0">—</span></div><div class="metric"><span class="label">CPU1 · % · 5 s avg</span><span class="value" id="cpu1">—</span></div><div class="metric"><span class="label">Internal RAM · heap %</span><span class="value" id="ram">—</span></div><div class="metric"><span class="label">PSRAM · heap %</span><span class="value" id="psram">—</span></div></div><p id="status" role="status">Connecting...</p><p>Boxes are delayed detections, not frame-synchronized tracking. Close other stream viewers.</p><script>
const img=document.getElementById('video'), canvas=document.getElementById('overlay'),ctx=canvas.getContext('2d'),status=document.getElementById('status');
const fpsValue=document.getElementById('fps'),ipsValue=document.getElementById('ips'),scoreValue=document.getElementById('score');
const cpu0Value=document.getElementById('cpu0'),cpu1Value=document.getElementById('cpu1');
const ramValue=document.getElementById('ram'),psramValue=document.getElementById('psram');
let streamFailed=false;
function clearValues(){fpsValue.textContent=ipsValue.textContent=scoreValue.textContent=cpu0Value.textContent=cpu1Value.textContent=ramValue.textContent=psramValue.textContent='—';}
img.src='http://'+location.hostname+':80/stream-inf';let last=0;
const detectionUrl='http://'+location.hostname+':81/detections';
setInterval(()=>{if(Date.now()-last>2200)ctx.clearRect(0,0,320,240)},200);
async function poll() {
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),5000);
  try {
    const r=await fetch(detectionUrl,{cache:'no-store',signal:controller.signal});
    if(!r.ok) throw Error('HTTP '+r.status);
    const d=await r.json();
    if(!Array.isArray(d.boxes)) throw Error('Invalid detection response: boxes missing');
    ctx.clearRect(0,0,320,240);ctx.strokeStyle='#39ff88';ctx.lineWidth=2;
    for(const b of d.boxes) ctx.strokeRect(b[0]*320,b[1]*240,(b[2]-b[0])*320,(b[3]-b[1])*240);
    last=Date.now();
    fpsValue.textContent=Number.isFinite(d.fps)&&d.fps>=0?d.fps.toFixed(2):'—';
    cpu0Value.textContent=Number.isFinite(d.cpu0_busy)&&d.cpu0_busy>=0?d.cpu0_busy.toFixed(1):'—';
    cpu1Value.textContent=Number.isFinite(d.cpu1_busy)&&d.cpu1_busy>=0?d.cpu1_busy.toFixed(1):'—';
    ramValue.textContent=Number.isFinite(d.ram_used_pct)&&d.ram_used_pct>=0?d.ram_used_pct.toFixed(1):'—';
    psramValue.textContent=Number.isFinite(d.psram_used_pct)&&d.psram_used_pct>=0?d.psram_used_pct.toFixed(1):'—';
    const valid=d.enabled&&d.age_ms>=0&&d.age_ms<=2000;
    ipsValue.textContent=d.enabled&&Number.isFinite(d.ips)&&d.ips>=0?d.ips.toFixed(2):'—';
    scoreValue.textContent=valid&&Number.isFinite(d.max_score)&&d.max_score>=0?d.max_score.toFixed(4):'—';
    status.textContent=streamFailed?'Camera stream failed. Close other stream tabs and reload.':!d.enabled?'Detection unavailable; stream only.':d.status&&d.status.endsWith('_error')?'Detection error: '+d.status:'';
  } catch(e) {
    clearValues();
    ctx.clearRect(0,0,320,240);
    status.textContent=e.name==='AbortError'?'Detection request timed out after 5 s':'Detection error: '+e.message;
  } finally {
    clearTimeout(timer);
    setTimeout(poll,500);
  }
}
img.addEventListener('error',()=>{streamFailed=true;clearValues();status.textContent='Camera stream failed. Close other stream tabs and reload.'});
poll();</script></html>)HTML";
static esp_err_t aiPage(httpd_req_t *req) {
  httpd_resp_set_type(req,"text/html; charset=utf-8");httpd_resp_set_hdr(req,"Cache-Control","no-store");return httpd_resp_send(req,AI_PAGE,HTTPD_RESP_USE_STRLEN);
}
static void aiStart() {
#ifdef AI_HAS_MODEL
  aiJpeg=(uint8_t*)heap_caps_malloc(AI_JPEG_CAPACITY,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  aiBgr=(uint8_t*)heap_caps_malloc(320*240*3,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  aiA=(int8_t*)heap_caps_malloc(NN_BUFFER_SIZE,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  aiB=(int8_t*)heap_caps_malloc(NN_BUFFER_SIZE,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  aiSlot=xSemaphoreCreateMutex();
  if(aiJpeg && aiBgr && aiA && aiB && aiSlot) {
    aiReady=xTaskCreatePinnedToCore(aiWorker,"neuralnet",8192,nullptr,1,&aiTask,1)==pdPASS;
  }
  if(!aiReady) {
    free(aiJpeg);free(aiBgr);free(aiA);free(aiB);
    if(aiSlot) vSemaphoreDelete(aiSlot);
    Serial.println("Neural network allocation/task failed; stream remains available.");
  }
#else
  Serial.println("Neural network model missing; copy exported nn_model.h into neuralnet/.");
#endif
  httpd_config_t cfg=HTTPD_DEFAULT_CONFIG();cfg.server_port=81;cfg.ctrl_port=32769;cfg.max_uri_handlers=6;
  // JSON float formatting and HTTP calls need stack headroom.
  cfg.stack_size=8192;
  if(httpd_start(&aiHttp,&cfg)==ESP_OK) {
    httpd_uri_t view={};view.uri="/";view.method=HTTP_GET;view.handler=aiPage;
    httpd_uri_t detections={};detections.uri="/detections";detections.method=HTTP_GET;detections.handler=aiDetections;
    httpd_uri_t photo={};photo.uri="/capture";photo.method=HTTP_POST;photo.handler=photoRequest;
    httpd_uri_t photoStatus={};photoStatus.uri="/capture";photoStatus.method=HTTP_GET;photoStatus.handler=photoResponse;
    httpd_uri_t lamp={};lamp.uri="/light";lamp.method=HTTP_POST;lamp.handler=lightRequest;
    httpd_uri_t lampStatus={};lampStatus.uri="/light";lampStatus.method=HTTP_GET;lampStatus.handler=lightResponse;
    if(httpd_register_uri_handler(aiHttp,&lamp)!=ESP_OK || httpd_register_uri_handler(aiHttp,&lampStatus)!=ESP_OK || httpd_register_uri_handler(aiHttp,&photo)!=ESP_OK || httpd_register_uri_handler(aiHttp,&photoStatus)!=ESP_OK || httpd_register_uri_handler(aiHttp,&view)!=ESP_OK || httpd_register_uri_handler(aiHttp,&detections)!=ESP_OK) {
      httpd_stop(aiHttp);aiHttp=nullptr;Serial.println("Detection UI registration failed.");
    } else Serial.println("Detection view: http://ai-cam.local/inf (raw stream without inference: /)");
  } else Serial.println("Detection HTTP server failed; original stream remains on port 80.");
}
