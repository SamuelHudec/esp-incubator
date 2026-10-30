"""Host checks for the shared illumination controller; no camera required."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class IlluminationTests(unittest.TestCase):
    def test_auto_controller(self):
        source = Path(__file__).resolve().parents[2]/'firmware'
        code = r'''
#include "light_policy.h"
#include <cassert>
int main() {
    LightPolicy p;p.reset(0);
    assert(!p.update(0,1000000,1000000,64,8,2000000,20,35));
    assert(p.update(10,2000000,2000000,64,8,2000000,20,35));
    assert(p.duty==8);
    // A late-arriving frame captured before settling must not change brightness.
    assert(!p.update(0,3000000,5000000,64,8,2000000,20,35));
    assert(p.duty==8);
    assert(!p.update(27,4000000,5000000,64,8,2000000,20,35));
    assert(p.duty==8); // Inside deadband.
    p.smoothed=-1;
    assert(p.update(50,5000000,5000000,64,8,2000000,20,35));
    assert(p.duty==0);
    // Clamp at both ends; do not wrap the unsigned duty.
    p.duty=60;p.smoothed=-1;
    assert(p.update(0,7000000,7000000,64,8,2000000,20,35));
    assert(p.duty==64);
    assert(!p.update(0,9000000,9000000,64,8,2000000,20,35));
    p.duty=3;p.smoothed=-1;
    assert(p.update(100,9000000,9000000,64,8,2000000,20,35));
    assert(p.duty==0);
    assert(!p.update(-1,12000000,12000000,64,8,2000000,20,35));
    assert(!p.update(101,12000000,12000000,64,8,2000000,20,35));
    p.duty=64;p.reset(13000000);assert(p.duty==0&&p.smoothed==-1);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'test.cpp').write_text(code)
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',
                            '-I'+str(source),str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_mode_lifecycle_and_master_off(self):
        source = Path(__file__).resolve().parents[2]/'firmware'
        stubs = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cassert>
#define INPUT 0
#define OUTPUT 1
#define LOW 0
using portMUX_TYPE=int;
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
int64_t clockUs=1000000;
int64_t esp_timer_get_time(){return clockUs;}
void pinMode(int pin,int){assert(pin==4);}void digitalWrite(int pin,int value){assert(pin==4&&value==0);}
struct {void println(const char*){}} Serial;
constexpr bool LIGHT_ENABLED=TEST_LIGHT_ENABLED;
constexpr uint8_t LIGHT_MAX_PERCENT=25,LIGHT_AUTO_STEP=8;
constexpr int LIGHT_SETTLE_MS=2000;
constexpr float LIGHT_DARK_PERCENT=20,LIGHT_BRIGHT_PERCENT=35;
using esp_err_t=int;constexpr int ESP_OK=0,HTTPD_400_BAD_REQUEST=400,HTTPD_RESP_USE_STRLEN=-1;
struct httpd_req_t {};
int httpd_resp_send_err(httpd_req_t*,int,const char*){return -1;}
int httpd_resp_set_type(httpd_req_t*,const char*){return 0;}
int httpd_resp_set_hdr(httpd_req_t*,const char*,const char*){return 0;}
int httpd_resp_send(httpd_req_t*,const char*,int){return 0;}
int httpd_resp_set_status(httpd_req_t*,const char*){return 0;}
int httpd_req_get_url_query_str(httpd_req_t*,char*,size_t){return -1;}
int httpd_query_key_value(const char*,const char*,char*,size_t){return -1;}
#include "illumination.h"
static bool cameraOriginAllowed(httpd_req_t*){return true;}
int main(){
 lightStart();assert(lightAvailable==LIGHT_ENABLED);
 {
  LightStreamGuard stream(LightMode::Manual);
  lightManualPercent=20;lightTick();
  assert(lightAppliedDuty==(LIGHT_ENABLED?51:0));
  if(LIGHT_ENABLED)assert(!lightPhotoSettled());
  clockUs+=2100000;assert(lightPhotoSettled());
 }
 lightTick();assert(lightAppliedDuty==0);
 clockUs+=10000000;
 {
  LightStreamGuard stream(LightMode::Auto);
  clockUs+=2100000;lightStreamHeartbeat();
  int8_t dark[16]={};lightObserve(dark,16,clockUs);lightTick();
  assert(lightAppliedDuty==(LIGHT_ENABLED?8:0));
  clockUs+=4100000;lightTick();assert(lightAppliedDuty==0);
 }
 lightTick();assert(lightMode==LightMode::Off&&lightAppliedDuty==0);
}
'''
        driver = r'''
#pragma once
constexpr int LEDC_LOW_SPEED_MODE=0,LEDC_TIMER_1=1,LEDC_TIMER_8_BIT=8;
constexpr int LEDC_AUTO_CLK=0,LEDC_CHANNEL_2=2;
struct ledc_timer_config_t {int speed_mode,timer_num,duty_resolution,freq_hz,clk_cfg;};
struct ledc_channel_config_t {int gpio_num,speed_mode,channel,timer_sel,duty;};
int ledc_timer_config(ledc_timer_config_t*t){assert(t->timer_num==1&&t->freq_hz==5000);return 0;}
int ledc_channel_config(ledc_channel_config_t*c){assert(c->channel==2&&c->timer_sel==1&&c->gpio_num==4);return 0;}
int ledc_set_duty(int,int,unsigned){return 0;}int ledc_update_duty(int,int){return 0;}
int ledc_stop(int,int,int){return 0;}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'driver').mkdir()
            (path/'driver/ledc.h').write_text(driver)
            (path/'test.cpp').write_text(stubs)
            for enabled in (0, 1):
                subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',
                                '-Wno-unused-function',f'-DTEST_LIGHT_ENABLED={enabled}',
                                '-I'+str(path),'-I'+str(source),str(path/'test.cpp'),
                                '-o',str(path/'test')],check=True)
                subprocess.run([str(path/'test')],check=True)
