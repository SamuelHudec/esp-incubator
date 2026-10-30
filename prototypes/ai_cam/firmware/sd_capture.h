#pragma once
#include <SD_MMC.h>

// AI Thinker onboard socket: SDMMC slot 1, CLK14/CMD15/D0=2, one-bit mode.
// See docs/sd-capture.md for schematic and power assumptions.
static portMUX_TYPE photoMux=portMUX_INITIALIZER_UNLOCKED;
static bool photoReady=false;
static const char *photoState="unavailable",*photoError="SD not initialized";
static uint32_t photoId=0;
static int64_t photoRequested=0;
static char photoPath[80]={};

static void photoStart() {
  photoReady=false;photoState="unavailable";
  // DAT3 must idle high during initialization, even in one-bit mode.
  // AI Thinker socket DAT3 is GPIO13; no external GPIO13 peripheral is assumed.
  // See docs/sd-capture.md. This is a weak input pull-up, not an output drive.
  pinMode(13,INPUT_PULLUP);
  // Never format an inserted card automatically.
  Serial.println("SD     mounting onboard socket (1-bit, DAT3 pull-up, no autoformat)");
  if(!SD_MMC.begin("/sdcard",true,false)) {
    photoError="SD mount failed; check SD startup log and card filesystem";
    Serial.println("ERROR  SD mount failed before /photos check; enable Core Debug Level: Error for driver details");
    return;
  }
  const uint8_t type=SD_MMC.cardType();
  if(type==CARD_NONE) {
    photoError="SD mounted but no card detected; power off and reseat card";
    Serial.println("ERROR  SD cardType=NONE");
    SD_MMC.end();return;
  }
  Serial.printf("SD     mounted type=%s capacity=%lluMiB filesystem=%lluMiB used=%lluMiB\n",
                type==CARD_MMC?"MMC":type==CARD_SD?"SD":type==CARD_SDHC?"SDHC":"unknown",
                (unsigned long long)(SD_MMC.cardSize()/(1024*1024)),
                (unsigned long long)(SD_MMC.totalBytes()/(1024*1024)),
                (unsigned long long)(SD_MMC.usedBytes()/(1024*1024)));
  if(SD_MMC.exists("/photos")) {
    File directory=SD_MMC.open("/photos",FILE_READ);
    bool isDirectory=directory && directory.isDirectory();
    if(directory)directory.close();
    if(!isDirectory) {
      photoError="SD /photos exists but is not an accessible directory";
      Serial.println("ERROR  SD /photos is not an accessible directory; existing entry preserved");
      return;
    }
  } else if(!SD_MMC.mkdir("/photos")) {
    photoError="SD mounted but could not create /photos; check free space and filesystem";
    Serial.println("ERROR  SD mkdir /photos failed (card mounted successfully)");
    return;
  }
  photoReady=true;photoState="idle";photoError="";
  Serial.println("SD     ready; photos saved in /photos");
}
static void photoExpire() { // Caller holds photoMux.
  if(strcmp(photoState,"pending")==0 && esp_timer_get_time()-photoRequested>5000000) {
    photoState="error";photoError="No camera frame within 5 seconds";
  }
}
static esp_err_t photoResponse(httpd_req_t *req) {
  char body[320];
  portENTER_CRITICAL(&photoMux);
  photoExpire();
  snprintf(body,sizeof(body),"{\"id\":%lu,\"state\":\"%s\",\"path\":\"%s\",\"error\":\"%s\"}",
           (unsigned long)photoId,photoState,photoPath,photoError);
  portEXIT_CRITICAL(&photoMux);
  httpd_resp_set_hdr(req,"Access-Control-Allow-Origin","*");
  httpd_resp_set_hdr(req,"Cache-Control","no-store");
  httpd_resp_set_type(req,"application/json");
  return httpd_resp_send(req,body,HTTPD_RESP_USE_STRLEN);
}
static bool cameraOriginAllowed(httpd_req_t *req) {
  char origin[128]={},host[96]={};
  if(httpd_req_get_hdr_value_str(req,"Origin",origin,sizeof(origin))!=ESP_OK ||
     httpd_req_get_hdr_value_str(req,"Host",host,sizeof(host))!=ESP_OK)return false;
  char *port=strchr(host,':');if(port)*port=0;
  char allowed[128],allowed80[128],allowed81[128];
  snprintf(allowed,sizeof(allowed),"http://%s",host);
  snprintf(allowed80,sizeof(allowed80),"http://%s:80",host);
  snprintf(allowed81,sizeof(allowed81),"http://%s:81",host);
  return !strcmp(origin,allowed)||!strcmp(origin,allowed80)||!strcmp(origin,allowed81);
}
static esp_err_t photoRequest(httpd_req_t *req) {
  if(!cameraOriginAllowed(req))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Use the camera capture page");
  portENTER_CRITICAL(&photoMux);
  photoExpire();
  bool busy=!strcmp(photoState,"pending")||!strcmp(photoState,"saving");
  if(photoReady&&!busy) {
    photoId++;photoRequested=esp_timer_get_time();photoPath[0]=0;
    photoError="";photoState="pending";
  }
  portEXIT_CRITICAL(&photoMux);
  if(busy) httpd_resp_set_status(req,"409 Conflict");
  return photoResponse(req);
}
// Only streamVideo owns camera frames and writes the card. No JPEG re-encoding.
static void photoSaveFrame(const camera_fb_t *frame) {
  portENTER_CRITICAL(&photoMux);
  photoExpire();
  bool requested=!strcmp(photoState,"pending");
  if(requested && !lightPhotoSettled())requested=false;
  uint32_t id=photoId;
  if(requested) photoState="saving";
  portEXIT_CRITICAL(&photoMux);
  if(!requested)return;
  char path[80],temporary[88];
  bool unique=false;
  for(int attempt=0;attempt<8;attempt++) {
    snprintf(path,sizeof(path),"/photos/cam_%08lx_%08lx_%lu.jpg",
             (unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)id);
    snprintf(temporary,sizeof(temporary),"%s.part",path);
    if(!SD_MMC.exists(path)&&!SD_MMC.exists(temporary)){unique=true;break;}
  }
  bool ok=false;
  if(unique && frame->format==PIXFORMAT_JPEG) {
    File file=SD_MMC.open(temporary,FILE_WRITE);
    if(file) {
      size_t written=file.write(frame->buf,frame->len);
      file.flush();file.close();
      File check=SD_MMC.open(temporary,FILE_READ);
      ok=check && written==frame->len && check.size()==frame->len;
      if(check)check.close();
      if(ok)ok=SD_MMC.rename(temporary,path);
    }
    if(!ok)SD_MMC.remove(temporary);
  }
  portENTER_CRITICAL(&photoMux);
  photoState=ok?"saved":"error";
  photoError=ok?"":"SD write failed; check card space and restart if card was removed";
  if(ok)strlcpy(photoPath,path,sizeof(photoPath));
  portEXIT_CRITICAL(&photoMux);
  if(ok)Serial.printf("PHOTO  saved %s bytes=%u\n",path,(unsigned)frame->len);
  else Serial.println("ERROR  SD photo write failed");
}
