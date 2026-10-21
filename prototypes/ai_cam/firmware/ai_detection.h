#pragma once
#include "jpeg_decoder.h"
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
static float aiLatency=0,aiMaxScore=-1;
static const float AI_THRESHOLD=.3f;
static const char *aiStatus="waiting_for_frame";
static bool aiRunning=false;
static uint32_t aiCompleted=0,aiErrors=0,aiSkipped=0;
static httpd_handle_t aiHttp=nullptr;

static void aiYield() { vTaskDelay(1); }
static void aiWorker(void *) {
#ifdef AI_HAS_MODEL
  // Scratch is static to keep the task stack small; only this worker accesses it.
  static nn_box scratch[NN_CANDIDATES], boxes[8];
  // Accumulate successful frames only; print outside the timed sections.
  static uint64_t jpegSum=0,preSum=0,postSum=0,yieldSum=0,totalSum=0;
  static uint64_t layerSum[NN_LAYER_COUNT]={};
  static uint32_t timingSamples=0;
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
    portEXIT_CRITICAL(&aiMux);
    if(ok) {
      timingSamples++;jpegSum+=jpegUs;preSum+=preUs;postSum+=postUs;
      yieldSum+=yieldUs;totalSum+=now-aiSampleTime;
      for(int i=0;i<NN_LAYER_COUNT;i++) layerSum[i]+=layerUs[i];
    }
    static int64_t lastLog=0;
    if(now-lastLog>=5000000) {
      lastLog=now;
      Serial.printf("AI status=%s max_score=%.4f threshold=%.2f boxes=%d latency_ms=%.1f completed=%lu errors=%lu\n",
                    aiStatus,maxScore,AI_THRESHOLD,ok?count:0,aiLatency,(unsigned long)aiCompleted,(unsigned long)aiErrors);
      if(timingSamples) {
        const double divisor=1000.0*timingSamples;
        uint64_t networkSum=0;
        for(int i=0;i<NN_LAYER_COUNT;i++) networkSum+=layerSum[i];
        Serial.printf("AI_TIMING samples=%lu avg_ms jpeg=%.2f preprocess=%.2f network=%.2f yield=%.2f postprocess=%.2f total=%.2f\n",
                      (unsigned long)timingSamples,jpegSum/divisor,preSum/divisor,networkSum/divisor,
                      yieldSum/divisor,postSum/divisor,totalSum/divisor);
        Serial.print("AI_LAYERS avg_ms");
        for(int i=0;i<NN_LAYER_COUNT;i++) Serial.printf(" L%d=%.2f",i,layerSum[i]/divisor);
        Serial.println();
        timingSamples=0;jpegSum=preSum=postSum=yieldSum=totalSum=0;
        memset(layerSum,0,sizeof(layerSum));
      }
    }
    aiPending=false;
    xSemaphoreGive(aiSlot);
    vTaskDelay(1);
  }
#endif
  vTaskDelete(nullptr);
}
static void aiSubmit(const camera_fb_t *frame) {
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
  nn_box boxes[8];int count;int64_t timestamp;float latency,maxScore;bool running;const char *state;uint32_t completed,errors,skipped;
  portENTER_CRITICAL(&aiMux);
  count=aiCount;memcpy(boxes,aiBoxes,count*sizeof(nn_box));timestamp=aiResultTime;
  maxScore=aiMaxScore;running=aiRunning;state=aiStatus;
  latency=aiLatency;completed=aiCompleted;errors=aiErrors;skipped=aiSkipped;
  portEXIT_CRITICAL(&aiMux);
  int64_t age=timestamp?(esp_timer_get_time()-timestamp)/1000:-1;
  int detectedCount=count;
  if(age<0 || age>2000) count=0;
  // This server handles requests serially; keep its response off the task stack.
  static char response[1800];
  int used=snprintf(response,sizeof(response),"{\"enabled\":%s,\"running\":%s,\"status\":\"%s\",\"max_score\":%.4f,\"threshold\":%.2f,\"detected_count\":%d,\"age_ms\":%lld,\"latency_ms\":%.1f,\"completed\":%lu,\"errors\":%lu,\"skipped\":%lu,\"boxes\":[",aiReady?"true":"false",running?"true":"false",state,maxScore,AI_THRESHOLD,detectedCount,(long long)age,latency,(unsigned long)completed,(unsigned long)errors,(unsigned long)skipped);
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
static const char AI_PAGE[] PROGMEM=R"HTML(<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI camera</title><style>body{font-family:system-ui;background:#15191e;color:#eee;margin:24px}#view{position:relative;width:min(100%,640px)}img,canvas{width:100%;display:block}canvas{position:absolute;top:0;left:0;pointer-events:none}p{max-width:640px}</style><h2>Object detection</h2><div id="view"><img id="video" alt="Camera stream"><canvas id="overlay" width="320" height="240"></canvas></div><p id="status">Connecting...</p><p>Boxes are delayed detections, not frame-synchronized tracking. Close other stream viewers.</p><script>
const img=document.getElementById('video'), canvas=document.getElementById('overlay'),ctx=canvas.getContext('2d'),status=document.getElementById('status');
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
    const score=typeof d.max_score==='number'&&d.max_score>=0?d.max_score.toFixed(4):'unavailable';
    status.textContent=d.enabled?`Status ${d.status||'unknown'}${d.running?" (running)":""} | max score ${score} / threshold ${d.threshold??'unknown'} | detected ${d.detected_count??d.boxes.length}, shown ${d.boxes.length} | inference ${d.latency_ms} ms | result age ${d.age_ms} ms | completed ${d.completed} | errors ${d.errors} | skipped ${d.skipped}`:'Detection unavailable; stream only.';
  } catch(e) {
    ctx.clearRect(0,0,320,240);
    status.textContent=e.name==='AbortError'?'Detection request timed out after 5 s':'Detection error: '+e.message;
  } finally {
    clearTimeout(timer);
    setTimeout(poll,500);
  }
}
img.addEventListener('error',()=>{status.textContent='Camera stream failed. Close other stream tabs and reload.'});
poll();</script></html>)HTML";
static esp_err_t aiPage(httpd_req_t *req) {
  httpd_resp_set_type(req,"text/html");httpd_resp_set_hdr(req,"Cache-Control","no-store");return httpd_resp_send(req,AI_PAGE,HTTPD_RESP_USE_STRLEN);
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
  httpd_config_t cfg=HTTPD_DEFAULT_CONFIG();cfg.server_port=81;cfg.ctrl_port=32769;cfg.max_uri_handlers=2;
  // JSON float formatting and HTTP calls need stack headroom.
  cfg.stack_size=8192;
  if(httpd_start(&aiHttp,&cfg)==ESP_OK) {
    httpd_uri_t view={};view.uri="/";view.method=HTTP_GET;view.handler=aiPage;
    httpd_uri_t detections={};detections.uri="/detections";detections.method=HTTP_GET;detections.handler=aiDetections;
    if(httpd_register_uri_handler(aiHttp,&view)!=ESP_OK || httpd_register_uri_handler(aiHttp,&detections)!=ESP_OK) {
      httpd_stop(aiHttp);aiHttp=nullptr;Serial.println("Detection UI registration failed.");
    } else Serial.println("Detection view: http://ai-cam.local/inf (raw stream without inference: /)");
  } else Serial.println("Detection HTTP server failed; original stream remains on port 80.");
}
