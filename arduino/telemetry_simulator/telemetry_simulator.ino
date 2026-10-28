/*
 * ==============================================================================
 * CONAE CANSAT 2026–2027 TELEMETRY & COMMAND SIMULATOR FIRMWARE
 * ==============================================================================
 * Target: Arduino Uno / Nano / Mega / ESP32 / RP2040 / Teensy
 * Serial: 115200 baud, 8N1
 * Rate:   1 Hz (1 packet per second, official CONAE rate C5, X4)
 * Protocol: Plain-text ASCII CSV (Bases §4, G5)
 *
 * Telemetry Format:
 * TEAM_ID,MISSION_TIME,PACKET_COUNT,MODE,STATE,ALTITUDE,TEMPERATURE,PRESSURE,
 * VOLTAGE,CURRENT,GYRO_R,GYRO_P,GYRO_Y,ACCEL_R,ACCEL_P,ACCEL_Y,GPS_TIME,
 * GPS_ALTITUDE,GPS_LATITUDE,GPS_LONGITUDE,GPS_SATS,CMD_ECHO[,,OPTIONAL_DATA]
 *
 * Uplink Command Parser:
 * CMD,<TEAM_ID>,<ACTION>[,<ARGS>]\r\n
 * Supported:
 *   - CMD,1000,CAL         -> Calibrates relative altitude to 0.0 m (G1)
 *   - CMD,1000,ST,<TIME>   -> Synchronizes mission UTC time (F3)
 *   - CMD,1000,PC,0        -> Resets persistent packet counter (F1, F5)
 *   - CMD,1000,BATT        -> Queries battery health & solar payload (X6, G7)
 *   - CMD,1000,SIM,<MODE>  -> Toggles flight ('F') / simulation ('S') mode
 *   - CMD,1000,START       -> Manual mission launch / separation trigger (X3)
 * ==============================================================================
 */

#if defined(ARDUINO)
#include <Arduino.h>
#endif
#include <stdio.h>
#include <string.h>
#include <math.h>

// ------------------------------------------------------------------------------
// CONSTANTS & CONFIGURATION
// ------------------------------------------------------------------------------
const char TEAM_ID[] = "1000";
const uint32_t SERIAL_BAUD = 115200;
const uint32_t TELEMETRY_INTERVAL_MS = 1000; // 1 Hz (1000 ms)

// GPS Base Coordinates (Falda del Cañete, CONAE Córdoba, Argentina)
const float BASE_LATITUDE  = -31.5240f;
const float BASE_LONGITUDE = -64.4640f;
const float BASE_ELEVATION_MSL = 720.0f; // Ground elevation 720 m ASL

// ------------------------------------------------------------------------------
// MISSION STATE MACHINE
// ------------------------------------------------------------------------------
enum MissionState {
    STATE_LAUNCH_PAD = 0,
    STATE_ASCENT,
    STATE_APOGEE,
    STATE_DESCENT_C3, // Drogue parachute: 15 ± 3 m/s
    STATE_DESCENT_C4, // Main parachute: 5 ± 3 m/s
    STATE_LANDED
};

const char* STATE_NAMES[] = {
    "LAUNCH_PAD",
    "ASCENT",
    "APOGEE",
    "DESCENT",
    "DESCENT",
    "LANDED"
};

// ------------------------------------------------------------------------------
// RUNTIME VARIABLES
// ------------------------------------------------------------------------------
uint32_t lastTelemetryTime = 0;
uint32_t missionSeconds = 0;
uint32_t packetCount = 0;
char mode = 'F'; // 'F' = Flight, 'S' = Simulation
MissionState currentState = STATE_LAUNCH_PAD;

float currentAltitude = 0.0f;
float altitudeOffset = 0.0f;
float currentPressure = 93.5f; // kPa at ~720m ASL
float currentTemp = 21.5f;     // °C
float batteryVoltage = 3.92f;  // V (18650 Li-ion cell)
float batteryCurrent = 0.18f;  // A

// IMU dynamics
float gyroR = 0.0f, gyroP = 0.0f, gyroY = 0.0f;       // deg/s
float accelR = 0.0f, accelP = 0.0f, accelY = 9.81f;   // m/s^2 (Z = 1G on pad)

// GPS dynamics
float gpsLatitude = BASE_LATITUDE;
float gpsLongitude = BASE_LONGITUDE;
float gpsAltitude = BASE_ELEVATION_MSL;
uint8_t gpsSats = 11;

// Telecommand echo buffer
char cmdEcho[32] = "STANDBY";

// Serial input buffer for incoming commands
char rxBuffer[64];
uint8_t rxIndex = 0;

// Mission timeline benchmarks (seconds from launch)
uint32_t launchTimeSec = 20; // Launches at T+20s
uint32_t apogeeTimeSec = 45; // Apogee & rocket separation at T+45s (~1500m)
uint32_t mainChuteTimeSec = 115; // Deploy main at T+115s (~450m)
uint32_t landedTimeSec = 200;    // Touchdown at T+200s

// ------------------------------------------------------------------------------
// FUNCTION PROTOTYPES
// ------------------------------------------------------------------------------
void handleIncomingSerial();
void processCommand(const char* cmd);
void updatePhysics(float dt);
void transmitTelemetry();
void formatTime(uint32_t totalSec, char* outStr);

// ------------------------------------------------------------------------------
// SETUP
// ------------------------------------------------------------------------------
void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial && millis() < 3000); // Wait for USB CDC on boards like RP2040/ESP32

    lastTelemetryTime = millis();
}

// ------------------------------------------------------------------------------
// MAIN LOOP
// ------------------------------------------------------------------------------
void loop() {
    // 1. Process incoming telecommands from Ground Station
    handleIncomingSerial();

    // 2. Transmit 1 Hz telemetry
    uint32_t now = millis();
    if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime += TELEMETRY_INTERVAL_MS;
        missionSeconds++;

        updatePhysics(1.0f);
        transmitTelemetry();
    }
}

// ------------------------------------------------------------------------------
// TELECOMMAND HANDLER (Ground Station -> CanSat)
// ------------------------------------------------------------------------------
void handleIncomingSerial() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r') continue;
        if (c == '\n') {
            rxBuffer[rxIndex] = '\0';
            if (rxIndex > 0) {
                processCommand(rxBuffer);
            }
            rxIndex = 0;
        } else if (rxIndex < sizeof(rxBuffer) - 1) {
            rxBuffer[rxIndex++] = c;
        }
    }
}

void processCommand(const char* cmd) {
    // Format expected: CMD,<TEAM_ID>,<ACTION>[,<ARGS>]
    if (strncmp(cmd, "CMD,", 4) != 0) return;

    const char* teamPtr = cmd + 4;
    if (strncmp(teamPtr, TEAM_ID, strlen(TEAM_ID)) != 0) return; // Ignore foreign packets (X2)

    const char* actionPtr = strchr(teamPtr, ',');
    if (!actionPtr) return;
    actionPtr++; // Advance past comma

    // 1. Altitude Calibration (G1)
    if (strncmp(actionPtr, "CAL", 3) == 0) {
        altitudeOffset = currentAltitude;
        strncpy(cmdEcho, "CAL", sizeof(cmdEcho) - 1);
    }
    // 2. Set UTC Mission Time (F3)
    else if (strncmp(actionPtr, "ST,", 3) == 0) {
        // e.g. CMD,1000,ST,14:20:00
        int h = 0, m = 0, s = 0;
        if (sscanf(actionPtr + 3, "%d:%d:%d", &h, &m, &s) == 3) {
            missionSeconds = (uint32_t)h * 3600 + (uint32_t)m * 60 + s;
        }
        strncpy(cmdEcho, "ST", sizeof(cmdEcho) - 1);
    }
    // 3. Reset Packet Counter (F1, F5)
    else if (strncmp(actionPtr, "PC,0", 4) == 0) {
        packetCount = 0;
        strncpy(cmdEcho, "PC_RESET", sizeof(cmdEcho) - 1);
    }
    // 4. Battery Query (X6, G7)
    else if (strncmp(actionPtr, "BATT", 4) == 0) {
        strncpy(cmdEcho, "BATT_OK", sizeof(cmdEcho) - 1);
    }
    // 5. Simulation Mode Toggle (Bases §4)
    else if (strncmp(actionPtr, "SIM,", 4) == 0) {
        if (strstr(actionPtr, "ENABLE")) mode = 'S';
        else if (strstr(actionPtr, "DISABLE")) mode = 'F';
        strncpy(cmdEcho, "SIM_MODE", sizeof(cmdEcho) - 1);
    }
    // 6. Manual Flight Start / Separation Trigger (X3)
    else if (strncmp(actionPtr, "START", 5) == 0) {
        if (currentState == STATE_LAUNCH_PAD) {
            currentState = STATE_ASCENT;
            strncpy(cmdEcho, "LAUNCHED", sizeof(cmdEcho) - 1);
        }
    } else {
        // Generic custom command echo
        strncpy(cmdEcho, actionPtr, sizeof(cmdEcho) - 1);
    }
    cmdEcho[sizeof(cmdEcho) - 1] = '\0';
}

// ------------------------------------------------------------------------------
// TRAJECTORY PHYSICS SIMULATOR
// ------------------------------------------------------------------------------
void updatePhysics(float dt) {
    // Battery slight steady drain
    batteryVoltage = fmaxf(3.40f, 3.92f - (float)missionSeconds * 0.00015f);
    batteryCurrent = 0.16f + 0.04f * ((packetCount % 5 == 0) ? 1.0f : 0.0f);

    // State machine updates
    if (missionSeconds < launchTimeSec) {
        currentState = STATE_LAUNCH_PAD;
        currentAltitude = 0.0f;
        accelR = 0.02f; accelP = -0.01f; accelY = 9.81f;
        gyroR = 0.1f; gyroP = 0.0f; gyroY = -0.1f;
    } 
    else if (missionSeconds < apogeeTimeSec) {
        currentState = STATE_ASCENT;
        // Ascent velocity ~60 m/s average up to 1500m
        float progress = (float)(missionSeconds - launchTimeSec) / (float)(apogeeTimeSec - launchTimeSec);
        currentAltitude = 1500.0f * sinf(progress * (PI / 2.0f));
        accelY = 9.81f + 32.0f * (1.0f - progress); // Boost acceleration
        accelR = 2.5f * sinf(missionSeconds);
        accelP = 2.1f * cosf(missionSeconds);
        gyroR = 45.0f * (1.0f - progress);
        gyroP = 12.0f;
        gyroY = 8.0f;
    }
    else if (missionSeconds == apogeeTimeSec) {
        currentState = STATE_APOGEE;
        currentAltitude = 1500.0f;
        accelR = 0.0f; accelP = 0.0f; accelY = 0.0f; // Free-fall momentary
        gyroR = 1.0f; gyroP = 1.0f; gyroY = 1.0f;
        strncpy(cmdEcho, "MISSION_START", sizeof(cmdEcho) - 1); // Automatic X3 separation trigger
    }
    else if (missionSeconds < mainChuteTimeSec) {
        currentState = STATE_DESCENT_C3; // Drogue: 15 ± 3 m/s (C3 compliant)
        float descentRate = 14.8f; // m/s
        currentAltitude = fmaxf(450.0f, 1500.0f - descentRate * (float)(missionSeconds - apogeeTimeSec));
        accelY = 9.81f;
        accelR = 3.2f * sinf(missionSeconds * 1.5f);
        accelP = 2.8f * cosf(missionSeconds * 1.5f);
        gyroR = 22.0f * sinf(missionSeconds);
        gyroP = 18.0f * cosf(missionSeconds);
        gyroY = 9.0f;
    }
    else if (missionSeconds < landedTimeSec) {
        currentState = STATE_DESCENT_C4; // Main parachute: 5 ± 3 m/s (C4 compliant)
        float descentRate = 5.2f; // m/s
        currentAltitude = fmaxf(0.0f, 450.0f - descentRate * (float)(missionSeconds - mainChuteTimeSec));
        accelY = 9.81f;
        accelR = 0.8f * sinf(missionSeconds);
        accelP = 0.7f * cosf(missionSeconds);
        gyroR = 4.5f * sinf(missionSeconds * 0.5f);
        gyroP = 3.8f * cosf(missionSeconds * 0.5f);
        gyroY = 2.0f;
        if (currentAltitude <= 0.0f) {
            currentState = STATE_LANDED;
            currentAltitude = 0.0f;
        }
    }
    else {
        currentState = STATE_LANDED;
        currentAltitude = 0.0f;
        accelR = 0.0f; accelP = 0.0f; accelY = 9.81f;
        gyroR = 0.0f; gyroP = 0.0f; gyroY = 0.0f;
    }

    // Atmospheric barometric model: P = P0 * (1 - L*h/T0)^(g*M/(R*L))
    float relAlt = currentAltitude - altitudeOffset;
    currentPressure = 93.5f * expf(-relAlt / 8400.0f);
    currentTemp = 21.5f - (relAlt * 0.0065f);

    // GPS dynamic update
    gpsAltitude = BASE_ELEVATION_MSL + relAlt;
    gpsLatitude = BASE_LATITUDE + (0.000008f * (float)missionSeconds); // Slight wind drift
    gpsLongitude = BASE_LONGITUDE + (0.000012f * (float)missionSeconds);
}

// ------------------------------------------------------------------------------
// TELEMETRY TRANSMISSION (CONAE ASCII CSV at 1 Hz)
// ------------------------------------------------------------------------------
void transmitTelemetry() {
    packetCount++;

    char timeStr[12];
    formatTime(missionSeconds, timeStr);

    float relativeAlt = currentAltitude - altitudeOffset;

    // Optional payload data: e.g. solar panel voltage & temperature
    float solarVoltage = (currentState == STATE_DESCENT_C3 || currentState == STATE_DESCENT_C4) ? 4.95f : 0.0f;

    // Construct comma-separated packet
    // TEAM_ID, MISSION_TIME, PACKET_COUNT, MODE, STATE, ALTITUDE, TEMPERATURE, PRESSURE, 
    // VOLTAGE, CURRENT, GYRO_R, GYRO_P, GYRO_Y, ACCEL_R, ACCEL_P, ACCEL_Y, 
    // GPS_TIME, GPS_ALTITUDE, GPS_LATITUDE, GPS_LONGITUDE, GPS_SATS, CMD_ECHO [,,OPTIONAL_DATA]
    Serial.print(TEAM_ID);
    Serial.print(',');
    Serial.print(timeStr);
    Serial.print(',');
    Serial.print(packetCount);
    Serial.print(',');
    Serial.print(mode);
    Serial.print(',');
    Serial.print(STATE_NAMES[currentState]);
    Serial.print(',');
    Serial.print(relativeAlt, 1);
    Serial.print(',');
    Serial.print(currentTemp, 1);
    Serial.print(',');
    Serial.print(currentPressure, 2);
    Serial.print(',');
    Serial.print(batteryVoltage, 2);
    Serial.print(',');
    Serial.print(batteryCurrent, 2);
    Serial.print(',');
    Serial.print(gyroR, 1);
    Serial.print(',');
    Serial.print(gyroP, 1);
    Serial.print(',');
    Serial.print(gyroY, 1);
    Serial.print(',');
    Serial.print(accelR, 2);
    Serial.print(',');
    Serial.print(accelP, 2);
    Serial.print(',');
    Serial.print(accelY, 2);
    Serial.print(',');
    Serial.print(timeStr); // GPS time synchronized
    Serial.print(',');
    Serial.print(gpsAltitude, 1);
    Serial.print(',');
    Serial.print(gpsLatitude, 6);
    Serial.print(',');
    Serial.print(gpsLongitude, 6);
    Serial.print(',');
    Serial.print(gpsSats);
    Serial.print(',');
    Serial.print(cmdEcho);
    Serial.print(",,SOLAR_V:");
    Serial.print(solarVoltage, 2);
    Serial.print("\r\n");
}

void formatTime(uint32_t totalSec, char* outStr) {
    uint32_t h = (totalSec / 3600) % 24;
    uint32_t m = (totalSec / 60) % 60;
    uint32_t s = totalSec % 60;
    sprintf(outStr, "%02lu:%02lu:%02lu", (unsigned long)h, (unsigned long)m, (unsigned long)s);
}
