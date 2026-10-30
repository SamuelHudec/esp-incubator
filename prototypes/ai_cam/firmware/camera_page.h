#pragma once

// Request an original JPEG on the camera SD card via the control server.
static const char CAMERA_PAGE[] PROGMEM=R"HTML(<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camera capture</title>
<style>body{font-family:system-ui;background:#15191e;color:#eee;margin:24px;max-width:720px}img{display:block;width:100%;max-width:640px;background:#222;image-rendering:auto}button{font:inherit;padding:12px 22px;margin:16px 0;cursor:pointer}p{line-height:1.5}</style>
<h1>Camera capture</h1><img id="video" alt="Live camera stream">
<p><label for="light">Light <output id="lightValue">0%</output></label><br><input id="light" type="range" min="0" max="0" value="0" disabled><br><span id="lightStatus">Connecting to light control...</span></p>
<button id="capture" disabled>Save photo to SD</button>
<p id="status" role="status">Connecting to camera...</p>
<p>Original JPEG photos are saved in /photos on the camera SD card. Inference is off. Close other stream tabs. Wait for Saved before powering off or removing the card.</p>
<script>
const video=document.getElementById('video');
const button=document.getElementById('capture');
const message=document.getElementById('status');
let busy=false,failed=false,ready=false,lightBusy=false,lightEditing=false;
video.addEventListener('error',()=>{
  failed=true;button.disabled=true;
  message.textContent='Stream disconnected. Close other camera tabs and reload this page.';
});
video.src='/stream-camera';
// MJPEG load events differ across browsers; dimensions become available with a frame.
const readiness=setInterval(()=>{
  if(!failed&&video.naturalWidth>0&&video.naturalHeight>0){
    ready=true;button.disabled=busy||lightBusy;
    message.textContent=`Ready — ${video.naturalWidth} × ${video.naturalHeight}`;
    clearInterval(readiness);
  }
},200);
const lightSlider=document.getElementById('light');
const lightValue=document.getElementById('lightValue');
const lightStatus=document.getElementById('lightStatus');
const lightUrl='http://'+location.hostname+':81/light';
async function lightCall(method='GET',value='') {
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
  try {
    const response=await fetch(lightUrl+(method==='POST'?'?value='+encodeURIComponent(value):''),
                               {method,cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error('HTTP '+response.status);
    return await response.json();
  } finally {clearTimeout(timer);}
}
async function refreshLight() {
  try {
    const d=await lightCall();
    if(!lightBusy&&!lightEditing) {
      lightSlider.disabled=!d.enabled||d.mode!=='manual';
      lightSlider.max=String(d.maximum);lightSlider.value=String(d.percent);
      lightValue.textContent=d.percent+'%';
      lightStatus.textContent=!d.enabled?'Light disabled in firmware or unavailable.':d.mode!=='manual'?'Waiting for camera stream...':'Manual light (maximum '+d.maximum+'%).';
    }
  } catch(error){if(!lightBusy){lightSlider.disabled=true;lightStatus.textContent='Light control: '+error.message;}}
  setTimeout(refreshLight,2000);
}
lightSlider.addEventListener('input',()=>{lightEditing=true;lightValue.textContent=lightSlider.value+'%';});
lightSlider.addEventListener('change',async()=>{
  lightEditing=false;
  if(lightBusy)return;
  lightBusy=true;lightSlider.disabled=true;button.disabled=true;
  lightStatus.textContent='Adjusting light; waiting for exposure...';
  try {
    await lightCall('POST',lightSlider.value);
    await new Promise(resolve=>setTimeout(resolve,2100));
    lightStatus.textContent='Light ready.';
  } catch(error){lightStatus.textContent='Light control: '+error.message;}
  finally {lightBusy=false;button.disabled=failed||busy||!ready;}
  refreshLightOnce();
});
async function refreshLightOnce(){
  try{const d=await lightCall();lightSlider.disabled=!d.enabled||d.mode!=='manual';}
  catch(error){lightSlider.disabled=true;}
}
refreshLight();
const captureUrl='http://'+location.hostname+':81/capture';
async function captureCall(method){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
  try {
    const response=await fetch(captureUrl,{method,cache:'no-store',signal:controller.signal});
    if(!response.ok)throw Error(response.status===409?'A photo is already being saved':'HTTP '+response.status);
    return await response.json();
  } finally {clearTimeout(timer);}
}
button.addEventListener('click',async()=>{
  if(busy||lightBusy||failed||!ready)return;
  busy=true;button.disabled=true;message.textContent='Saving to SD...';
  try {
    let result=await captureCall('POST');
    const id=result.id,started=Date.now();
    while(result.state==='pending'||result.state==='saving') {
      if(Date.now()-started>20000)throw Error('Still waiting for SD confirmation. Check the PHOTO serial log before retrying.');
      await new Promise(resolve=>setTimeout(resolve,300));
      result=await captureCall('GET');
      if(result.id!==id)throw Error('Capture changed in another viewer. Check the PHOTO serial log.');
    }
    if(result.state!=='saved')throw Error(result.error||'SD is unavailable');
    message.textContent='Saved to SD: '+result.path;
  } catch(error) {
    message.textContent='Photo not confirmed: '+error.message+' See SD / PHOTO in Serial Monitor.';
  } finally {busy=false;button.disabled=failed||lightBusy;}
});
</script></html>)HTML";

static esp_err_t cameraPage(httpd_req_t *request) {
  httpd_resp_set_type(request,"text/html; charset=utf-8");
  httpd_resp_set_hdr(request,"Cache-Control","no-store");
  return httpd_resp_send(request,CAMERA_PAGE,HTTPD_RESP_USE_STRLEN);
}
