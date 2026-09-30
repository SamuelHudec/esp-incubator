#include <Arduino.h>
#include <RF24.h>
#include <SPI.h>

namespace {

constexpr uint8_t PIN_CE = 1;
constexpr uint8_t PIN_CSN = 3;
constexpr uint8_t PIN_SCK = 5;
constexpr uint8_t PIN_MISO = 6;
constexpr uint8_t PIN_MOSI = 7;

// A conservative clock is more tolerant of jumper wires and breadboards.
constexpr uint32_t SPI_FREQUENCY_HZ = 4000000UL;
constexpr uint32_t STATUS_INTERVAL_MS = 2000UL;

RF24 radio(PIN_CE, PIN_CSN, SPI_FREQUENCY_HZ);
bool radioDetected = false;
uint32_t lastStatusAt = 0;

const __FlashStringHelper* dataRateName(rf24_datarate_e rate) {
  switch (rate) {
    case RF24_250KBPS:
      return F("250 kbps");
    case RF24_1MBPS:
      return F("1 Mbps");
    case RF24_2MBPS:
      return F("2 Mbps");
    default:
      return F("unknown");
  }
}

void printPinout() {
  Serial.println(F("SPI pinout:"));
  Serial.printf("  SCK  = GPIO%u\n", PIN_SCK);
  Serial.printf("  MISO = GPIO%u\n", PIN_MISO);
  Serial.printf("  MOSI = GPIO%u\n", PIN_MOSI);
  Serial.printf("  CSN  = GPIO%u\n", PIN_CSN);
  Serial.printf("  CE   = GPIO%u\n", PIN_CE);
}

void printRadioSummary() {
  Serial.println(F("nRF24: detected"));
  Serial.print(F("Model: "));
  Serial.println(radio.isPVariant() ? F("nRF24L01+") : F("nRF24L01 compatible"));
  Serial.printf("Channel: %u (%u MHz)\n", radio.getChannel(),
                2400U + radio.getChannel());
  Serial.print(F("Data rate: "));
  Serial.println(dataRateName(radio.getDataRate()));
  Serial.println(F("TX: disabled; radio powered down"));
}

}  // namespace

void setup() {
  Serial.begin(115200);

  // Give a native USB serial connection a short time to appear, but never block
  // startup indefinitely when the board is powered without a computer.
  const uint32_t serialWaitStartedAt = millis();
  while (!Serial && millis() - serialWaitStartedAt < 3000) {
    delay(10);
  }

  Serial.println();
  Serial.println(F("2.4 GHz Signal Lab - SPI diagnostic"));
  printPinout();
  Serial.printf("SPI clock: %lu Hz\n", static_cast<unsigned long>(SPI_FREQUENCY_HZ));

  pinMode(PIN_CE, OUTPUT);
  digitalWrite(PIN_CE, LOW);

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CSN);
  radioDetected = radio.begin(&SPI);

  if (!radioDetected || !radio.isChipConnected()) {
    radioDetected = false;
    Serial.println(F("nRF24: NOT DETECTED"));
    Serial.println(F("Check 3.3 V power, common GND, capacitor, and SPI wiring."));
    return;
  }

  // No RX or TX is needed for this test. Power down the RF section after the
  // register check; SPI remains available for connection monitoring.
  radio.stopListening();
  radio.powerDown();
  printRadioSummary();
}

void loop() {
  const uint32_t now = millis();
  if (now - lastStatusAt < STATUS_INTERVAL_MS) {
    delay(10);
    return;
  }
  lastStatusAt = now;

  const bool connected = radio.isChipConnected();
  if (connected != radioDetected) {
    radioDetected = connected;
    Serial.println(connected ? F("nRF24: connection restored")
                             : F("nRF24: connection lost"));
  }
}
