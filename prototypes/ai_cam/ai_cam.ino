#include <WiFi.h>
#include <ESPmDNS.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "secrets.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "freertos/task.h"

// AI-Thinker ESP32-CAM / OV2640. Pin sources and power notes: README.md.
static httpd_handle_t server = nullptr;
static const char *HOSTNAME = "ai-cam";

// Window counters are shared by the HTTP task and Arduino loop task.
static portMUX_TYPE metricsMux = portMUX_INITIALIZER_UNLOCKED;
static uint32_t acquiredFrames = 0, sentFrames = 0, frameErrors = 0;
static uint64_t sentBytes = 0, acquireUs = 0, sendUs = 0;
static uint32_t sendAttempts = 0;
static size_t imageWidth = 0, imageHeight = 0;
static int64_t metricsStartUs = 0;
static const uint32_t STREAM_PAUSE_MS = 30;

#if configGENERATE_RUN_TIME_STATS && configUSE_TRACE_FACILITY && CONFIG_FREERTOS_RUN_TIME_STATS_USING_ESP_TIMER
#define HAS_CPU_METRICS 1
static configRUN_TIME_COUNTER_TYPE previousIdle[portNUM_PROCESSORS] = {};
static void readCpuMetrics(double *busy, uint64_t elapsedUs) {
  for (int core = 0; core < portNUM_PROCESSORS; ++core) {
    TaskStatus_t status = {};
    vTaskGetInfo(xTaskGetIdleTaskHandleForCore(core), &status, pdFALSE, eInvalid);
    // Unsigned subtraction handles the runtime counter's wraparound.
    configRUN_TIME_COUNTER_TYPE idleDelta = status.ulRunTimeCounter - previousIdle[core];
    previousIdle[core] = status.ulRunTimeCounter;
    double percent = elapsedUs ? 100.0 * (1.0 - (double)idleDelta / elapsedUs) : 0;
    busy[core] = constrain(percent, 0.0, 100.0);
  }
}
#endif

static void reportMetrics() {
  int64_t now = esp_timer_get_time();
  uint64_t elapsed = now - metricsStartUs;
  if (elapsed < 5000000) return;
  metricsStartUs = now;
  portENTER_CRITICAL(&metricsMux);
  uint32_t acquired = acquiredFrames, sent = sentFrames, errors = frameErrors;
  uint32_t attempts = sendAttempts;
  uint64_t bytes = sentBytes, captureTime = acquireUs, networkTime = sendUs;
  size_t width = imageWidth, height = imageHeight;
  acquiredFrames = sentFrames = frameErrors = sendAttempts = 0;
  sentBytes = acquireUs = sendUs = 0;
  portEXIT_CRITICAL(&metricsMux);

#ifdef HAS_CPU_METRICS
  double busy[portNUM_PROCESSORS];
  readCpuMetrics(busy, elapsed);
#endif
  Serial.printf("METRICS window=%.2fs image=%ux%u acquired=%lu sent=%lu "
                "fps=%.2f jpeg_avg=%.1fKiB payload=%.1fKiB/s "
                "acquire_avg=%.2fms send_avg=%.2fms errors=%lu\n",
                elapsed / 1e6, (unsigned)width, (unsigned)height,
                (unsigned long)acquired, (unsigned long)sent, sent * 1e6 / elapsed,
                sent ? bytes / (1024.0 * sent) : 0.0, bytes * 1e6 / (1024.0 * elapsed),
                acquired ? captureTime / (1000.0 * acquired) : 0.0,
                attempts ? networkTime / (1000.0 * attempts) : 0.0,
                (unsigned long)errors);
#ifdef HAS_CPU_METRICS
  for (int core = 0; core < portNUM_PROCESSORS; ++core) {
    Serial.printf("cpu%d_busy=%.1f%% ", core, busy[core]);
  }
#else
  Serial.print("cpu_busy=unavailable ");
#endif
  Serial.printf("cpu_clock=%luMHz internal_free=%u internal_min=%u "
                "internal_largest=%u psram_free=%u psram_min=%u rssi=%lddBm\n",
                (unsigned long)ESP.getCpuFreqMHz(),
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
                (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
                (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
                (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM),
                (long)WiFi.RSSI());
}

static esp_err_t streamVideo(httpd_req_t *request) {
  esp_err_t result = httpd_resp_set_type(
      request, "multipart/x-mixed-replace;boundary=frame");
  if (result != ESP_OK) return result;
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");

  while (true) {
    int64_t captureStart = esp_timer_get_time();
    camera_fb_t *frame = esp_camera_fb_get();
    uint64_t captureElapsed = esp_timer_get_time() - captureStart;
    portENTER_CRITICAL(&metricsMux);
    if (frame) {
      ++acquiredFrames;
      acquireUs += captureElapsed;
      imageWidth = frame->width;
      imageHeight = frame->height;
    } else {
      ++frameErrors;
    }
    portEXIT_CRITICAL(&metricsMux);
    if (!frame) return ESP_FAIL;

    char header[96];
    int length = snprintf(header, sizeof(header),
        "\r\n--frame\r\nContent-Type: image/jpeg\r\n"
        "Content-Length: %zu\r\n\r\n", frame->len);
    if (length < 0 || (size_t)length >= sizeof(header)) {
      portENTER_CRITICAL(&metricsMux);
      ++frameErrors;
      portEXIT_CRITICAL(&metricsMux);
      esp_camera_fb_return(frame);
      return ESP_FAIL;
    }
    int64_t sendStart = esp_timer_get_time();
    result = httpd_resp_send_chunk(request, header, length);
    if (result == ESP_OK) {
      result = httpd_resp_send_chunk(request, (const char *)frame->buf, frame->len);
    }
    uint64_t sendElapsed = esp_timer_get_time() - sendStart;
    portENTER_CRITICAL(&metricsMux);
    ++sendAttempts;
    sendUs += sendElapsed;
    if (result == ESP_OK) {
      ++sentFrames;
      sentBytes += frame->len;
    } else {
      ++frameErrors;
    }
    portEXIT_CRITICAL(&metricsMux);
    // Always release the buffer, including when the phone disconnects.
    esp_camera_fb_return(frame);
    if (result != ESP_OK) return result;
    delay(STREAM_PAUSE_MS);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  if (!psramFound()) {
    Serial.println("PSRAM not found. Select AI Thinker ESP32-CAM and check the board.");
    return;
  }

  camera_config_t camera = {};
  camera.pin_pwdn = 32;
  camera.pin_reset = -1;
  camera.pin_xclk = 0;
  camera.pin_sccb_sda = 26;
  camera.pin_sccb_scl = 27;
  camera.pin_d0 = 5;
  camera.pin_d1 = 18;
  camera.pin_d2 = 19;
  camera.pin_d3 = 21;
  camera.pin_d4 = 36;
  camera.pin_d5 = 39;
  camera.pin_d6 = 34;
  camera.pin_d7 = 35;
  camera.pin_vsync = 25;
  camera.pin_href = 23;
  camera.pin_pclk = 22;
  camera.xclk_freq_hz = 20000000;
  camera.ledc_timer = LEDC_TIMER_0;
  camera.ledc_channel = LEDC_CHANNEL_0;
  camera.pixel_format = PIXFORMAT_JPEG;
  camera.frame_size = FRAMESIZE_QVGA;  // 320 x 240
  camera.jpeg_quality = 12;
  camera.fb_count = 2;
  camera.fb_location = CAMERA_FB_IN_PSRAM;
  camera.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t result = esp_camera_init(&camera);
  if (result != ESP_OK) {
    Serial.printf("Camera initialization failed: %s\n", esp_err_to_name(result));
    return;
  }

  WiFi.setHostname(HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.setSleep(false);
  Serial.println("Connecting to Wi-Fi (2.4 GHz)...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print('.');
  }
  Serial.println();

  metricsStartUs = esp_timer_get_time();
#ifdef HAS_CPU_METRICS
  double initialBusy[portNUM_PROCESSORS];
  readCpuMetrics(initialBusy, 0);
#endif
  Serial.printf("Metrics every 5s; JPEG QVGA quality=12 buffers=2 pause=%lums\n",
                (unsigned long)STREAM_PAUSE_MS);
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_open_sockets = 2;
  config.lru_purge_enable = true;
  config.send_wait_timeout = 3;
  result = httpd_start(&server, &config);
  if (result == ESP_OK) {
    httpd_uri_t stream = {};
    stream.uri = "/";
    stream.method = HTTP_GET;
    stream.handler = streamVideo;
    result = httpd_register_uri_handler(server, &stream);
    if (result != ESP_OK) httpd_stop(server);
  }
  if (result != ESP_OK) {
    Serial.printf("HTTP server failed: %s\n", esp_err_to_name(result));
    return;
  }
  if (MDNS.begin(HOSTNAME)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("Open on your phone: http://%s.local/\n", HOSTNAME);
  } else {
    Serial.println("mDNS failed; use the IP address below.");
  }
  Serial.printf("Camera IP address: http://%s/\n", WiFi.localIP().toString().c_str());
}

void loop() {
  // Print the current address after a Wi-Fi reconnection or DHCP change.
  static IPAddress lastAddress;
  if (WiFi.status() == WL_CONNECTED && WiFi.localIP() != lastAddress) {
    lastAddress = WiFi.localIP();
    Serial.printf("Camera address: http://%s/\n", lastAddress.toString().c_str());
  }
  if (metricsStartUs) reportMetrics();
  delay(100);
}
