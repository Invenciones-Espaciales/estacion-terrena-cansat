/*
 * ============================================================
 * ROCKET TELEMETRY SIMULATOR - HIGH-FIDELITY FLIGHT PROFILE
 * ============================================================
 *
 * Microcontroller:   Arduino Uno / Nano / Mega / ESP32 / RP2040
 * Baud Rate:         115200 baud, 8N1
 * Sample Rate:       5 Hz (nominal period 200 ms)
 * Total Cycle:       290 seconds (4 min 50 s, loops automatically)
 * Peak Altitude:     ~1850 m
 * Frame Size:        29 bytes binary
 *
 * SIMULATION TIMELINE & TEST PHASES:
 * 1. 000 - 120 s : STANDBY (0x00) - Pre-launch data variation (noise/sway, fluctuating RSSI & sats)
 * 2. 120 - 155 s : STANDBY (0x00) - Pre-launch normalization (calibrated baseline: 1.0g Z, 0g X/Y, steady RSSI & 12 sats)
 * 3. 155 - 161 s : POWERED (0x01) - Motor burn, 9.8g peak thrust.
 *                  * ALERT: Extreme Lateral G (ax=+9.7g, ay=-9.6g) at 157.0 - 158.5 s
 * 4. 161 - 180 s : BURNOUT (0x03) - Ballistic coast to apogee (~1850 m)
 *                  * ALERT: Packet loss (>15%) induced at 165.0 - 168.0 s
 * 5. 180.0 - 180.4s: APOGEE     (0x07) - Peak altitude reached (~1850 m)
 * 6. 180.4 - 180.8s: DROGUE_ORD (0x0F) - Pyro 1 command sent (Drogue deployment)
 * 7. 180.8 - 210.0s: DROGUE_CONF (0x1F) - Drogue confirmed deployed & descent (~48 m/s)
 *                  * ALERT: CRC errors (3 corrupted packets) at 184.0 - 184.6 s
 * 8. 210.0 - 210.4s: MAIN_ORD   (0x3F) - Pyro 2 command sent (Main deployment at ~450 m)
 * 9. 210.4 - 230.0s: MAIN_CONF (0x7F) - Main confirmed deployed, gentle descent (~5.5 m/s)
 * 10. 230 - 290 s : LANDED      (0xFF) - Touchdown on ground, held for 1 full minute (60 s)
 *
 * ============================================================
 * 29-BYTE BINARY FRAME FORMAT
 * ============================================================
 *
 * Byte 0       : Rocket ID (0x01)
 * Byte 1       : Frame Type / Header (0x01)
 * Bytes 2-3    : Frame Number [uint16 BE]
 * Bytes 4-7    : Timestamp [uint32 BE, ms]
 * Bytes 8-9    : Accel X [int16 BE, scale 0.001 g -> 1000 counts/g]
 * Bytes 10-11  : Accel Y [int16 BE, scale 0.001 g -> 1000 counts/g]
 * Bytes 12-13  : Accel Z [int16 BE, scale 0.0005 g -> 2000 counts/g]
 * Bytes 14-17  : Latitude [int32 BE, deg * 1e6]
 * Bytes 18-21  : Longitude [int32 BE, deg * 1e6]
 * Bytes 22-23  : Altitude [int16 BE, m]
 * Byte 24      : Status [0x00=STANDBY, 0x01=POWERED, 0x03=BURNOUT, 0x07=APOGEE,
 *                        0x0F=DROGUE_ORD, 0x1F=DROGUE_CONF, 0x3F=MAIN_ORD,
 *                        0x7F=MAIN_CONF, 0xFF=LANDED]
 * Byte 25      : RSSI [int8, signed dBm]
 * Byte 26      : Satellites [uint8, GNSS count]
 * Bytes 27-28  : CRC-16/CCITT-FALSE [uint16 BE, calculated over bytes 0..26]
 *
 * ============================================================
 */

#if defined(ARDUINO)
#include <Arduino.h>
#endif
#include <math.h>

#ifndef PI
#define PI 3.14159265358979323846f
#endif

// ------------------------------------------------------------
// HARDWARE & TIMING CONSTANTS
// ------------------------------------------------------------

const uint8_t ROCKET_ID = 0x01;
const uint8_t HEADER    = 0x01;

const uint32_t BAUD_RATE = 115200;

const uint16_t SAMPLE_RATE_HZ   = 5;
const uint32_t SAMPLE_PERIOD_MS = 1000UL / SAMPLE_RATE_HZ; // 200 ms

// Complete mission cycle duration (290 seconds = 4 min 50 s)
const uint32_t TOTAL_CYCLE_MS = 290000UL;

// Peak target altitude (meters)
const float APOGEE_ALTITUDE = 1850.0f;

// Earth standard gravity (m/s^2)
const float GRAVITY = 9.80665f;

// Conversion factors matching config/frame.yaml:
// accel_x: scale 0.001  -> 1000 counts / g
// accel_y: scale 0.001  -> 1000 counts / g
// accel_z: scale 0.0005 -> 2000 counts / g
const float ACCEL_XY_SCALE = 1000.0f;
const float ACCEL_Z_SCALE  = 2000.0f;

// Launchpad GPS origin coordinates (Buenos Aires test field)
const float BASE_LATITUDE  = -34.603722f;
const float BASE_LONGITUDE = -58.381592f;

// ------------------------------------------------------------
// FLIGHT STATE STRUCTURE
// ------------------------------------------------------------

struct FlightState
{
    float   altitude;        // meters
    float   velocity;        // m/s
    float   accelX_g;        // g
    float   accelY_g;        // g
    float   accelZ_g;        // g
    uint8_t statusCode;      // bit flags / phase code
    int8_t  rssi;            // dBm (-128..127)
    uint8_t satellites;      // GNSS satellite count
    float   downrangeDrift;  // 0.0 to 1.0 progress southeast
    bool    corruptCrc;      // true to inject CRC error for testing
};

// ------------------------------------------------------------
// GLOBAL RUNTIME STATE
// ------------------------------------------------------------

uint16_t frameNumber      = 0;
uint32_t missionStartTime = 0;
uint32_t lastSendTime     = 0;
uint8_t  crcErrorCount    = 0;

// ------------------------------------------------------------
// UTILITY FUNCTIONS: BIG ENDIAN PACKING
// ------------------------------------------------------------

void writeUint16BE(uint8_t *buf, uint8_t idx, uint16_t val)
{
    buf[idx]     = (uint8_t)((val >> 8) & 0xFF);
    buf[idx + 1] = (uint8_t)(val & 0xFF);
}

void writeInt16BE(uint8_t *buf, uint8_t idx, int16_t val)
{
    uint16_t v = (uint16_t)val;
    buf[idx]     = (uint8_t)((v >> 8) & 0xFF);
    buf[idx + 1] = (uint8_t)(v & 0xFF);
}

void writeUint32BE(uint8_t *buf, uint8_t idx, uint32_t val)
{
    buf[idx]     = (uint8_t)((val >> 24) & 0xFF);
    buf[idx + 1] = (uint8_t)((val >> 16) & 0xFF);
    buf[idx + 2] = (uint8_t)((val >> 8) & 0xFF);
    buf[idx + 3] = (uint8_t)(val & 0xFF);
}

void writeInt32BE(uint8_t *buf, uint8_t idx, int32_t val)
{
    uint32_t v = (uint32_t)val;
    buf[idx]     = (uint8_t)((v >> 24) & 0xFF);
    buf[idx + 1] = (uint8_t)((v >> 16) & 0xFF);
    buf[idx + 2] = (uint8_t)((v >> 8) & 0xFF);
    buf[idx + 3] = (uint8_t)(v & 0xFF);
}

// ------------------------------------------------------------
// CRC-16 / CCITT-FALSE
// Polynomial: 0x1021, Initial: 0xFFFF, Final XOR: 0x0000
// ------------------------------------------------------------

uint16_t crc16_ccitt(const uint8_t *data, uint8_t length)
{
    uint16_t crc = 0xFFFF;

    for (uint8_t i = 0; i < length; i++)
    {
        crc ^= ((uint16_t)data[i] << 8);

        for (uint8_t j = 0; j < 8; j++)
        {
            if (crc & 0x8000)
            {
                crc = (crc << 1) ^ 0x1021;
            }
            else
            {
                crc <<= 1;
            }
        }
    }

    return crc;
}

// ------------------------------------------------------------
// MATH HELPERS
// ------------------------------------------------------------

float lerp(float a, float b, float t)
{
    return a + (b - a) * t;
}

float smoothstep(float edge0, float edge1, float x)
{
    float t = (x - edge0) / (edge1 - edge0);
    if (t < 0.0f) t = 0.0f;
    if (t > 1.0f) t = 1.0f;
    return t * t * (3.0f - 2.0f * t);
}

float randomNoise(float amplitude)
{
    return (((float)random(-1000, 1001)) / 1000.0f) * amplitude;
}

// ------------------------------------------------------------
// HIGH-FIDELITY FLIGHT TRAJECTORY KINEMATICS
// ------------------------------------------------------------

FlightState calculateFlight(float t)
{
    FlightState s;
    s.altitude       = 0.0f;
    s.velocity       = 0.0f;
    s.accelX_g       = 0.0f;
    s.accelY_g       = 0.0f;
    s.accelZ_g       = 1.0f;
    s.statusCode     = 0x00; // STANDBY
    s.rssi           = -55;
    s.satellites     = 12;
    s.downrangeDrift = 0.0f;
    s.corruptCrc     = false;

    // ========================================================
    // PHASE 1: 0 - 120 s (PRE-LAUNCH DATA VARIATION)
    // Pad idle: sensor noise, slight sway, fluctuating RSSI & sats
    // ========================================================
    if (t < 120.0f)
    {
        s.statusCode     = 0x00; // STANDBY
        s.altitude       = 0.0f + randomNoise(0.25f);
        s.velocity       = 0.0f;
        s.accelX_g       = randomNoise(0.04f);
        s.accelY_g       = randomNoise(0.04f);
        s.accelZ_g       = 1.0f + randomNoise(0.03f);
        s.rssi           = (int8_t)(-60 + random(-5, 6)); // -55 to -65 dBm
        s.satellites     = (uint8_t)random(7, 11);        // 7 to 10 satellites
        s.downrangeDrift = 0.0f;
        return s;
    }

    // ========================================================
    // PHASE 2: 120 - 155 s (PRE-LAUNCH NORMALIZATION)
    // Calibrated baseline: steady 1.0g Z, 0g X/Y, steady -55 dBm, 12 sats
    // ========================================================
    if (t < 155.0f)
    {
        s.statusCode     = 0x00; // STANDBY
        s.altitude       = 0.0f;
        s.velocity       = 0.0f;
        s.accelX_g       = 0.0f;
        s.accelY_g       = 0.0f;
        s.accelZ_g       = 1.000f;
        s.rssi           = -55;
        s.satellites     = 12;
        s.downrangeDrift = 0.0f;
        return s;
    }

    // ========================================================
    // LIFTOFF DETECTED (t >= 155 s)
    // Time since liftoff: tau = t - 155.0 s
    // ========================================================
    float tau = t - 155.0f;

    // ========================================================
    // PHASE 3: 155 - 161 s (tau 0 to 6 s): POWERED FLIGHT
    // Motor ignition & burn (status 0x01)
    // Alert injection: Extreme lateral G (ax=+9.7g, ay=-9.6g) at 157.0 - 158.5 s
    // ========================================================
    if (t < 161.0f)
    {
        s.statusCode = 0x01; // POWERED
        s.rssi       = -58;
        s.satellites = 12;

        float p = tau / 6.0f; // 0.0 to 1.0
        // Altitude: 0 -> 350 m with quadratic acceleration curve
        s.altitude = 350.0f * (p * p);
        s.velocity = (700.0f / 6.0f) * p; // up to ~116 m/s

        // Vertical acceleration profile: climbs to 9.8g peak thrust
        if (p < 0.25f)
        {
            s.accelZ_g = lerp(2.2f, 9.8f, p / 0.25f);
        }
        else if (p < 0.85f)
        {
            s.accelZ_g = 9.8f + randomNoise(0.2f);
        }
        else
        {
            s.accelZ_g = lerp(9.8f, 3.5f, (p - 0.85f) / 0.15f);
        }

        // Lateral acceleration:
        // Inject extreme lateral G alert between t = 157.0 and 158.5 s (tau 2.0 to 3.5 s)
        if (t >= 157.0f && t <= 158.5f)
        {
            s.accelX_g = 9.7f;
            s.accelY_g = -9.6f;
        }
        else
        {
            s.accelX_g = randomNoise(0.18f);
            s.accelY_g = randomNoise(0.18f);
        }

        s.downrangeDrift = 0.08f * p;
        return s;
    }

    // ========================================================
    // PHASE 4: 161 - 180 s (tau 6 to 25 s): BURNOUT & COAST
    // Motor burnout, ballistic coast to apogee (~1850 m) (status 0x03)
    // Alert injection: Packet loss is handled in sendTelemetry() at 165 - 168 s
    // ========================================================
    if (t < 180.0f)
    {
        s.statusCode = 0x03; // BURNOUT (Bits 0|1 = 1|2 = 3)
        s.rssi       = (int8_t)(-60 - (int8_t)((t - 161.0f) * 0.4f)); // -60 to -68 dBm
        s.satellites = 12;

        float p = (t - 161.0f) / 19.0f; // 0.0 to 1.0
        // Coasting deceleration under aerodynamic drag + gravity
        float smoothP = smoothstep(0.0f, 1.0f, p);
        s.altitude = lerp(350.0f, APOGEE_ALTITUDE, smoothP);
        s.velocity = lerp(120.0f, 0.0f, p);

        // Coasting acceleration: drag + gravity
        s.accelZ_g = -1.05f + randomNoise(0.06f);
        s.accelX_g = randomNoise(0.08f);
        s.accelY_g = randomNoise(0.08f);

        s.downrangeDrift = lerp(0.08f, 0.40f, p);
        return s;
    }

    // ========================================================
    // PHASE 5: 180.0 - 180.4 s: APOGEE REACHED
    // Peak altitude (~1850 m), near-zero velocity (status 0x07)
    // ========================================================
    if (t < 180.4f)
    {
        s.statusCode     = 0x07; // APOGEE (Bits 0|1|2 = 7)
        s.altitude       = APOGEE_ALTITUDE;
        s.velocity       = 0.0f;
        s.accelX_g       = 0.02f;
        s.accelY_g       = -0.01f;
        s.accelZ_g       = 0.98f;
        s.rssi           = -68;
        s.satellites     = 12;
        s.downrangeDrift = 0.40f;
        return s;
    }

    // ========================================================
    // PHASE 6: 180.4 - 180.8 s: DROGUE_ORD
    // Pyro 1 firing signal sent (status 0x0F)
    // ========================================================
    if (t < 180.8f)
    {
        s.statusCode     = 0x0F; // DROGUE_ORD (Bits 0|1|2|3 = 15)
        s.altitude       = APOGEE_ALTITUDE - 2.0f;
        s.velocity       = -3.0f;
        s.accelX_g       = 0.15f;
        s.accelY_g       = -0.10f;
        s.accelZ_g       = 2.2f; // Ejection recoil shock
        s.rssi           = -68;
        s.satellites     = 12;
        s.downrangeDrift = 0.41f;
        return s;
    }

    // ========================================================
    // PHASE 7: 180.8 - 210.0 s: DROGUE_CONF & DROGUE DESCENT
    // Drogue deployed, fast descent ~48 m/s down to 450 m (status 0x1F)
    // Alert injection: CRC error corruption at 184.0 - 184.6 s
    // ========================================================
    if (t < 210.0f)
    {
        s.statusCode = 0x1F; // DROGUE_CONF (Bits 0|1|2|3|4 = 31)
        s.rssi       = (int8_t)(-68 + (int8_t)((t - 180.8f) * 0.2f)); // climbing back
        s.satellites = 12;

        float p = (t - 180.8f) / 29.2f; // 0.0 to 1.0
        // Altitude: 1848 m -> 450 m
        s.altitude = lerp(APOGEE_ALTITUDE - 2.0f, 450.0f, p);
        s.velocity = -47.8f;

        s.accelZ_g = 1.0f + 0.15f * sin(p * 20.0f); // Drogue oscillation
        s.accelX_g = 0.10f * cos(p * 15.0f);
        s.accelY_g = 0.10f * sin(p * 12.0f);

        s.downrangeDrift = lerp(0.41f, 0.78f, p);

        // Inject CRC corruption on packets around 184.0 to 184.6 s
        if (t >= 184.0f && t <= 184.6f)
        {
            s.corruptCrc = true;
        }

        return s;
    }

    // ========================================================
    // PHASE 8: 210.0 - 210.4 s: MAIN_ORD
    // Pyro 2 firing signal sent at ~450 m (status 0x3F)
    // ========================================================
    if (t < 210.4f)
    {
        s.statusCode     = 0x3F; // MAIN_ORD (Bits 0..5 = 63)
        s.altitude       = 450.0f;
        s.velocity       = -35.0f;
        s.accelX_g       = 0.35f;
        s.accelY_g       = -0.20f;
        s.accelZ_g       = 3.8f; // Main deployment shock
        s.rssi           = -63;
        s.satellites     = 12;
        s.downrangeDrift = 0.78f;
        return s;
    }

    // ========================================================
    // PHASE 9: 210.4 - 230.0 s: MAIN_CONF & GENTLE DESCENT
    // Main parachute open, gentle descent ~5.5 m/s to 0 m (status 0x7F)
    // ========================================================
    if (t < 230.0f)
    {
        s.statusCode = 0x7F; // MAIN_CONF (Bits 0..6 = 127)
        s.rssi       = (int8_t)(-63 + (int8_t)((t - 210.4f) * 0.4f)); // improves near ground
        s.satellites = 12;

        float p = (t - 210.4f) / 19.6f; // 0.0 to 1.0
        // Descent curve with gentle ground flare
        float smoothP = smoothstep(0.0f, 1.0f, p);
        s.altitude = lerp(450.0f, 0.0f, smoothP);
        s.velocity = lerp(-12.0f, -4.5f, p);

        s.accelZ_g = 1.0f + 0.06f * sin(p * 8.0f);
        s.accelX_g = 0.04f * sin(p * 6.0f);
        s.accelY_g = 0.04f * cos(p * 6.0f);

        s.downrangeDrift = lerp(0.78f, 1.0f, p);
        return s;
    }

    // ========================================================
    // PHASE 10: 230 - 290 s (60 SECONDS): LANDED ON GROUND
    // Touchdown confirmed, held for 1 full minute (status 0xFF)
    // ========================================================
    s.statusCode     = 0xFF; // LANDED (Bits 0..7 = 255)
    s.altitude       = 0.0f;
    s.velocity       = 0.0f;
    s.accelX_g       = 0.0f;
    s.accelY_g       = 0.0f;
    s.accelZ_g       = 1.000f;
    s.rssi           = -70; // On ground signal
    s.satellites     = 12;
    s.downrangeDrift = 1.0f;
    s.corruptCrc     = false;

    return s;
}

// ------------------------------------------------------------
// GENERATE & TRANSMIT TELEMETRY PACKET (29 BYTES)
// ------------------------------------------------------------

void sendTelemetry()
{
    uint32_t timestamp = millis() - missionStartTime;
    float t = timestamp / 1000.0f;

    // Run flight trajectory kinematics
    FlightState flight = calculateFlight(t);

    // ========================================================
    // IN-FLIGHT ALERT 2: PACKET LOSS INJECTION (165.0 - 168.0 s)
    // Simulate dropouts causing >15% loss in the 5-second window
    // ========================================================
    if (t >= 165.0f && t <= 168.0f)
    {
        // Advance frameNumber by 4 to create a sequence skip, and drop 3 of 4 frames
        if ((frameNumber % 4) != 0)
        {
            frameNumber += 2; // Sequence gap for ground station packet loss calculation
            return;           // Drop packet transmission
        }
    }

    // ========================================================
    // 29-BYTE FRAME BUILDER
    // ========================================================
    uint8_t packet[29];

    // Accelerometer raw scaling
    int16_t accelX = (int16_t)(flight.accelX_g * ACCEL_XY_SCALE);
    int16_t accelY = (int16_t)(flight.accelY_g * ACCEL_XY_SCALE);
    int16_t accelZ = (int16_t)(flight.accelZ_g * ACCEL_Z_SCALE);

    // Downrange ground track drift (~750 m southeast)
    float latDeg = BASE_LATITUDE  - (0.0032f * flight.downrangeDrift);
    float lonDeg = BASE_LONGITUDE + (0.0055f * flight.downrangeDrift);
    int32_t latRaw = (int32_t)(latDeg * 1000000.0f);
    int32_t lonRaw = (int32_t)(lonDeg * 1000000.0f);

    int16_t altRaw = (int16_t)round(flight.altitude);

    // Byte 0: Rocket ID (0x01)
    packet[0] = ROCKET_ID;

    // Byte 1: Header / Frame Type (0x01)
    packet[1] = HEADER;

    // Bytes 2-3: Frame Sequence Number
    writeUint16BE(packet, 2, frameNumber);

    // Bytes 4-7: Timestamp in ms
    writeUint32BE(packet, 4, timestamp);

    // Bytes 8-9: Accel X
    writeInt16BE(packet, 8, accelX);

    // Bytes 10-11: Accel Y
    writeInt16BE(packet, 10, accelY);

    // Bytes 12-13: Accel Z
    writeInt16BE(packet, 12, accelZ);

    // Bytes 14-17: Latitude (int32 BE)
    writeInt32BE(packet, 14, latRaw);

    // Bytes 18-21: Longitude (int32 BE)
    writeInt32BE(packet, 18, lonRaw);

    // Bytes 22-23: Altitude (int16 BE)
    writeInt16BE(packet, 22, altRaw);

    // Byte 24: Status (0x00..0xFF)
    packet[24] = flight.statusCode;

    // Byte 25: RSSI (int8 signed dBm)
    packet[25] = (int8_t)flight.rssi;

    // Byte 26: Satellites (uint8 GNSS count)
    packet[26] = (uint8_t)flight.satellites;

    // Bytes 27-28: CRC-16/CCITT-FALSE across bytes 0..26 (27 bytes)
    uint16_t crc = crc16_ccitt(packet, 27);

    // In-flight CRC error injection (corrupt 3 packets during drogue deployment)
    if (flight.corruptCrc && crcErrorCount < 3)
    {
        crc ^= 0xAAAA;
        crcErrorCount++;
    }

    writeUint16BE(packet, 27, crc);

    // Transmit 29-byte frame
    Serial.write(packet, 29);

    frameNumber++;
}

// ------------------------------------------------------------
// SETUP
// ------------------------------------------------------------

void setup()
{
    Serial.begin(BAUD_RATE);

    // Seed pseudo-random generator
    randomSeed(analogRead(A0));

    missionStartTime = millis();
    lastSendTime     = millis();
    frameNumber      = 0;
    crcErrorCount    = 0;
}

// ------------------------------------------------------------
// MAIN LOOP
// ------------------------------------------------------------

void loop()
{
    uint32_t now = millis();

    // Reset mission loop when complete cycle elapses (290 seconds)
    if ((now - missionStartTime) >= TOTAL_CYCLE_MS)
    {
        missionStartTime = now;
        frameNumber      = 0;
        crcErrorCount    = 0;
    }

    // Fixed 5 Hz transmission rate (200 ms interval)
    if ((now - lastSendTime) >= SAMPLE_PERIOD_MS)
    {
        lastSendTime = now;
        sendTelemetry();
    }
}
