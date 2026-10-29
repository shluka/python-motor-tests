#include <Arduino.h>
#include <esp_timer.h>

// One sensor is connected at a time to this single divider input.
// Wiring: 3V3 -> sensor -> GPIO4 -> fixed-resistor socket -> GND.
const uint8_t SENSOR_PIN = 4;
const uint32_t BAUD_RATE = 115200;
const uint32_t SAMPLE_PERIOD_US = 10000; // 100 samples/s
const uint8_t ADC_AVERAGES = 8;

uint64_t nextSampleUs = 0;
uint64_t sequence = 0;

void setup() {
  Serial.begin(BAUD_RATE);
  analogReadResolution(12);
  pinMode(SENSOR_PIN, INPUT);
  analogSetPinAttenuation(SENSOR_PIN, ADC_11db);
  delay(2000);
  nextSampleUs = (uint64_t)esp_timer_get_time();
}

void loop() {
  const uint64_t now = (uint64_t)esp_timer_get_time();
  if (now < nextSampleUs) return;

  // Skip late acquisition slots instead of generating a catch-up burst.
  const uint64_t missed = (now - nextSampleUs) / SAMPLE_PERIOD_US;
  sequence += missed;
  nextSampleUs += (missed + 1) * SAMPLE_PERIOD_US;

  // Discard the first conversion, then average calibrated millivolt readings.
  analogReadMilliVolts(SENSOR_PIN);
  uint32_t sumMv = 0;
  for (uint8_t k = 0; k < ADC_AVERAGES; ++k) {
    sumMv += analogReadMilliVolts(SENSOR_PIN);
  }
  const float voltage = sumMv / (1000.0f * ADC_AVERAGES);

  // Protocol: S,sequence,time_us,Vout
  Serial.print("S,");
  Serial.print((unsigned long long)sequence++);
  Serial.print(',');
  Serial.print((unsigned long long)now);
  Serial.print(',');
  Serial.println(voltage, 6);
}
