/*
 * ============================================================
 * ROCKET TELEMETRY SIMULATOR - HIGH-FIDELITY MISSION PROFILE
 * ============================================================
 *
 * Microcontroller:   Arduino Uno / Nano / Mega / ESP32 / RP2040 / STM32
 * Baud Rate:         115200 baud
 * Sample Rate:       5 Hz (nominal period 200 ms)
 * Total Mission MET: 95 seconds (loops automatically)
 * Apogee Altitude:   ~1850 m
 * Serial:            115200 baud, 8N1
 *
 * MISSION PHASES & STATUS STATES:
 * 1. 00 - 10 s: STANDBY     (0x00) - Launchpad pre-launch baseline
 * 2. 10 - 16 s: POWERED     (0x01) - Motor ignition & burn (9.8g peak thrust)
 * 3. 16 - 35 s: BURNOUT     (0x03) - Motor burnout & ballistic coast to apogee
 * 4. 35 - 35.3s: APOGEE     (0x07) - Peak altitude reached (~1850m)
 * 5. 35.3 - 35.7s: DROGUE_ORD (0x0F) - Pyro 1 command sent (Drogue ejection charge)
 * 6. 35.7 - 65 s: DROGUE_CONF (0x1F) - Drogue parachute confirmed deployed & descent
 * 7. 65 - 65.4s: MAIN_ORD   (0x3F) - Pyro 2 command sent (Main parachute deployment)
 * 8. 65.4 - 85 s: MAIN_CONF (0x7F) - Main parachute confirmed open & terminal glide
 * 9. 85 - 95 s: LANDED      (0xFF) - Touchdown confirmed on ground, recovery beacon
 *
 * ============================================================
 * FRAME FORMAT (Ground Station Standard - 30 Bytes)
 * ============================================================
 *
 * Byte 0       : Rocket ID (0x01)
 * Byte 1       : Frame Type / Header (0x01)
 * Bytes 2-3    : Frame Number [uint16 BE]
 * Bytes 4-7    : Timestamp [uint32 BE, ms]
 * Bytes 8-9    : Accel X [int16 BE, scale 0.001 g -> 1000 counts/g]
 * Bytes 10-11  : Accel Y [int16 BE, scale 0.001 g -> 1000 counts/g]
 * Bytes 12-13  : Accel Z [int16 BE, scale 0.0005 g -> 2000 counts/g]
 * Bytes 14-16  : Pressure [uint24 BE, Pa]
 * Bytes 17-20  : Latitude [int32 BE, deg * 1e6]
 * Bytes 21-24  : Longitude [int32 BE, deg * 1e6]
 * Bytes 25-26  : Altitude [int16 BE, m]
 * Byte 27      : Flight Status [0x00..0x05]
 * Bytes 28-29  : CRC-16/CCITT-FALSE [uint16 BE, over bytes 0..27]
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
// PROTOCOL & TEST CONFIGURATION
// ------------------------------------------------------------

// Set to 1 to transmit 30-byte frames (100% compatible with Ground Station).
// Set to 0 to transmit 22-byte legacy frames.
#ifndef USE_GROUND_STATION_30BYTE_FRAME
#define USE_GROUND_STATION_30BYTE_FRAME 1
#endif

// Set to 1 to simulate RF link dropouts / packet loss to test dashboard loss badges
#ifndef SIMULATE_RF_PACKET_LOSS
#define SIMULATE_RF_PACKET_LOSS 0
#endif

// ------------------------------------------------------------
// HARDWARE CONSTANTS
// ------------------------------------------------------------

const uint8_t ROCKET_ID = 0x01;
const uint8_t HEADER    = 0x01;

const uint32_t BAUD_RATE = 115200;

const uint16_t SAMPLE_RATE_HZ = 5;
const uint32_t SAMPLE_PERIOD_MS = 1000UL / SAMPLE_RATE_HZ; // 200 ms

// Complete mission cycle duration in milliseconds (95 seconds)
const uint32_t MISSION_DURATION_MS = 95000UL;

// Peak target altitude (meters)
const float APOGEE_ALTITUDE = 1850.0f;

// Earth standard gravity (m/s^2)
const float GRAVITY = 9.80665f;

#if USE_GROUND_STATION_30BYTE_FRAME
// Conversion factors matching config/frame.yaml:
// accel_x: scale 0.001  -> 1000 counts / g
// accel_y: scale 0.001  -> 1000 counts / g
// accel_z: scale 0.0005 -> 2000 counts / g
const float ACCEL_XY_SCALE = 1000.0f;
const float ACCEL_Z_SCALE  = 2000.0f;

// Launchpad GPS origin coordinates (Buenos Aires launch test site)
const float BASE_LATITUDE  = -34.603722f;
const float BASE_LONGITUDE = -58.381592f;
#else
// Simulated MPU6050 raw sensitivity (+/-2g -> 16384 counts/g)
const float MPU_SCALE = 16384.0f;
#endif

// ------------------------------------------------------------
// FLIGHT COMPUTER STATUS BITFLAGS (Byte 27)
// ------------------------------------------------------------
// Bit 0 (1)   : POWERED     - Motor encendido / Despegue detectado
// Bit 1 (2)   : BURNOUT     - Fin de empuje del motor
// Bit 2 (4)   : APOGEE      - Apogeo alcanzado (altura maxima)
// Bit 3 (8)   : DROGUE_ORD  - Orden enviada: Disparo de Pirotecnico 1 (Drogue)
// Bit 4 (16)  : DROGUE_CONF - Confirmado: Pirotecnico 1 efectivamente se activo
// Bit 5 (32)  : MAIN_ORD    - Orden enviada: Disparo de Pirotecnico 2 (Principal)
// Bit 6 (64)  : MAIN_CONF   : Confirmado: Pirotecnico 2 efectivamente se activo
// Bit 7 (128) : LANDED      - Aterrizaje confirmado en tierra

const uint8_t STATUS_BIT_POWERED     = (1 << 0); // 1
const uint8_t STATUS_BIT_BURNOUT     = (1 << 1); // 2
const uint8_t STATUS_BIT_APOGEE      = (1 << 2); // 4
const uint8_t STATUS_BIT_DROGUE_ORD  = (1 << 3); // 8
const uint8_t STATUS_BIT_DROGUE_CONF = (1 << 4); // 16
const uint8_t STATUS_BIT_MAIN_ORD    = (1 << 5); // 32
const uint8_t STATUS_BIT_MAIN_CONF   = (1 << 6); // 64
const uint8_t STATUS_BIT_LANDED      = (1 << 7); // 128

// ------------------------------------------------------------
// FLIGHT STATE DATA STRUCTURE
// ------------------------------------------------------------

struct FlightState {
    float altitude;       // Meters
    float accelX_g;       // G-force
    float accelY_g;       // G-force
    float accelZ_g;       // G-force
    float downrangeDrift; // Normalized 0.0 -> 1.0
    uint8_t statusCode;   // 0x00 to 0x05
};

// ------------------------------------------------------------
// STATE VARIABLES
// ------------------------------------------------------------

uint16_t frameNumber = 0;
uint32_t missionStartTime = 0;
uint32_t lastSendTime = 0;

// ------------------------------------------------------------
// BIG-ENDIAN BUFFER SERIALIZATION
// ------------------------------------------------------------

void writeUint16BE(uint8_t *buffer, uint8_t index, uint16_t value)
{
    buffer[index]     = (value >> 8) & 0xFF;
    buffer[index + 1] = value & 0xFF;
}

void writeInt16BE(uint8_t *buffer, uint8_t index, int16_t value)
{
    uint16_t v = (uint16_t)value;
    buffer[index]     = (v >> 8) & 0xFF;
    buffer[index + 1] = v & 0xFF;
}

void writeUint24BE(uint8_t *buffer, uint8_t index, uint32_t value)
{
    buffer[index]     = (value >> 16) & 0xFF;
    buffer[index + 1] = (value >> 8) & 0xFF;
    buffer[index + 2] = value & 0xFF;
}

void writeUint32BE(uint8_t *buffer, uint8_t index, uint32_t value)
{
    buffer[index]     = (value >> 24) & 0xFF;
    buffer[index + 1] = (value >> 16) & 0xFF;
    buffer[index + 2] = (value >> 8) & 0xFF;
    buffer[index + 3] = value & 0xFF;
}

void writeInt32BE(uint8_t *buffer, uint8_t index, int32_t value)
{
    uint32_t v = (uint32_t)value;
    buffer[index]     = (v >> 24) & 0xFF;
    buffer[index + 1] = (v >> 16) & 0xFF;
    buffer[index + 2] = (v >> 8) & 0xFF;
    buffer[index + 3] = v & 0xFF;
}

// ------------------------------------------------------------
// CRC-16 / CCITT-FALSE
// ------------------------------------------------------------
// Polynomial: 0x1021, Initial Value: 0xFFFF, Final XOR: 0x0000
// Standard check vector: "123456789" -> 0x29B1
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
// PSEUDO-RANDOM SENSOR NOISE
// ------------------------------------------------------------

float noiseValue(float amplitude)
{
    return ((float)random(-1000, 1001) / 1000.0f) * amplitude;
}

// ------------------------------------------------------------
// COMPREHENSIVE FLIGHT TRAJECTORY ENGINE
// ------------------------------------------------------------
// Computes altitude, accelerations, flight state, and GPS drift
// for any given mission elapsed time (seconds).
// ------------------------------------------------------------


FlightState calculateFlight(float t)
{
    FlightState s;

    // --------------------------------------------------------
    // PHASE 0: STANDBY (0 - 5 s)
    // Rocket standing upright on launch pad, engine cold.
    // --------------------------------------------------------
    if (t < 5.0f)
    {
        s.altitude = 0.0f;
        s.accelX_g = noiseValue(0.005f);
        s.accelY_g = noiseValue(0.005f);
        s.accelZ_g = 1.0f + noiseValue(0.005f); // Resting 1g against gravity
        s.downrangeDrift = 0.0f;
        s.statusCode = 0x00; // Pad Standby (no flags set)
        return s;
    }

    // --------------------------------------------------------
    // PHASE 1: PRE-LAUNCH COUNTDOWN (5 - 10 s)
    // Vehicle armed, countdown T-5 to T-0, sensor baseline checks.
    // --------------------------------------------------------
    if (t < 10.0f)
    {
        s.altitude = 0.0f;
        // Minor pre-launch pad acoustic flutter
        s.accelX_g = 0.01f * sin(t * 12.0f) + noiseValue(0.008f);
        s.accelY_g = 0.01f * cos(t * 10.0f) + noiseValue(0.008f);
        s.accelZ_g = 1.0f + noiseValue(0.008f);
        s.downrangeDrift = 0.0f;
        s.statusCode = 0x00; // Standby / Armed
        return s;
    }

    // --------------------------------------------------------
    // PHASE 2: MOTOR IGNITION & POWERED BOOST (10 - 16 s)
    // Solid rocket motor fires. Peak thrust hits 9.8g at t=10.8s
    // Bit 0: STATUS_BIT_POWERED (1)
    // --------------------------------------------------------
    if (t < 16.0f)
    {
        float tau = t - 10.0f; // 0 to 6 seconds into burn
        float p = tau / 6.0f;

        // Thrust acceleration profile
        if (tau < 0.8f)
        {
            // Rapid ignition transient ramp up to 9.8g
            s.accelZ_g = 1.0f + 8.8f * (tau / 0.8f);
        }
        else
        {
            // Sustained thrust tapering slightly as propellant burns down
            s.accelZ_g = 9.8f - 4.5f * ((tau - 0.8f) / 5.2f);
        }

        // Intense acoustic motor vibrations on transverse axes
        s.accelX_g = 0.25f * sin(tau * 25.0f) + noiseValue(0.05f);
        s.accelY_g = 0.25f * cos(tau * 20.0f) + noiseValue(0.05f);
        s.accelZ_g += noiseValue(0.08f);

        // Quadratic altitude climb during constant acceleration: ~450 m at burnout
        s.altitude = 450.0f * (p * p);
        s.downrangeDrift = 0.15f * p;
        s.statusCode = STATUS_BIT_POWERED; // Bit 0 (1)
        return s;
    }

    // --------------------------------------------------------
    // PHASE 3: BALLISTIC COAST TO APOGEE (16 - 35 s)
    // Engine burnout. Sensed acceleration drops to -1.0g (free-fall).
    // Kinetic energy carries the rocket from 450 m to 1850 m.
    // Bit 0: POWERED | Bit 1: BURNOUT (1 | 2 = 3)
    // --------------------------------------------------------
    if (t < 35.0f)
    {
        float tau = (t - 16.0f) / 19.0f; // 0 to 1 over 19 seconds

        // Decelerating ascent curve smoothly arriving at peak
        s.altitude = 450.0f + (APOGEE_ALTITUDE - 450.0f) * (1.0f - (1.0f - tau) * (1.0f - tau));

        // In free-fall ballistic flight, proper acceleration is -1g
        s.accelZ_g = -1.0f + noiseValue(0.02f);

        // Aerodynamic buffeting & slow fin-induced roll
        s.accelX_g = 0.05f * sin(t * 3.0f) + noiseValue(0.01f);
        s.accelY_g = 0.05f * cos(t * 3.0f) + noiseValue(0.01f);

        s.downrangeDrift = 0.15f + 0.45f * tau;
        s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT; // Bits 0,1 (3)
        return s;
    }

    // --------------------------------------------------------
    // PHASE 4: APOGEE & SEPARATION (35 - 38 s)
    // Velocity crosses 0 m/s at ~1850 m.
    // t < 35.3s: Bit 2 (APOGEE = 4)
    // t 35.3 - 35.7s: Bit 3 (DROGUE_ORD = 8)
    // t >= 35.7s: Bit 4 (DROGUE_CONF = 16)
    // --------------------------------------------------------
    if (t < 38.0f)
    {
        float tau = (t - 35.0f) / 3.0f;
        s.altitude = APOGEE_ALTITUDE - 3.0f * sin(tau * PI);

        // Black powder separation charge shock (t = 35.3 to 35.7 s)
        if (t >= 35.3f && t <= 35.7f)
        {
            s.accelZ_g = 3.5f + noiseValue(0.2f);
            s.accelX_g = 1.5f + noiseValue(0.2f);
            s.accelY_g = 1.2f + noiseValue(0.2f);
        }
        else
        {
            s.accelZ_g = -0.2f + noiseValue(0.02f);
            s.accelX_g = 0.02f * sin(t * 2.0f);
            s.accelY_g = 0.02f * cos(t * 2.0f);
        }

        s.downrangeDrift = 0.60f;

        if (t < 35.3f)
        {
            s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE; // (7)
        }
        else if (t < 35.7f)
        {
            s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD; // (15)
        }
        else
        {
            s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF; // (31)
        }
        return s;
    }

    // --------------------------------------------------------
    // PHASE 5: DROGUE PARACHUTE DESCENT (38 - 65 s)
    // High-speed descent (~55 m/s) from 1850 m down to 350 m.
    // Pendulum swing under canopy creates realistic cyclic transverse load.
    // --------------------------------------------------------
    if (t < 65.0f)
    {
        float tau = (t - 38.0f) / 27.0f;
        s.altitude = APOGEE_ALTITUDE - (APOGEE_ALTITUDE - 350.0f) * tau;

        // Equilibrium drag balances gravity: net 1g with atmospheric turbulence
        s.accelZ_g = 1.0f + 0.2f * sin(t * 2.0f) + noiseValue(0.03f);

        // Coning/pendulum oscillation beneath canopy
        s.accelX_g = 0.15f * sin(t * 1.5f) + noiseValue(0.02f);
        s.accelY_g = 0.15f * cos(t * 1.5f) + noiseValue(0.02f);

        s.downrangeDrift = 0.60f + 0.25f * tau;
        s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF; // (31)
        return s;
    }

    // --------------------------------------------------------
    // PHASE 6: MAIN CHUTE INFLATION SHOCK (65 - 68 s)
    // At ~350 m, main parachute deploys.
    // t < 65.4s: Bit 5 (MAIN_ORD = 32)
    // t >= 65.4s: Bit 6 (MAIN_CONF = 64)
    // --------------------------------------------------------
    if (t < 68.0f)
    {
        float tau = (t - 65.0f) / 3.0f;
        s.altitude = 350.0f - 50.0f * tau;

        // Parachute canopy snatch load & inflation shock
        if (t >= 65.2f && t <= 65.8f)
        {
            s.accelZ_g = 4.8f + noiseValue(0.2f);
            s.accelX_g = 0.4f * sin(t * 5.0f) + noiseValue(0.1f);
            s.accelY_g = 0.3f * cos(t * 5.0f) + noiseValue(0.1f);
        }
        else
        {
            s.accelZ_g = 1.2f + noiseValue(0.04f);
            s.accelX_g = 0.1f * sin(t * 2.0f);
            s.accelY_g = 0.1f * cos(t * 2.0f);
        }

        s.downrangeDrift = 0.85f + 0.05f * tau;

        if (t < 65.4f)
        {
            s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF | STATUS_BIT_MAIN_ORD; // (63)
        }
        else
        {
            s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF | STATUS_BIT_MAIN_ORD | STATUS_BIT_MAIN_CONF; // (127)
        }
        return s;
    }

    // --------------------------------------------------------
    // PHASE 7: MAIN CANOPY TERMINAL GLIDE (68 - 85 s)
    // Gentle steady descent (~17 m/s) from 300 m down to ground.
    // --------------------------------------------------------
    if (t < 85.0f)
    {
        float tau = (t - 68.0f) / 17.0f;
        s.altitude = 300.0f * (1.0f - tau);

        s.accelZ_g = 1.0f + 0.05f * sin(t) + noiseValue(0.015f);
        s.accelX_g = 0.05f * sin(t * 0.8f) + noiseValue(0.01f);
        s.accelY_g = 0.05f * cos(t * 0.8f) + noiseValue(0.01f);

        s.downrangeDrift = 0.90f + 0.10f * tau;
        s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF | STATUS_BIT_MAIN_ORD | STATUS_BIT_MAIN_CONF; // (127)
        return s;
    }

    // --------------------------------------------------------
    // PHASE 8: TOUCHDOWN & RECOVERY BEACON (85 - 95 s)
    // Ground impact spike at t = 85.1s (6.2g shock).
    // Bit 7: LANDED (128) -> Total mask = 255
    // --------------------------------------------------------
    s.altitude = 0.0f;
    s.downrangeDrift = 1.0f;
    s.statusCode = STATUS_BIT_POWERED | STATUS_BIT_BURNOUT | STATUS_BIT_APOGEE | STATUS_BIT_DROGUE_ORD | STATUS_BIT_DROGUE_CONF | STATUS_BIT_MAIN_ORD | STATUS_BIT_MAIN_CONF | STATUS_BIT_LANDED; // (255)

    if (t >= 85.0f && t <= 85.3f)
    {
        // Touchdown landing impact impulse
        s.accelZ_g = 6.2f + noiseValue(0.3f);
        s.accelX_g = 2.0f + noiseValue(0.2f);
        s.accelY_g = 1.8f + noiseValue(0.2f);
    }
    else
    {
        // Stationary on the ground
        s.accelZ_g = 1.0f + noiseValue(0.003f);
        s.accelX_g = noiseValue(0.003f);
        s.accelY_g = noiseValue(0.003f);
    }

    return s;
}

// ------------------------------------------------------------
// BAROMETRIC PRESSURE FORMULA
// ------------------------------------------------------------
// P = P0 * exp(-h / H)
// P0 = 101325 Pa, H = 8434.5 m
// ------------------------------------------------------------

float getPressure(float altitude)
{
    const float P0 = 101325.0f;
    const float SCALE_HEIGHT = 8434.5f;
    return P0 * exp(-altitude / SCALE_HEIGHT);
}

// ------------------------------------------------------------
// SIMULATED TEMPERATURE
// ------------------------------------------------------------

float getTemperature(float altitude, float t)
{
    float temp = 20.0f - (altitude * 0.0065f);
    temp += 0.5f * sin(t * 0.3f);
    return temp;
}

// ------------------------------------------------------------
// GENERATE & TRANSMIT TELEMETRY PACKET
// ------------------------------------------------------------

void sendTelemetry()
{
    uint32_t timestamp = millis() - missionStartTime;
    float t = timestamp / 1000.0f;

    // Run flight trajectory kinematics
    FlightState flight = calculateFlight(t);
    uint32_t pressure = (uint32_t)getPressure(flight.altitude);

#if SIMULATE_RF_PACKET_LOSS
    // Drop 1 out of 5 packets during high dynamic motor burn to test loss metrics
    if ((t >= 13.0f && t <= 15.5f) || (t >= 50.0f && t <= 54.0f))
    {
        if ((frameNumber % 5) == 0)
        {
            frameNumber++; // Skip frame sequence number to induce detectable loss
            return;
        }
    }
#endif

#if USE_GROUND_STATION_30BYTE_FRAME
    // ========================================================
    // 30-BYTE FRAME BUILDER (Ground Station Native)
    // ========================================================
    uint8_t packet[30];

    // Accelerometer raw scaling
    int16_t accelX = (int16_t)(flight.accelX_g * ACCEL_XY_SCALE);
    int16_t accelY = (int16_t)(flight.accelY_g * ACCEL_XY_SCALE);
    int16_t accelZ = (int16_t)(flight.accelZ_g * ACCEL_Z_SCALE);

    // Realistic wind drift along a downrange ground track (~700 m southeast)
    float latDeg = BASE_LATITUDE  - (0.0030f * flight.downrangeDrift);
    float lonDeg = BASE_LONGITUDE + (0.0050f * flight.downrangeDrift);
    int32_t latRaw = (int32_t)(latDeg * 1000000.0f);
    int32_t lonRaw = (int32_t)(lonDeg * 1000000.0f);

    int16_t altRaw = (int16_t)round(flight.altitude);

    // Byte 0: Rocket ID
    packet[0] = ROCKET_ID;

    // Byte 1: Frame Type / Header (expected 0x01)
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

    // Bytes 14-16: Pressure (uint24)
    writeUint24BE(packet, 14, pressure);

    // Bytes 17-20: Latitude (int32)
    writeInt32BE(packet, 17, latRaw);

    // Bytes 21-24: Longitude (int32)
    writeInt32BE(packet, 21, lonRaw);

    // Bytes 25-26: Altitude (int16)
    writeInt16BE(packet, 25, altRaw);

    // Byte 27: Status
    packet[27] = flight.statusCode;

    // Bytes 28-29: CRC-16/CCITT-FALSE across bytes 0..27
    uint16_t crc = crc16_ccitt(packet, 28);
    writeUint16BE(packet, 28, crc);

    // Transmit 30 bytes over serial
    Serial.write(packet, 30);

#else
    // ========================================================
    // 22-BYTE FRAME BUILDER (Legacy Format)
    // ========================================================
    uint8_t packet[22];

    int16_t accelX = (int16_t)(flight.accelX_g * MPU_SCALE);
    int16_t accelY = (int16_t)(flight.accelY_g * MPU_SCALE);
    int16_t accelZ = (int16_t)(flight.accelZ_g * MPU_SCALE);

    float temperatureC = getTemperature(flight.altitude, t);
    int16_t temperature = (int16_t)(temperatureC * 10.0f);

    packet[0] = ROCKET_ID;
    packet[1] = HEADER;
    writeUint16BE(packet, 2, frameNumber);
    writeUint32BE(packet, 4, timestamp);
    writeInt16BE(packet, 8, accelX);
    writeInt16BE(packet, 10, accelY);
    writeInt16BE(packet, 12, accelZ);
    writeUint24BE(packet, 14, pressure);
    writeInt16BE(packet, 17, temperature);
    packet[19] = flight.statusCode;

    uint16_t crc = crc16_ccitt(packet, 20);
    writeUint16BE(packet, 20, crc);

    Serial.write(packet, 22);
#endif

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
    lastSendTime = millis();
    frameNumber = 0;
}

// ------------------------------------------------------------
// MAIN LOOP
// ------------------------------------------------------------

void loop()
{
    uint32_t now = millis();

    // Reset mission loop when total flight duration elapses
    if ((now - missionStartTime) >= MISSION_DURATION_MS)
    {
        missionStartTime = now;
        frameNumber = 0;
    }

    // Fixed 5 Hz transmission rate (200 ms interval)
    if ((now - lastSendTime) >= SAMPLE_PERIOD_MS)
    {
        lastSendTime = now;
        sendTelemetry();
    }
}
