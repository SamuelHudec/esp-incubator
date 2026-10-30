// Bench-only FlySkyHy compatibility probe. No LoRa or GNSS support.
// Arduino ESP32 core 2.0.17; built-in BLE library; ESP32 with BLE required.
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

BLECharacteristic *output;
volatile bool connected = false;
uint32_t lastHeartbeat = 0;
uint32_t testStarted = 0;
bool testActive = false;
String command;

class ConnectionCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { connected = true; }
  void onDisconnect(BLEServer *) override {
    connected = false;
    BLEDevice::startAdvertising();
  }
};

void sendSentence(const String &body) {
  uint8_t checksum = 0;
  for (size_t i = 0; i < body.length(); ++i) checksum ^= body[i];
  char suffix[6];
  snprintf(suffix, sizeof(suffix), "*%02X\r\n", checksum);
  String line = "$" + body + suffix;
  Serial.print(line);
  if (!connected) return;
  // Safe for the default ATT MTU of 23. Preserve newline only at line end.
  for (size_t i = 0; i < line.length(); i += 20) {
    size_t length = line.length() - i;
    if (length > 20) length = 20;
    output->setValue((uint8_t *)line.c_str() + i, length);
    output->notify();
    delay(30);
    if (!connected) break;
  }
}

void setup() {
  Serial.begin(115200);
  command.reserve(16);
  BLEDevice::init("FANET-Bench");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ConnectionCallbacks());
  BLEService *service = server->createService("FFE0");
  output = service->createCharacteristic("FFE1",
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  output->addDescriptor(new BLE2902());
  service->start();
  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID("FFE0");
  advertising->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.println("BENCH ONLY: TEST starts synthetic traffic for 60s; STOP ends it.");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      command.trim();
      if (command == "TEST") { testActive = true; testStarted = millis(); }
      if (command == "STOP") testActive = false;
      command = "";
    } else if (command.length() < 16) command += c;
  }
  uint32_t now = millis();
  if (testActive && (uint32_t)(now - testStarted) >= 60000) testActive = false;
  if ((uint32_t)(now - lastHeartbeat) >= 1000) {
    lastHeartbeat = now;
    // TX=0: no radio transmission. GPS=0: this probe has no own fix.
    sendSentence(testActive ? "PFLAU,1,0,0,1,0,,0,," : "PFLAU,0,0,0,1,0,,0,,");
    if (testActive) {
      // Synthetic target: 200m north, 100m east, 50m above app reference.
      // ID type 0, arbitrary test ID; aircraft type 7 = paraglider (FLARM).
      sendSentence("PFLAA,0,200,100,50,0,ABCDEF,90,,10,0,7");
    }
  }
  delay(5);
}
