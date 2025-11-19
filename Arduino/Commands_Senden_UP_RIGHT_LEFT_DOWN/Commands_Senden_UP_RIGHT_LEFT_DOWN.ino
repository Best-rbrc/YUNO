#include <Arduino.h>
#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <LiquidCrystal.h>

// -------------------- LCD + JOYSTICK PINS --------------------
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// Joystick axes swapped to match physical orientation
const int xPin = A1;   // Joystick X-axis (left/right)
const int yPin = A0;   // Joystick Y-axis (up/down)
const int swPin = 7;   // Joystick Button

// -------------------- WLAN + MQTT SETTINGS --------------------
const char* WIFI_SSID     = "Robin";
const char* WIFI_PASSWORD = "12345678";
const char* MQTT_HOST     = "172.20.10.2";
const uint16_t MQTT_PORT  = 1883;

const char* TOPIC_IN  = "pi/to/arduino";
const char* TOPIC_OUT = "arduino/to/pi";

// -------------------- DISPLAY STATE --------------------
String lineTop = "";
String lineBottom = "";
int scrollPos = 0;

// -------------------- MQTT CLIENT --------------------
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// -------------------- HELPER FUNCTIONS --------------------
String crop(const String& s, int start) {
  if (start < 0) start = 0;
  int end = start + 16;
  if (end > s.length()) end = s.length();
  String out = s.substring(start, end);
  while (out.length() < 16) out += " ";
  return out;
}

void render() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(crop(lineTop, 0));
  lcd.setCursor(0, 1);
  lcd.print(crop(lineBottom, scrollPos));
}

void flickerDisplay() {
  for (int i = 0; i < 10; i++) {
    lcd.noDisplay();
    delay(100);
    lcd.display();
    delay(100);
  }
  render();
}

void handleCommand(const String& cmd) {
  Serial.print("Received command: "); // DEBUG
  Serial.println(cmd);                // DEBUG

  if (cmd.startsWith("NAME:")) {
    lineTop = cmd.substring(5);
    scrollPos = 0;
  } else if (cmd.startsWith("DESC:")) {
    lineBottom = cmd.substring(5);
    scrollPos = 0;
  } else if (cmd == "CLEAR") {
    lineTop = "";
    lineBottom = "";
  } else if (cmd == "FLICKER") {
    flickerDisplay();
    return;
  }
  render();
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  Serial.println("MQTT message received"); // DEBUG

  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  handleCommand(msg);
}

void ensureMqtt() {
  if (mqtt.connected()) return;

  Serial.println("MQTT not connected! Attempting reconnect..."); // DEBUG

  while (!mqtt.connected()) {
    Serial.print("Connecting to MQTT... "); // DEBUG
    if (mqtt.connect("arduino-lcd-client")) {
      Serial.println("connected!"); // DEBUG
      mqtt.subscribe(TOPIC_IN);
      Serial.println("Subscribed to: pi/to/arduino"); // DEBUG
    } else {
      Serial.print("MQTT failed, rc="); // DEBUG
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

// -------------------- SETUP --------------------
void setup() {
  Serial.begin(9600);
  lcd.begin(16, 2);
  pinMode(swPin, INPUT_PULLUP);

  Serial.print("Connecting to WiFi "); // DEBUG
  Serial.print(WIFI_SSID);            // DEBUG
  Serial.println(" ...");             // DEBUG

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");                // DEBUG
    timeout++;
    if (timeout > 30) {
      Serial.println("\n❌ WiFi connection FAILED!"); // DEBUG
      break;
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✔️ WiFi connected!");         // DEBUG
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("⚠️ Not connected to WiFi!");     // DEBUG
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);

  ensureMqtt();

  lineTop = "YUNO";
  lineBottom = "Smart Learning";
  render();
}

// -------------------- MAIN LOOP --------------------
enum JoyState { NEUTRAL, UP, DOWN, LEFT, RIGHT };
static JoyState lastState = NEUTRAL;

void loop() {
  // ---------------- Debug: WiFi & MQTT status ----------------
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ Lost WiFi connection!"); // DEBUG
  }

  if (!mqtt.connected()) {
    Serial.println("⚠️ MQTT lost, reconnecting..."); // DEBUG
    ensureMqtt();
  }

  mqtt.loop();

  // ---------------- Joystick reading ----------------
  int xVal = analogRead(xPin);
  int yVal = analogRead(yPin);
  int btn  = digitalRead(swPin);

  // Debug raw values
  Serial.print("JOY X:");
  Serial.print(xVal);
  Serial.print(" Y:");
  Serial.print(yVal);
  Serial.print(" BTN:");
  Serial.println(btn);

  bool changed = false;
  JoyState currentState = NEUTRAL;

  if (yVal < 400) currentState = DOWN;
  else if (yVal > 600) currentState = UP;
  else if (xVal < 400) currentState = LEFT;
  else if (xVal > 600) currentState = RIGHT;

  if (currentState != lastState && currentState != NEUTRAL) {
    switch (currentState) {
      case UP:
        mqtt.publish(TOPIC_OUT, "JOY:UP");
        Serial.println("JOY:UP"); // DEBUG
        break;
      case DOWN:
        mqtt.publish(TOPIC_OUT, "JOY:DOWN");
        Serial.println("JOY:DOWN"); // DEBUG
        break;
      case LEFT:
        mqtt.publish(TOPIC_OUT, "JOY:LEFT");
        Serial.println("JOY:LEFT"); // DEBUG
        if (scrollPos > 0) scrollPos--;
        changed = true;
        break;
      case RIGHT:
        mqtt.publish(TOPIC_OUT, "JOY:RIGHT");
        Serial.println("JOY:RIGHT"); // DEBUG
        if (scrollPos < max(0, (int)lineBottom.length() - 16)) scrollPos++;
        changed = true;
        break;
      default: break;
    }
  }

  lastState = currentState;

  static int lastBtn = HIGH;
  if (btn == LOW && lastBtn == HIGH) {
    mqtt.publish(TOPIC_OUT, "JOY:PRESS");
    Serial.println("JOY:PRESS"); // DEBUG
  }
  lastBtn = btn;

  if (changed) render();

  delay(50);
}