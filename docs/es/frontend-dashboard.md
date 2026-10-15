# Diseño del Tablero de Telemetría y Especificación Ergonómica

> **Idioma / Language:** [ 🇪🇸 Español ](frontend-dashboard.md) | [ 🇬🇧 English ](../frontend-dashboard.md)

---

## 1. Objetivo y Filosofía Visual

El tablero de la **Estación Terrena** está diseñado para presentar la telemetría en tiempo real de forma clara, densa y ergonómica durante operaciones críticas de lanzamiento de cohetes.

### Principios de Diseño Aeronáutico:
1. **Adquisición Cognitiva Rápida:** Tipografía de gran tamaño con alto contraste (tema oscuro espacial `#0a0e17`) legible bajo luz solar directa en campo abierto.
2. **Jerarquía Visual de Tres Niveles:**
   - **Nivel 1 (Crítico):** Altitud, velocidad vertical, aceleración y estado de la máquina de vuelo.
   - **Nivel 2 (Navegación y Enlace):** Coordenadas geodésicas en mapa Leaflet, satélites, pérdida de paquetes y estado del puerto serie.
   - **Nivel 3 (Diagnóstico):** Presión barométrica, temperaturas, giroscopios y tramas crudas en hexadecimal.
3. **Insignias de Alerta Estándar ISA-18.2:** Códigos de color normalizados (Verde = Nominal, Amarillo = Alerta, Rojo = Crítico, Azul = Info).

---

## 2. Disposición General de la Interfaz (Grid de 12 Columnas)

La pantalla se distribuye en tres zonas funcionales:

### 2.1 Barra Superior (Header)
Abarca todo el ancho de la ventana:
- Título de Misión y Logotipo.
- Temporizador de Misión (MET - Mission Elapsed Time): `T+ 00:03:42`.
- Indicador de Enlace RF: `● CONECTADO` o `○ DESCONECTADO`.
- Contador de tramas y frecuencia instantánea de recepción (Hz).

### 2.2 Fila Superior de Instrumentos (4 / 4 / 4 Columnas)
- **Barómetro y Presión (4 col):** Presión estática en $\text{hPa}$, tendencia barométrica e historial temporal.
- **Altímetro Primario (4 col):** Cinta móvil de altitud Canvas, altitud actual en metros y apogeo máximo alcanzado.
- **Acelerómetro Triaxial (4 col):** Aceleraciones $a_x, a_y, a_z$ en $g$, vector de aceleración total y gráfico osciloscópico.

### 2.3 Fila Inferior (6 / 3 / 3 Columnas)
- **Mapa GPS y Navegación (6 col):** Mapa interactivo Leaflet con trazado de trayectoria, coordenadas WGS-84, altitud GPS y velocidad sobre el suelo.
- **Salud del Enlace y Radio (3 col):** Porcentaje de pérdida de paquetes, tramas corruptas descartadas, RSSI/SNR y calidad del enlace.
- **Hitos de Misión y Eventos (3 col):** Registro secuencial de fases de vuelo (despegue, fin de combustión, apogeo, apertura de paracaídas y aterrizaje).

```text
┌────────────────────────────────────────────────────────────────────────┐
│ HEADER — ESTACIÓN TERRENA               T+ 00:03:42   ● CONECTADO 10Hz │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ BARÓMETRO (hPa)   │ ALTITUD (m)       │ ACELERACIÓN (g)                │
│ 1013.2 hPa        │ 1850 m (MAX)      │ Ax: 0.1 | Ay: -0.1 | Az: 4.8  │
├───────────────────┴───────┬───────────┴────────┬───────────────────────┤
│ MAPA GPS LEAFLET          │ SALUD DEL ENLACE   │ HITOS DE VUELO        │
│ Lat: -34.6038             │ Pérdida: 0.0%      │ 155s: DESPEGUE        │
│ Lon: -58.3817  Sats: 14   │ Inválidos: 0       │ 180s: APOGEO (1850m)  │
└───────────────────────────┴────────────────────┴───────────────────────┘
```

---

## 3. Instrumentos Principales

### 3.1 Cinta Móvil de Altitud (Canvas)
Instrumento gráfico inspirado en las pantallas de vuelo primarias (PFD) aeronáuticas:
- Dibuja una escala graduada que se desliza verticalmente con suavidad.
- Aguja indicadora central fija con lectura digital de alta resolución.
- Indicador flotante de máxima altitud (apogeo) memorizado durante el vuelo.

### 3.2 Osciloscopios Temporales en Tiempo Real
- Búfer rodante de 300 puntos sin dependencias externas pesadas (renderizado directo mediante HTML5 2D Canvas).
- Escala dinámica automática para absorber tanto aceleraciones en plataforma ($1.0\text{ g}$) como empujes intensos de motor ($> 10\text{ g}$).

### 3.3 Mapa GPS Satelital
- Centrado automático con opción de seguimiento del cohete (*pan-to-track*).
- Marcador de plataforma de lanzamiento (origen) y posición actual.
- Línea poligonal de trayectoria con coloración según altitud.

---

## 4. Consola Pre-Vuelo Go / No-Go (`/gonogo`)

Vista operativa especializada en la verificación de seguridad y calificación de sensores en rampa antes del encendido del motor.

### Capacidades Principales:
- **Veredicto Global:** Cartel permanente de alto contraste `GO` (Verde) vs `NO-GO` (Rojo) con etiquetas de bloqueos activos.
- **Temporizador de Estabilidad Continua:** Acumula segundos de estabilidad con todos los subsistemas dentro de los márgenes nominales. Cualquier lectura fuera de rango reinicia el contador a cero.
- **Validación de Baselines en Rampa:**
  - *Altitud de referencia:* $|h| \le \text{tolerancia}$ (nominal $0.0\text{ m} \pm 5.0\text{ m}$).
  - *Calibración de acelerómetros:* Ejes transversales $|a_x|, |a_y| \le 0.10\text{ g}$ y gravedad en reposo $|a_z - 1.0\text{ g}| \le 0.15\text{ g}$.
  - *Fijación GPS:* Verificación de enganche (`FIX_3D`) y deriva radial en rampa $\le 5.0\text{ m}$.
- **Meteorología de Superficie:** Evaluación de viento ($\le 10\text{ m/s}$), nubosidad ($\le 75\%$), visibilidad ($\ge 5\text{ km}$) y autorización del oficial de meteorología.

---

## 5. Consola de Búsqueda y Recuperación Táctica (`/recovery`)

Vista operativa optimizada para cuadrillas de búsqueda y rescate (SAR) orientada a la localización expedita del vehículo tras el aterrizaje.

### Capacidades y Elementos de Interfaz:
- **Banner de Guiado Hero:**
  - **Distancia al Cohete:** Distancia geodésica instantánea calculada desde la plataforma de lanzamiento o la posición del operador (en metros o kilómetros).
  - **Rumbo / Azimut y Brújula Táctica:** Aguja animada de $360^\circ$ que marca la dirección exacta (ej. `124°`, sector `SE`) para orientar el desplazamiento del personal en terreno.
  - **Estado de Aterrizaje:** Evaluación del impacto (`STANDBY`, `VOLANDO`, `ATERRIZAJE SUAVE`, `ATERRIZAJE BRUSCO`) junto a la velocidad vertical residual ($V_z$ al contacto).
  - **Botones de Acción Inmediata:**
    - *Abrir en Google Maps:* Abre directamente la coordenada GPS en Google Maps (`https://www.google.com/maps/search/?api=1&query={lat},{lon}`) para navegación paso a paso a pie o en vehículo 4x4.
    - *Copiar Coordenadas:* Copia con un clic las coordenadas geográficas al portapapeles con confirmación visual tipo toast.
- **Mapa Táctico de Trayectoria y Zona de Impacto:**
  - Mapa interactivo Leaflet con marcador de rampa, trazado completo de descenso y última coordenada recibida.
  - Accesos directos de centrado: `Centrar Cohete`, `Centrar Base`, `Ver Todo` y `Mi Ubicación` (geolocalización de la cuadrilla mediante la API del navegador).
- **Paneles Laterales de Información:**
  - *Coordenadas del Vehículo:* Latitud y longitud WGS-84, altitud GPS, cantidad de satélites en seguimiento, hora del último paquete recibido e indicador de GPS FIX.
  - *Referencia de Base:* Coordenadas de rampa y ángulo de elevación respecto al horizonte.
  - *Cronología de Vuelo:* Historial secuencial de hitos y transiciones de fase (`STANDBY`, `POWERED`, `BURNOUT`, `APOGEE`, `MAIN_CONF`, `LANDED`).
  - *Diagnóstico del Enlace RF:* Tramas recibidas en tierra, número de secuencia de aviónica, pérdida porcentual en ventana deslizante de 5 segundos y apogeo máximo memorizado.
- **Diseño Adaptativo para Dispositivos Móviles:**
  - Cuadrícula responsiva que se colapsa fluidamente en una sola columna táctil para su uso ágil en smartphones y tablets en campo abierto.

---

## 6. Documentación Relacionada

- **[Arquitectura del Sistema](architecture.md):** Flujo de datos y renderizado desacoplado a 60 FPS.
- **[Especificación del Protocolo Binario](protocol.md):** Mapa de memoria y trama de 65 bytes.
- **[Especificación de la API](api.md):** Contratos de datos WebSocket y endpoints REST.
- **[Guía de Inicio y Operación](getting-started.md):** Puesta en marcha y verificación del enlace.
- **[Especificación del Esquema de Trama](frame-schema.md):** Definición declarativa de trama en YAML.
- **[Cálculos Futuros y Algoritmos](future-calculations.md):** Fórmulas de velocidad vertical $V_z$ y orientación 3D.
