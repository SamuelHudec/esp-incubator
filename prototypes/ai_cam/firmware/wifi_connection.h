#pragma once

// Optional credentials keep existing single-network secrets.h files compatible.
#ifndef WIFI_FALLBACK_SSID
#define WIFI_FALLBACK_SSID ""
#endif
#ifndef WIFI_FALLBACK_PASSWORD
#define WIFI_FALLBACK_PASSWORD ""
#endif

static constexpr uint32_t WIFI_ATTEMPT_MS = 15000;
static bool wifiStarted = false;
static bool wifiHadConnection = false;
static bool wifiTryingFallback = false;
static uint32_t wifiAttemptStarted = 0;

static void wifiAttempt(bool fallback) {
  wifiTryingFallback = fallback;
  WiFi.disconnect(false, false);
  Serial.printf("WIFI   trying %s network (15s timeout)\n", fallback ? "fallback" : "primary");
  WiFi.begin(fallback ? WIFI_FALLBACK_SSID : WIFI_SSID,
             fallback ? WIFI_FALLBACK_PASSWORD : WIFI_PASSWORD);
  wifiAttemptStarted = millis();
}

static void wifiTick() {
  if (!wifiStarted) return;
  if (WiFi.status() == WL_CONNECTED) {
    wifiHadConnection = true;
    return;  // Stay on a working fallback rather than interrupting the stream.
  }
  if (wifiHadConnection) {
    wifiHadConnection = false;
    wifiAttempt(false);
  } else if (uint32_t(millis() - wifiAttemptStarted) >= WIFI_ATTEMPT_MS) {
    wifiAttempt(!wifiTryingFallback && WIFI_FALLBACK_SSID[0] != '\0');
  }
}

static void wifiStart(const char *hostname) {
  WiFi.setHostname(hostname);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);  // This state machine owns reconnect attempts.
  WiFi.setSleep(false);
  wifiStarted = true;
  wifiAttempt(false);
}
