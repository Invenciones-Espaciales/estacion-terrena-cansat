# Cálculos e interpretaciones retirados del dashboard

Por ahora el dashboard ([`frontend/index.html`](../frontend/index.html)) muestra **solo datos tal como llegan en la trama**. Todo lo calculado o interpretado se quitó y queda documentado acá para retomarlo.

> La implementación completa y funcionando está archivada en
> [`docs/referencia/index_con_calculos.html`](referencia/index_con_calculos.html).
> Se puede abrir con el servidor corriendo (copiarla a `frontend/` o servirla aparte) para ver cómo se comportaba.

## Qué se muestra hoy (sin interpretación)

| Elemento | Origen |
|---|---|
| Altitud, cinta, máxima, gráfico | `altitude` de la trama |
| Barómetro | `pressure` (Pa → hPa) |
| Aceleración X/Y/Z | `accel_x/y/z` |
| Posición y traza | `latitude`, `longitude` |
| Fase de vuelo y marcadores en gráficos | `status` |
| MET | `timestamp` |
| Pérdida de paquetes, recibidos, CRC | `statistics` del backend |
| RSSI, SNR, voltaje | `N/D`: se muestran si el backend envía `rssi`, `snr`, `voltage` |

La tarjeta **CARGA G** muestra la magnitud `√(ax²+ay²+az²)` y su máximo. Es el único cálculo que se conserva, por pedido anterior. Si se quiere eliminar, basta quitar esa tarjeta.

## Cálculos retirados

### 1. Altitud barométrica y filtro de Kalman
- **Altitud barométrica:** `h_baro = h0 + 44330 · (1 − (p/p0)^0.190295)`
  - `p0` y `h0` son la presión y la altitud GNSS de la primera muestra (referencia en la rampa).
- **Filtro de Kalman 1D, estado `[h, v]`:**
  - Predicción con `dt` entre muestras (limitado a 1 s), ruido de proceso por aceleración `q = 20 (m/s²)²`:
    - `P00 += dt·(P10+P01) + dt²·P11 + q·dt⁴/4`
    - `P01 += dt·P11 + q·dt³/2`, `P10` igual
    - `P11 += q·dt²`
  - Dos actualizaciones secuenciales con `H=[1 0]`:
    - Barómetro con `R = 4 m²`.
    - GNSS con `R = 25 m²`.
  - Inicialización: `h = altitud GNSS`, `v = 0`, `P = diag(25, 25)`.
- **Se reinicia** cuando el `timestamp` retrocede.

### 2. Variómetro (Vz) y velocidad
- **Vz:** es la componente `v` del Kalman.
- **Velocidad horizontal `Vh`:**
  - Se calcula con la posición local (ver punto 3) comparando la muestra actual con la más reciente de hace 1 s o más (ventana de 4 s).
  - Esto evita que el GNSS, que tiene tasa menor que la telemetría, dé saltos y ceros.
- **Velocidad total:** `|V| = √(Vz² + Vh²)`.
- **Visualización:** barra vertical de ±100 m/s con aguja y gráfico `|V|` y `Vz` vs tiempo.

### 3. Posición local, acimut, elevación y distancia
- **Estación:** el primer fix GNSS válido (lat/lon distintos de 0) o los parámetros de URL `?stlat=&stlon=&stalt=`.
- **Coordenadas locales (aproximación plana):**
  - `x = (lon − lon0)·111320·cos(lat0)`
  - `y = (lat − lat0)·110540`
  - `u = altitud − alt_estación`
- **Resultados:**
  - Acimut: `atan2(x, y)` normalizado a 0–360°.
  - Elevación: `atan2(u, √(x²+y²))`.
  - Distancia: `√(x²+y²+u²)`; no se calcula si es menor a 5 m.
- **Cuadrante polar:** radio `(90−el)/90`, ángulo = acimut desde el norte, y haz de antena de ±10° (`beamHalfWidthDeg`).

### 4. Elipse de impacto
- **Condición:** `Vz < −2 m/s` y altitud sobre el suelo mayor a 5 m. `AGL = h − altitud inicial`.
- **Cálculo:**
  - `t = AGL / (−Vz)`
  - `impacto = pos + (Vx, Vy)·t`
  - Semieje mayor `a = max(10 m, 0.15·Vh·t)`, orientado según el rumbo de la velocidad.
  - Semieje menor `b = max(10 m, 0.5·a)`.
- **Limitaciones:** es una estimación lineal sin viento ni modelo del paracaídas. Los porcentajes son supuestos.

### 5. Actitud / inclinación
- `pitch = atan2(ax, √(ay²+az²))`
- `roll = atan2(ay, −az)`
- `inclinación = atan2(√(ax²+ay²), |az|)`
- Se suavizan con filtro exponencial `α = 0.2`.
- **Limitación:** solo es válida con aceleración propia baja, no durante el empuje del motor.
- **Pendiente:** el signo de los ejes depende del montaje del sensor (en reposo `az ≈ −1 g`).

### 6. Medidor G con aguja fantasma
- **Dial:** semicircular de 0 a 8 g₀.
- **Aguja fantasma:** retención de pico con caída de 2 g/s: `ghost = max(g, ghost − 2·dt)`.

### 7. Cola de alarmas ISA-18.2
- **Estados por alarma:** activa sin acuse, activa acusada, retornada sin acuse. Al retornar estando acusada, se elimina de la cola.
- **Orden:** por prioridad y luego por hora.
- **Acciones:** acuse individual y "acusar todas". Cada alarma, retorno y acuse se registra en el log de eventos.
- **Se evalúa a 4 Hz.**

| ID | Prioridad | Condición |
|---|---|---|
| `LINK` | Crítica | sin conexión o sin paquetes por más de 3 s |
| `DESC` | Crítica | fase ≥ Descenso, `Vz < −25 m/s`, AGL entre 20 y 300 m |
| `GLOAD` | Alta | carga mayor a 8 g |
| `CRC` | Alta | aumentó el contador de CRC inválidos en los últimos 10 s |
| `VOLT` | Alta | voltaje menor a 3,3 V |
| `LOSS` | Media | pérdida de paquetes mayor al 10% |
| `GNSS` | Media | sin fix válido |
| `RSSI` | Media | RSSI menor a −100 dBm |

Estos umbrales son supuestos y hay que validarlos con el cohete real.

## Frecuencias de refresco objetivo (de la especificación)

| Zona | Frecuencia |
|---|---|
| Cabecera | 1–5 Hz |
| Instrumento primario | 10–20 Hz |
| Series temporales | 10 Hz |
| Navegación | 1–5 Hz |
| Alarmas y registro | por evento |

## Pendientes para retomar

- Validar los signos y el montaje de los ejes de aceleración.
- Definir el modelo de impacto (viento y descenso con paracaídas) y su incertidumbre.
- Definir posición de la estación (fija en `app.yaml` o por URL).
- Confirmar umbrales de alarmas.
- Agregar al backend los campos `rssi`, `snr` y `voltage` (`config/frame.yaml`).
- Cartografía offline (hoy usa teselas online de OpenStreetMap).
- Cuenta atrás: requiere una hora de despegue programada.
