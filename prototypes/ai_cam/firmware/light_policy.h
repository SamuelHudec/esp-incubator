#pragma once
#include <stdint.h>

// Pure controller: input is mean grayscale intensity as a percentage, not lux.
struct LightPolicy {
  float smoothed=-1;
  uint8_t duty=0;
  int64_t changedUs=0;
  void reset(int64_t now) {smoothed=-1;duty=0;changedUs=now;}
  bool update(float brightness,int64_t sampleUs,int64_t now,uint8_t maximum,
              uint8_t step,int64_t settleUs,float low,float high) {
    // Never adjust using a frame exposed before the previous change settled.
    if(sampleUs<changedUs+settleUs || brightness<0 || brightness>100)return false;
    smoothed=smoothed<0?brightness:.75f*smoothed+.25f*brightness;
    if(now<changedUs+settleUs)return false;
    uint8_t next=duty;
    if(smoothed<low)next=(duty+step>maximum)?maximum:duty+step;
    else if(smoothed>high)next=duty<step?0:duty-step;
    if(next==duty)return false;
    duty=next;changedUs=now;smoothed=-1;return true;
  }
};
