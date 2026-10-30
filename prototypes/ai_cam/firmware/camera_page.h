#pragma once

// Request an original JPEG on the camera SD card via the control server.
static const char CAMERA_PAGE[] PROGMEM=R"HTML(<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camera capture</title>
<style>body{font-family:system-ui;background:#15191e;color:#eee;margin:24px;max-width:720px}img{display:block;width:100%;max-width:640px;background:#222;image-rendering:auto}button{font:inherit;padding:12px 22px;margin:16px 0;cursor:pointer}p{line-height:1.5}</style>
<h1>Camera capture</h1><img id="video" alt="Live camera stream">
<button id="capture" disabled>Save photo to SD</button>
<p id="status" role="status">Connecting to camera...</p>
<p>Original JPEG photos are saved in /photos on the camera SD card. Inference is off. Close other stream tabs. Wait for Saved before powering off or removing the card.</p>
<script>
const video=document.getElementById('video');
const button=document.getElementById('capture');
const message=document.getElementById('status');
let busy=false,failed=false,ready=false;
video.addEventListener('error',()=>{
  failed=true;button.disabled=true;
  message.textContent='Stream disconnected. Close other camera tabs and reload this page.';
});
video.src='/';
// MJPEG load events differ across browsers; dimensions become available with a frame.
const readiness=setInterval(()=>{
  if(!failed&&video.naturalWidth>0&&video.naturalHeight>0){
    ready=true;button.disabled=false;
    message.textContent=`Ready — ${video.naturalWidth} × ${video.naturalHeight}`;
    clearInterval(readiness);
  }
},200);
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
  if(busy||failed||!ready)return;
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
  } finally {busy=false;button.disabled=failed;}
});
</script></html>)HTML";

static esp_err_t cameraPage(httpd_req_t *request) {
  httpd_resp_set_type(request,"text/html; charset=utf-8");
  httpd_resp_set_hdr(request,"Cache-Control","no-store");
  return httpd_resp_send(request,CAMERA_PAGE,HTTPD_RESP_USE_STRLEN);
}
