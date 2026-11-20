// NFC Lab. Native USB CDC, PN532 normal frames, ISO14443-A at 106 kbit/s.
#include <Wire.h>

constexpr uint8_t address = 0x24;
bool ready = false;
uint8_t reply[64];
String selected;
bool is213 = false;

String hexBytes(const uint8_t *data, size_t count) {
  const char digits[] = "0123456789ABCDEF";
  String s;
  for (size_t i = 0; i < count; ++i) {
    s += digits[data[i] >> 4];
    s += digits[data[i] & 15];
  }
  return s;
}

bool waitReady() {
  unsigned long start = millis();
  do {
    if (Wire.requestFrom(address, size_t(1)) == 1 && Wire.read() == 1) return true;
    delay(5);
  } while (millis() - start < 1500);
  return false;
}

bool receive(uint8_t *out, size_t count) {
  if (!waitReady() || Wire.requestFrom(address, count + 1) != count + 1 || Wire.read() != 1) return false;
  return Wire.readBytes(out, count) == count;
}

// Return payload length. Validate ACK, frame length, direction, response code and checksum.
int command(const uint8_t *cmd, uint8_t count) {
  uint8_t len = count + 1, sum = 0xD4;
  uint8_t header[] = {0, 0, 0xFF, len, uint8_t(-len), sum};
  Wire.beginTransmission(address);
  Wire.write(header, sizeof(header));
  Wire.write(cmd, count);
  for (int i = 0; i < count; ++i) sum += cmd[i];
  Wire.write(uint8_t(-sum));
  Wire.write(uint8_t(0));
  if (Wire.endTransmission()) return -1;
  const uint8_t ack[] = {0, 0, 0xFF, 0, 0xFF, 0};
  uint8_t frame[64];
  if (!receive(frame, sizeof(ack)) || memcmp(frame, ack, sizeof(ack))) return -1;
  if (!receive(frame, sizeof(frame))) return -1;
  len = frame[3];
  if (frame[0] || frame[1] || frame[2] != 255 || uint8_t(len + frame[4]) ||
      len < 2 || len > sizeof(frame)-7 || frame[5] != 0xD5 || frame[6] != cmd[0]+1) return -1;
  sum = 0;
  for (int i = 5; i <= 5+len; ++i) sum += frame[i];
  if (sum || frame[6+len]) return -1;
  memcpy(reply, frame+7, len-2);
  return len-2;
}

bool scan() {
  selected = "";
  is213 = false;
  const uint8_t poll[] = {0x4A, 1, 0};
  int n = command(poll, sizeof(poll));
  if (n < 7 || reply[0] != 1 || reply[1] != 1 ||
      (reply[5] != 4 && reply[5] != 7 && reply[5] != 10) || n < 6+reply[5]) return false;
  selected = hexBytes(reply+6, reply[5]);
  return true;
}

int readPages(int page) {
  uint8_t cmd[] = {0x40, 1, 0x30, uint8_t(page)};
  return command(cmd, sizeof(cmd)) == 17 && reply[0] == 0 ? 16 : -1;
}

bool writable213() {
  if (!is213 || readPages(0) < 0) return false;
  const uint8_t cc[] = {0xE1, 0x10, 0x12, 0};
  if (reply[11] || reply[12] || memcmp(reply+13, cc, 4)) return false;
  if (readPages(40) < 0) return false;
  return !reply[1] && !reply[2] && !reply[3] && reply[8] == 0xFF &&
         !(reply[5] & 0xC0); // Reject enabled UID/counter mirroring.
}

void readClassicSector(const char *uid, int sector, char keyType, const char *key) {
  if (!scan() || selected != uid) {
    Serial.println("ERR expected card was not selected");
    return;
  }

  uint8_t uidLength = reply[5];
  uint8_t atqa = reply[3];
  bool classic1K = reply[4] == 0x08 && (atqa == 0x04 || atqa == 0x44);
  bool classic4K = reply[4] == 0x18 && (atqa == 0x02 || atqa == 0x42);
  if (reply[2] || (uidLength != 4 && uidLength != 7) ||
      (!classic4K && !classic1K) || sector < 0 || sector >= (classic4K ? 40 : 16)) {
    Serial.println("ERR unsupported Classic layout or sector");
    return;
  }

  int first = sector < 32 ? sector * 4 : 128 + (sector - 32) * 16;
  int count = sector < 32 ? 4 : 16;
  uint8_t auth[] = {0x40, 1, uint8_t(keyType == 'A' ? 0x60 : 0x61), uint8_t(first),
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
  memcpy(auth + 10, reply + 6 + uidLength - 4, 4);
  for (int i = 0; i < 6; ++i) {
    char pair[] = {key[2 * i], key[2 * i + 1], 0};
    auth[4 + i] = strtoul(pair, nullptr, 16);
  }
  int length = command(auth, sizeof(auth));
  if (length != 1 || reply[0]) {
    Serial.println(length == 1 ? "OK AUTH " + hexBytes(reply, 1) : "OK AUTH IO");
    return;
  }

  // Read the trailer first so its access conditions survive a later data error.
  String fields[16];
  bool failed = false;
  for (int step = 0; step < count; ++step) {
    int offset = step == 0 ? count - 1 : step - 1;
    if (failed) {
      fields[offset] = "-";
      continue;
    }
    uint8_t read[] = {0x40, 1, 0x30, uint8_t(first + offset)};
    length = command(read, sizeof(read));
    if (length == 17 && reply[0] == 0) {
      fields[offset] = step == 0 ? "T" + hexBytes(reply + 7, 4) : hexBytes(reply + 1, 16);
    } else {
      fields[offset] = length > 0 && reply[0] ? "E" + hexBytes(reply, 1) : "EIO";
      // A failed exchange can invalidate the selected/authenticated state.
      failed = true;
    }
  }
  Serial.print("OK READ");
  for (int offset = 0; offset < count; ++offset) Serial.print(" " + fields[offset]);
  Serial.println();
}

void handle(String line) {
  int sda, scl, page, consumed;
  char uid[21], data[9];
  if (sscanf(line.c_str(), "INIT %d %d%n", &sda, &scl, &consumed) == 2 && consumed == line.length()) {
    ready = false;
    selected = "";
    if (sda < 0 || scl < 0 || sda > 10 || scl > 10 || sda == scl) {
      Serial.println("ERR expected distinct exposed GPIO0..10"); return;
    }
    Wire.end();
    if (Wire.begin(sda, scl, 100000)) {
      uint8_t info[] = {2}, sam[] = {0x14, 1, 0x14, 0}, retries[] = {0x32, 5, 0xFF, 1, 2};
      if (command(info, 1) == 4 && reply[0] == 0x32) {
        String version = hexBytes(reply, 4);
        ready = command(sam, sizeof(sam)) == 0 && command(retries, sizeof(retries)) == 0;
        if (ready) { Serial.println("OK " + version); return; }
      }
    }
    Serial.println("ERR PN532 initialization failed"); return;
  }
  if (!ready) { Serial.println("ERR initialize reader first"); return; }
  int sector;
  char keyType, key[13];
  if (sscanf(line.c_str(), "CLASSIC %20[0-9A-F] %d %c %12[0-9A-F]%n",
             uid, &sector, &keyType, key, &consumed) == 4 &&
      consumed == line.length() && strlen(key) == 12 && (keyType == 'A' || keyType == 'B')) {
    readClassicSector(uid, sector, keyType, key);
    return;
  }
  if (line == "SCAN") {
    if (!scan()) { Serial.println("ERR no target or poll failed"); return; }
    String atqa = hexBytes(reply+2, 2), sak = hexBytes(reply+4, 1);
    String uid = selected, version = "-", diagnostics;
    if (sak == "00" && selected.length() == 14) {
      uint8_t cmd[] = {0x40, 1, 0x60};
      int length = command(cmd, sizeof(cmd));
      diagnostics = length > 0 ? " " + hexBytes(reply, 1) : " -";
      diagnostics += " " + String(length);
      if (length > 1 && !reply[0]) {
        version = hexBytes(reply + 1, length - 1);
      } else if (atqa == "0044") {
        if (scan() && selected == uid && hexBytes(reply + 2, 2) == atqa &&
            hexBytes(reply + 4, 1) == sak) {
          uint8_t read[] = {0x40, 1, 0x30, 0};
          length = command(read, sizeof(read));
          diagnostics += length > 0 ? " " + hexBytes(reply, 1) : " -";
          diagnostics += " " + String(length);
          diagnostics += length == 17 && !reply[0] ? " " + hexBytes(reply + 1, 16) : " -";
        } else {
          diagnostics += " RESELECT";
        }
      }
    }
    is213 = atqa == "0044" && sak == "00" &&
            (version == "0004040201000F03" || version == "0004040201010F03");
    Serial.println("OK " + uid + " " + atqa + " " + sak + " " + version + diagnostics);
    return;
  }
  if (sscanf(line.c_str(), "PAGE %d%n", &page, &consumed) == 1 && consumed == line.length() &&
      selected.length() && page >= 0 && page <= 255) {
    uint8_t cmd[] = {0x40, 1, 0x3A, uint8_t(page), uint8_t(page)};
    if (command(cmd, sizeof(cmd)) == 5 && !reply[0]) {
      Serial.println("OK " + hexBytes(reply+1, 4)); return;
    }
  }
  if (sscanf(line.c_str(), "WRITE %20[0-9A-F] %d %8[0-9A-F]%n", uid, &page, data, &consumed) == 3 &&
      consumed == line.length() && strlen(data) == 8 && selected == uid && page >= 4 && page <= 39 && writable213()) {
    uint8_t cmd[] = {0x40, 1, 0xA2, uint8_t(page), 0, 0, 0, 0};
    for (int i = 0; i < 4; ++i) {
      char pair[] = {data[2*i], data[2*i+1], 0};
      cmd[4+i] = strtoul(pair, nullptr, 16);
    }
    int n = command(cmd, sizeof(cmd));
    if ((n == 1 || (n == 2 && reply[1] == 0x0A)) && !reply[0] &&
        readPages(page) == 16 && !memcmp(reply+1, cmd+4, 4)) {
      Serial.println("OK verified"); return;
    }
  }
  Serial.println("ERR operation unavailable or verification failed");
}

void setup() { Serial.begin(115200); }
void loop() {
  static String line;
  static bool overflow;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (overflow) Serial.println("ERR command too long");
      else handle(line);
      line = ""; overflow = false;
    } else if (c != '\r') {
      if (line.length() < 96) line += c;
      else overflow = true;
    }
  }
}
