#pragma once
#include "driver/ledc.h"
#include "light_policy.h"

static bool cameraOriginAllowed(httpd_req_t *req);

enum class LightMode {Off,Manual,Auto};
static portMUX_TYPE lightMux=portMUX_INITIALIZER_UNLOCKED;
static bool lightAvailable=false;
static LightMode lightMode=LightMode::Off;
static uint8_t lightManualPercent=0,lightAppliedDuty=0;
static int64_t lightHeartbeat=0,lightChangedUs=0;
static LightPolicy lightPolicy;
static uint8_t lightMaximumDuty() {return (LIGHT_MAX_PERCENT*255+50)/100;}
static void lightStart() {
  // GPIO4 is the AI Thinker flash LED / SD DAT1. SD stays in one-bit mode.
  pinMode(4,OUTPUT);digitalWrite(4,LOW);
  if(!LIGHT_ENABLED){Serial.println("LIGHT  disabled in firmware");return;}
  // Explicit separate timer: camera uses timer 0/channel 0.
  ledc_timer_config_t timer={};timer.speed_mode=LEDC_LOW_SPEED_MODE;
  timer.timer_num=LEDC_TIMER_1;timer.duty_resolution=LEDC_TIMER_8_BIT;
  timer.freq_hz=5000;timer.clk_cfg=LEDC_AUTO_CLK;
  ledc_channel_config_t channel={};channel.gpio_num=4;channel.speed_mode=LEDC_LOW_SPEED_MODE;
  channel.channel=LEDC_CHANNEL_2;channel.timer_sel=LEDC_TIMER_1;channel.duty=0;
  lightAvailable=ledc_timer_config(&timer)==ESP_OK && ledc_channel_config(&channel)==ESP_OK;
  if(!lightAvailable)Serial.println("ERROR  light PWM setup failed; illumination disabled");
}
static void lightTick() {
  // Only Arduino loop writes PWM; worker and HTTP tasks only update requests.
  const int64_t now=esp_timer_get_time();
  portENTER_CRITICAL(&lightMux);
  uint8_t target=0;
  if(LIGHT_ENABLED&&lightAvailable&&now-lightHeartbeat<4000000) {
    if(lightMode==LightMode::Manual)target=(lightManualPercent*255+50)/100;
    if(lightMode==LightMode::Auto)target=lightPolicy.duty;
  }
  uint8_t current=lightAppliedDuty;
  portEXIT_CRITICAL(&lightMux);
  if(target==current)return;
  bool ok=ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,target)==ESP_OK &&
          ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2)==ESP_OK;
  if(!ok) {
    ledc_stop(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,0);
    Serial.println("ERROR  light PWM update failed; illumination disabled");
  }
  portENTER_CRITICAL(&lightMux);
  lightAvailable=lightAvailable&&ok;lightAppliedDuty=ok?target:0;lightChangedUs=now;
  lightPolicy.changedUs=now;
  portEXIT_CRITICAL(&lightMux);
}
struct LightStreamGuard {
  explicit LightStreamGuard(LightMode mode) {
    portENTER_CRITICAL(&lightMux);
    lightMode=mode;lightHeartbeat=esp_timer_get_time();lightPolicy.reset(lightHeartbeat);
    lightManualPercent=0;
    portEXIT_CRITICAL(&lightMux);
  }
  ~LightStreamGuard() {
    portENTER_CRITICAL(&lightMux);lightMode=LightMode::Off;portEXIT_CRITICAL(&lightMux);
  }
};
static void lightStreamHeartbeat() {
  portENTER_CRITICAL(&lightMux);lightHeartbeat=esp_timer_get_time();portEXIT_CRITICAL(&lightMux);
}
static void lightObserve(const int8_t *gray,int count,int64_t sampleUs) {
  // Called before nn_conv overwrites its input. Existing normalized INT8 is 0..127.
  uint32_t sum=0;for(int i=0;i<count;i++)sum+=(uint8_t)gray[i];
  const float brightness=sum*(100.0f/(127*count));
  const int64_t now=esp_timer_get_time();
  portENTER_CRITICAL(&lightMux);
  if(lightMode==LightMode::Auto&&LIGHT_ENABLED&&lightAvailable&&now-lightHeartbeat<4000000)
    lightPolicy.update(brightness,sampleUs,now,lightMaximumDuty(),LIGHT_AUTO_STEP,
                       LIGHT_SETTLE_MS*1000LL,LIGHT_DARK_PERCENT,LIGHT_BRIGHT_PERCENT);
  portEXIT_CRITICAL(&lightMux);
}
static bool lightPhotoSettled() {
  portENTER_CRITICAL(&lightMux);
  bool settled=esp_timer_get_time()-lightChangedUs>=LIGHT_SETTLE_MS*1000LL;
  // A manual request must also have been applied by loop().
  if(lightMode==LightMode::Manual&&lightAvailable&&LIGHT_ENABLED)
    settled=settled&&lightAppliedDuty==(lightManualPercent*255+50)/100;
  portEXIT_CRITICAL(&lightMux);return settled;
}
static esp_err_t lightResponse(httpd_req_t *req) {
  char response[192];
  portENTER_CRITICAL(&lightMux);
  snprintf(response,sizeof(response),"{\"enabled\":%s,\"mode\":\"%s\",\"percent\":%u,\"maximum\":%u,\"duty\":%u}",
           LIGHT_ENABLED&&lightAvailable?"true":"false",
           lightMode==LightMode::Manual?"manual":lightMode==LightMode::Auto?"auto":"off",
           lightManualPercent,LIGHT_MAX_PERCENT,lightAppliedDuty);
  portEXIT_CRITICAL(&lightMux);
  httpd_resp_set_type(req,"application/json");httpd_resp_set_hdr(req,"Cache-Control","no-store");
  httpd_resp_set_hdr(req,"Access-Control-Allow-Origin","*");
  return httpd_resp_send(req,response,HTTPD_RESP_USE_STRLEN);
}
static esp_err_t lightRequest(httpd_req_t *req) {
  if(!cameraOriginAllowed(req))return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Use the camera page");
  char query[40],value[8];
  if(httpd_req_get_url_query_str(req,query,sizeof(query))!=ESP_OK ||
     httpd_query_key_value(query,"value",value,sizeof(value))!=ESP_OK)
    return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Missing value");
  char *end;long percent=strtol(value,&end,10);
  if(!value[0]||*end||percent<0||percent>LIGHT_MAX_PERCENT)
    return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid brightness");
  portENTER_CRITICAL(&lightMux);
  bool allowed=LIGHT_ENABLED&&lightAvailable&&lightMode==LightMode::Manual;
  if(allowed)lightManualPercent=percent;
  portEXIT_CRITICAL(&lightMux);
  if(!allowed){httpd_resp_set_status(req,"409 Conflict");return lightResponse(req);}
  return lightResponse(req);
}
