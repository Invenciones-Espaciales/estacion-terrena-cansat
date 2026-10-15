/*
 * ============================================================
 * ROCKET TELEMETRY SIMULATOR - HIGH-FIDELITY FLIGHT PROFILE
 * DEFINITIVE 65-BYTE LORA TELEMETRY FRAME SPECIFICATION
 * ============================================================
 *
 * Microcontroller:   Arduino Uno / Nano / Mega / ESP32 / RP2040
 * Baud Rate:         115200 baud, 8N1
 * Sample Rate:       10 Hz (nominal period 100 ms)
 * Total Cycle:       290 seconds (4 min 50 s, loops automatically)
 * Peak Altitude:     ~1850 m
 * Frame Size:        65 bytes binary (LoRa Definitive)
 *
 * SIMULATION TIMELINE & TEST PHASES:
 * 1. 000 - 120 s : STANDBY (0x00) - Pre-launch data variation (pad sway, noise, fluctuating RSSI & sats)
 * 2. 120 - 155 s : STANDBY (0x00) - Pre-launch normalization (calibrated baseline: 1.0g Z, 0g X/Y, steady 12 sats)
 * 3. 155 - 161 s : POWERED (0x01) - Motor burn, 9.8g peak thrust, roll rate ~120 deg/s
 *                  * ALERT: Extreme Lateral G (ax=+9.7g, ay=-9.6g) at 157.0 - 158.5 s
 * 4. 161 - 180 s : BURNOUT (0x03) - Ballistic coast to apogee (~1850 m)
 *                  * ALERT: Packet loss (>15%) induced at 165.0 - 168.0 s
 * 5. 180.0 - 180.4s: APOGEE     (0x07) - Peak altitude reached (~1850 m), v=0 m/s
 * 6. 180.4 - 180.8s: DROGUE_ORD (0x0F) - Pyro pin 1 fired (Pin Frenado = 1)
 * 7. 180.8 - 210.0s: DROGUE_CONF (0x1F) - Drogue confirmed deployed, descent (~48 m/s)
 *                  * ALERT: CRC errors (3 corrupted packets) at 184.0 - 184.6 s
 * 8. 210.0 - 210.4s: MAIN_ORD   (0x3F) - Pyro pin 2 fired (Pin Principal = 1 at ~450 m)
 * 9. 210.4 - 230.0s: MAIN_CONF (0x7F) - Main confirmed deployed, gentle descent (~5.5 m/s)
 * 10. 230 - 290 s : LANDED      (0xFF) - Touchdown on ground, held for 1 full minute (60 s)
 *
 * ============================================================
 * 65-BYTE DEFINITIVE LORA BINARY FRAME FORMAT (LITTLE-ENDIAN)
 * ============================================================
 *
 * Header (7 bytes):
 *   Byte 0        : Sync Byte (0xAA)
 *   Bytes 1-2     : Frame Number [uint16 LE]
 *   Bytes 3-6     : Timestamp [uint32 LE, ms]
 *
 * Payload (56 bytes):
 *   Byte 7        : Status [uint8, 0x00..0xFF]
 *   Bytes 8-11    : Pressure [float32 LE, hPa from BMP280]
 *   Bytes 12-15   : Altura Actual [float32 LE, barometric meters]
 *   Bytes 16-19   : Accel X [float32 LE, g]
 *   Bytes 20-23   : Accel Y [float32 LE, g]
 *   Bytes 24-27   : Accel Z [float32 LE, g]
 *   Bytes 28-31   : Gyro X [float32 LE, deg/s]
 *   Bytes 32-35   : Gyro Y [float32 LE, deg/s]
 *   Bytes 36-39   : Gyro Z [float32 LE, deg/s]
 *   Bytes 40-43   : Temp IMU [float32 LE, °C]
 *   Bytes 44-47   : Latitude [float32 LE, decimal degrees]
 *   Bytes 48-51   : Longitude [float32 LE, decimal degrees]
 *   Bytes 52-55   : Altitud GPS [float32 LE, meters ASL]
 *   Byte 56       : Satellites [uint8, GPS count]
 *   Bytes 57-60   : Ground Speed [float32 LE, m/s]
 *   Byte 61       : Pin Frenado [uint8, 0/1]
 *   Byte 62       : Pin Principal [uint8, 0/1]
 *
 * Trailer (2 bytes):
 *   Bytes 63-64   : CRC-16/CCITT-FALSE [uint16 LE, over bytes 0..62]
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

const uint8_t SYNC_BYTE = 0xAA;
const uint32_t BAUD_RATE = 115200;

// LoRa 10 Hz transmission rate (100 ms period)
const uint16_t SAMPLE_RATE_HZ   = 10;
const uint32_t SAMPLE_PERIOD_MS = 1000UL / SAMPLE_RATE_HZ; // 100 ms

// Complete mission cycle duration (290 seconds = 4 min 50 s)
const uint32_t TOTAL_CYCLE_MS = 290000UL;

// Peak target altitude (meters)
const float APOGEE_ALTITUDE = 1850.0f;

// Standard gravity (m/s^2)
const float GRAVITY = 9.80665f;

// Launchpad GPS origin coordinates (Buenos Aires test field)
const float BASE_LATITUDE  = -34.603722f;
const float BASE_LONGITUDE = -58.381592f;
const float BASE_ALT_MSL   = 25.0f; // Ground elevation 25m above sea level

// ------------------------------------------------------------
// PACKED LORA TELEMETRY STRUCTURE (65 BYTES)
// ------------------------------------------------------------

struct __attribute__((packed)) LoRaPacket
{
    // Header (7 bytes)
    uint8_t  sync;           // 0xAA
    uint16_t frame_number;   // Packet sequence ID
    uint32_t timestamp;      // millis() since boot

    // Payload (56 bytes)
    uint8_t  status;         // Flight phase
    float    pressure;       // BMP280 barometric pressure (hPa)
    float    altura_actual;  // Calibrated relative altitude (m)
    float    accel_x;        // Linear acceleration X (g)
    float    accel_y;        // Linear acceleration Y (g)
    float    accel_z;        // Linear acceleration Z (g)
    float    gyro_x;         // Angular rate X (deg/s)
    float    gyro_y;         // Angular rate Y (deg/s)
    float    gyro_z;         // Angular rate Z (deg/s)
    float    temp_imu;       // IMU die temperature (°C)
    float    latitude;       // GPS latitude (decimal degrees)
    float    longitude;      // GPS longitude (decimal degrees)
    float    altitud_gps;    // GPS altitude ASL (m)
    uint8_t  satellites;     // Satellite count
    float    ground_speed;   // GPS ground speed (m/s)
    uint8_t  pin_frenado;    // 0: OFF, 1: ACTIVE
    uint8_t  pin_principal;  // 0: OFF, 1: ACTIVE

    // Trailer (2 bytes)
    uint16_t crc;            // CRC-16/CCITT-FALSE
};

// ------------------------------------------------------------
// FLIGHT STATE STRUCTURE
// ------------------------------------------------------------

struct FlightState
{
    float   altitude;        // meters relative
    float   velocity;        // m/s vertical
    float   accelX_g;        // g
    float   accelY_g;        // g
    float   accelZ_g;        // g
    float   gyroX_dps;       // deg/s
    float   gyroY_dps;       // deg/s
    float   gyroZ_dps;       // deg/s
    float   tempImu_c;       // °C
    float   pressure_hpa;    // hPa
    float   groundSpeed_ms;  // m/s
    uint8_t statusCode;      // bit flags / phase code
    int8_t  rssi;            // dBm (-128..127)
    uint8_t satellites;      // GPS satellite count
    uint8_t pinFrenado;      // 0 or 1
    uint8_t pinPrincipal;    // 0 or 1
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
// CRC-16/CCITT-FALSE CALCULATION
// ------------------------------------------------------------

uint16_t crc16_ccitt(const uint8_t *data, size_t length)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++)
    {
        crc ^= ((uint16_t)data[i]) << 8;
        for (uint8_t bit = 0; bit < 8; bit++)
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
// MATHEMATICAL INTERPOLATION HELPERS
// ------------------------------------------------------------

float lerp(float a, float b, float t)
{
    return a + t * (b - a);
}

float smoothstep(float edge0, float edge1, float x)
{
    float t = (x - edge0) / (edge1 - edge0);
    if (t < 0.0f) t = 0.0f;
    if (t > 1.0f) t = 1.0f;
    return t * t * (3.0f - 2.0f * t);
}

float randomFloat(float minVal, float maxVal)
{
    return minVal + ((float)rand() / (float)RAND_MAX) * (maxVal - minVal);
}

// Barometric pressure formula for standard atmosphere
float altitudeToPressure(float altMeters)
{
    const float p0 = 1013.25f;
    return p0 * powf(1.0f - (2.25577e-5f * altMeters), 5.25588f);
}

// ------------------------------------------------------------
// MISSION PROFILE SIMULATOR KINEMATICS
// ------------------------------------------------------------

FlightState calculateFlight(float t)
{
    FlightState s;
    s.altitude       = 0.0f;
    s.velocity       = 0.0f;
    s.accelX_g       = 0.0f;
    s.accelY_g       = 0.0f;
    s.accelZ_g       = 1.000f; // Earth 1G nominal
    s.gyroX_dps      = 0.0f;
    s.gyroY_dps      = 0.0f;
    s.gyroZ_dps      = 0.0f;
    s.tempImu_c      = 28.5f;
    s.groundSpeed_ms = 0.0f;
    s.statusCode     = 0x00;   // STANDBY
    s.rssi           = -55;
    s.satellites     = 12;
    s.pinFrenado     = 0;
    s.pinPrincipal   = 0;
    s.downrangeDrift = 0.0f;
    s.corruptCrc     = false;

    // Wrap simulation cycle at 290 seconds
    if (t >= 290.0f)
    {
        missionStartTime = millis();
        t = 0.0f;
    }

    // ========================================================
    // PHASE 1: 000 - 120 s (2 MINUTES): PRE-LAUNCH DATA VARIATION
    // ========================================================
    if (t < 120.0f)
    {
        s.statusCode = 0x00; // STANDBY
        s.altitude   = randomFloat(-0.8f, 1.2f);
        s.velocity   = 0.0f;

        // Realistic launchpad wind sway / g-jitter
        float swayAngle = t * 0.4f;
        s.accelX_g = 0.06f * sin(swayAngle) + randomFloat(-0.03f, 0.03f);
        s.accelY_g = 0.05f * cos(swayAngle * 0.8f) + randomFloat(-0.03f, 0.03f);
        s.accelZ_g = 1.000f + randomFloat(-0.02f, 0.02f);

        s.gyroX_dps = 0.15f * sin(t);
        s.gyroY_dps = 0.12f * cos(t * 0.9f);
        s.gyroZ_dps = 0.05f * sin(t * 0.5f);
        s.tempImu_c = 28.0f + 0.5f * sin(t * 0.05f);

        s.rssi       = (int8_t)(-60 + (int8_t)(5.0f * sin(t * 0.2f)));
        s.satellites = (uint8_t)(8 + (int)(2.0f * sin(t * 0.1f)));
        s.downrangeDrift = 0.0f;
        s.pressure_hpa = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 2: 120 - 155 s (35 SECONDS): PRE-LAUNCH NORMALIZATION
    // Calibrated baseline
    // ========================================================
    if (t < 155.0f)
    {
        s.statusCode     = 0x00; // STANDBY
        s.altitude       = 0.0f;
        s.velocity       = 0.0f;
        s.accelX_g       = 0.000f;
        s.accelY_g       = 0.000f;
        s.accelZ_g       = 1.000f; // Exactly 1.000 g
        s.gyroX_dps      = 0.0f;
        s.gyroY_dps      = 0.0f;
        s.gyroZ_dps      = 0.0f;
        s.tempImu_c      = 28.5f;
        s.rssi           = -55;    // Constant strong signal
        s.satellites     = 12;     // Constant 12 sats
        s.downrangeDrift = 0.0f;
        s.pressure_hpa   = altitudeToPressure(0.0f);
        return s;
    }

    // ========================================================
    // PHASE 3: 155 - 161 s (6 SECONDS): POWERED BOOST FLIGHT
    // Motor burn: peak thrust 9.8g
    // ========================================================
    if (t < 161.0f)
    {
        s.statusCode = 0x01; // POWERED (Bit 0 = 1)
        float burnTime = t - 155.0f; // 0.0 to 6.0 s
        float burnProgress = burnTime / 6.0f;

        float thrustCurve = sin(burnProgress * PI);
        s.accelZ_g = 1.0f + (8.8f * thrustCurve); // 1.0g baseline + 8.8g thrust = 9.8g peak
        s.tempImu_c = 28.5f + (burnTime * 0.8f);   // Warming up to 33.3°C

        // IN-FLIGHT ALERT 1: Extreme Lateral G (157.0 - 158.5 s)
        if (t >= 157.0f && t <= 158.5f)
        {
            s.accelX_g = 9.70f;
            s.accelY_g = -9.60f;
            s.gyroX_dps = 45.0f;
            s.gyroY_dps = -40.0f;
        }
        else
        {
            s.accelX_g = 0.25f * sin(burnTime * 4.0f);
            s.accelY_g = 0.20f * cos(burnTime * 4.0f);
            s.gyroX_dps = 2.5f * sin(burnTime * 2.0f);
            s.gyroY_dps = 2.0f * cos(burnTime * 2.0f);
        }

        // Longitudinal roll rate spin stabilization
        s.gyroZ_dps = 120.0f * burnProgress;

        // Kinematic integration
        s.velocity = 195.0f * powf(burnProgress, 1.4f);
        s.altitude = 480.0f * powf(burnProgress, 2.2f);
        s.groundSpeed_ms = 15.0f * burnProgress;

        s.rssi       = (int8_t)(-58 - (int8_t)(burnProgress * 8.0f));
        s.satellites = 12;
        s.downrangeDrift = 0.08f * burnProgress;
        s.pressure_hpa   = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 4: 161 - 180 s (19 SECONDS): UNPOWERED COAST (BURNOUT)
    // Ballistic ascent to apogee
    // ========================================================
    if (t < 180.0f)
    {
        s.statusCode = 0x03; // BURNOUT (Bits 0..1 = 3)
        float coastTime = t - 161.0f; // 0.0 to 19.0 s
        float coastProgress = coastTime / 19.0f;

        s.accelZ_g = lerp(-1.05f, -0.98f, coastProgress);
        s.accelX_g = 0.08f * sin(coastTime * 1.5f);
        s.accelY_g = 0.06f * cos(coastTime * 1.5f);

        s.gyroX_dps = 1.2f * sin(coastTime);
        s.gyroY_dps = 1.0f * cos(coastTime);
        s.gyroZ_dps = lerp(120.0f, 15.0f, coastProgress); // Spin decay
        s.tempImu_c = lerp(33.3f, 31.0f, coastProgress);

        s.velocity = lerp(195.0f, 0.0f, coastProgress);
        float p = smoothstep(0.0f, 1.0f, coastProgress);
        s.altitude = lerp(480.0f, APOGEE_ALTITUDE, p);
        s.groundSpeed_ms = lerp(15.0f, 8.0f, coastProgress);

        s.rssi       = (int8_t)(-66 - (int8_t)(coastProgress * 6.0f));
        s.satellites = 12;
        s.downrangeDrift = lerp(0.08f, 0.45f, p);
        s.pressure_hpa   = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 5: 180.0 - 180.4 s (400 ms): APOGEE
    // ========================================================
    if (t < 180.4f)
    {
        s.statusCode = 0x07; // APOGEE (Bits 0..2 = 7)
        s.altitude   = APOGEE_ALTITUDE;
        s.velocity   = 0.0f;
        s.accelZ_g   = 0.00f; // Free fall / 0G moment at apogee
        s.accelX_g   = 0.02f;
        s.accelY_g   = 0.02f;
        s.gyroX_dps  = 0.5f;
        s.gyroY_dps  = 0.5f;
        s.gyroZ_dps  = 5.0f;
        s.tempImu_c  = 30.5f;
        s.groundSpeed_ms = 7.5f;
        s.rssi       = -72;
        s.satellites = 12;
        s.downrangeDrift = 0.46f;
        s.pressure_hpa   = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 6: 180.4 - 180.8 s (400 ms): DROGUE EJECTION COMMAND
    // Pin Frenado Activated!
    // ========================================================
    if (t < 180.8f)
    {
        s.statusCode = 0x0F; // DROGUE_ORD (Bits 0..3 = 15)
        s.altitude   = APOGEE_ALTITUDE - 2.0f;
        s.velocity   = -4.0f;
        s.accelZ_g   = -0.85f;
        s.accelX_g   = 0.40f; // Ejection shockwave
        s.accelY_g   = 0.35f;
        s.gyroX_dps  = 15.0f;
        s.gyroY_dps  = -12.0f;
        s.gyroZ_dps  = 20.0f;
        s.tempImu_c  = 30.5f;
        s.pinFrenado = 1;     // ACTIVATED
        s.groundSpeed_ms = 8.0f;
        s.rssi       = -72;
        s.satellites = 12;
        s.downrangeDrift = 0.47f;
        s.pressure_hpa   = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 7: 180.8 - 210.0 s (29.2 s): DROGUE DESCENT
    // High-speed stabilized descent (~48 m/s) down to 450m
    // ========================================================
    if (t < 210.0f)
    {
        s.statusCode = 0x1F; // DROGUE_CONF (Bits 0..4 = 31)
        s.pinFrenado = 1;     // Maintained active/deployed
        float dTime = t - 180.8f;
        float dProgress = dTime / 29.2f;

        s.altitude = lerp(APOGEE_ALTITUDE - 2.0f, 450.0f, dProgress);
        s.velocity = -48.0f;

        s.accelZ_g = 1.0f + 0.15f * sin(dTime * 3.0f);
        s.accelX_g = 0.12f * sin(dTime * 2.5f);
        s.accelY_g = 0.12f * cos(dTime * 2.5f);

        s.gyroX_dps = 4.0f * sin(dTime * 1.5f);
        s.gyroY_dps = 3.5f * cos(dTime * 1.5f);
        s.gyroZ_dps = 8.0f * sin(dTime * 0.5f);
        s.tempImu_c = lerp(30.5f, 29.2f, dProgress);

        s.rssi       = (int8_t)(-72 + (int8_t)(dProgress * 6.0f));
        s.satellites = 12;
        s.downrangeDrift = lerp(0.47f, 0.75f, dProgress);
        s.groundSpeed_ms = 12.0f;

        // IN-FLIGHT ALERT 3: CRC Error Injection (184.0 - 184.6 s)
        if (t >= 184.0f && t <= 184.6f)
        {
            s.corruptCrc = true;
        }

        s.pressure_hpa = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 8: 210.0 - 210.4 s (400 ms): MAIN CHUTE COMMAND
    // Pin Principal Activated!
    // ========================================================
    if (t < 210.4f)
    {
        s.statusCode   = 0x3F; // MAIN_ORD (Bits 0..5 = 63)
        s.pinFrenado   = 1;
        s.pinPrincipal = 1;    // ACTIVATED
        s.altitude     = 450.0f;
        s.velocity     = -45.0f;
        s.accelZ_g     = 3.2f; // Main canopy snatch load shock
        s.accelX_g     = 0.60f;
        s.accelY_g     = 0.55f;
        s.gyroX_dps    = 18.0f;
        s.gyroY_dps    = 16.0f;
        s.gyroZ_dps    = -10.0f;
        s.tempImu_c    = 29.0f;
        s.groundSpeed_ms = 10.0f;
        s.rssi         = -65;
        s.satellites   = 12;
        s.downrangeDrift = 0.76f;
        s.pressure_hpa = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 9: 210.4 - 230.0 s (19.6 s): MAIN CHUTE DESCENT
    // Gentle canopy glide (~5.5 m/s) to touchdown
    // ========================================================
    if (t < 230.0f)
    {
        s.statusCode   = 0x7F; // MAIN_CONF (Bits 0..6 = 127)
        s.pinFrenado   = 1;
        s.pinPrincipal = 1;
        float p = (t - 210.4f) / 19.6f; // 0.0 to 1.0

        float smoothP = smoothstep(0.0f, 1.0f, p);
        s.altitude = lerp(450.0f, 0.0f, smoothP);
        s.velocity = lerp(-12.0f, -4.5f, p);

        s.accelZ_g = 1.0f + 0.06f * sin(p * 8.0f);
        s.accelX_g = 0.04f * sin(p * 6.0f);
        s.accelY_g = 0.04f * cos(p * 6.0f);

        s.gyroX_dps = 1.5f * sin(p * 5.0f);
        s.gyroY_dps = 1.2f * cos(p * 5.0f);
        s.gyroZ_dps = 0.5f;
        s.tempImu_c = lerp(29.0f, 28.5f, p);

        s.rssi       = (int8_t)(-63 + (int8_t)(p * 8.0f));
        s.satellites = 12;
        s.groundSpeed_ms = lerp(10.0f, 3.2f, p);
        s.downrangeDrift = lerp(0.78f, 1.0f, p);
        s.pressure_hpa = altitudeToPressure(s.altitude);
        return s;
    }

    // ========================================================
    // PHASE 10: 230 - 290 s (60 SECONDS): LANDED ON GROUND
    // Touchdown confirmed, held for 1 full minute (status 0xFF)
    // ========================================================
    s.statusCode     = 0xFF; // LANDED (Bits 0..7 = 255)
    s.pinFrenado     = 1;
    s.pinPrincipal   = 1;
    s.altitude       = 0.0f;
    s.velocity       = 0.0f;
    s.accelX_g       = 0.0f;
    s.accelY_g       = 0.0f;
    s.accelZ_g       = 1.000f;
    s.gyroX_dps      = 0.0f;
    s.gyroY_dps      = 0.0f;
    s.gyroZ_dps      = 0.0f;
    s.tempImu_c      = 28.5f;
    s.pressure_hpa   = altitudeToPressure(0.0f);
    s.groundSpeed_ms = 0.0f;
    s.rssi           = -70; // On ground RF beacon
    s.satellites     = 12;
    s.downrangeDrift = 1.0f;
    s.corruptCrc     = false;

    return s;
}

// ------------------------------------------------------------
// GENERATE & TRANSMIT TELEMETRY PACKET (65 BYTES)
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
    // 65-BYTE DEFINITIVE LORA PACKET BUILDER
    // ========================================================
    LoRaPacket packet;

    // Header
    packet.sync         = SYNC_BYTE;
    packet.frame_number = frameNumber;
    packet.timestamp    = timestamp;

    // Payload
    packet.status        = flight.statusCode;
    packet.pressure      = flight.pressure_hpa;
    packet.altura_actual = flight.altitude;
    packet.accel_x       = flight.accelX_g;
    packet.accel_y       = flight.accelY_g;
    packet.accel_z       = flight.accelZ_g;
    packet.gyro_x        = flight.gyroX_dps;
    packet.gyro_y        = flight.gyroY_dps;
    packet.gyro_z        = flight.gyroZ_dps;
    packet.temp_imu      = flight.tempImu_c;

    // GPS Geodetic Position & Drift (~750m southeast)
    packet.latitude      = BASE_LATITUDE  - (0.0032f * flight.downrangeDrift);
    packet.longitude     = BASE_LONGITUDE + (0.0055f * flight.downrangeDrift);
    packet.altitud_gps   = flight.altitude + BASE_ALT_MSL;
    packet.satellites    = flight.satellites;
    packet.ground_speed  = flight.groundSpeed_ms;

    // Pyrotechnic recovery pins
    packet.pin_frenado   = flight.pinFrenado;
    packet.pin_principal = flight.pinPrincipal;

    // Trailer: CRC-16/CCITT-FALSE across bytes 0..62 (63 bytes)
    uint16_t crc = crc16_ccitt((const uint8_t*)&packet, 63);

    // In-flight CRC error injection (corrupt 3 packets during drogue deployment)
    if (flight.corruptCrc && crcErrorCount < 3)
    {
        crc ^= 0xAAAA;
        crcErrorCount++;
    }

    packet.crc = crc;

    // Transmit 65-byte frame over UART / Serial
    Serial.write((const uint8_t*)&packet, sizeof(packet));

    frameNumber++;
}

// ------------------------------------------------------------
// SETUP
// ------------------------------------------------------------

void setup()
{
    Serial.begin(BAUD_RATE);
    while (!Serial && millis() < 3000)
    {
        ; // Wait for serial port connection
    }

    srand(12345);
    missionStartTime = millis();
    lastSendTime = millis();
}

// ------------------------------------------------------------
// MAIN LOOP: 10 HZ TRANSMISSION
// ------------------------------------------------------------

void loop()
{
    uint32_t now = millis();

    if (now - lastSendTime >= SAMPLE_PERIOD_MS)
    {
        lastSendTime = now;
        sendTelemetry();
    }
}
