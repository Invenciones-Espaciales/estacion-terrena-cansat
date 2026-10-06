# Dashboard de Telemetría — Especificación

## 1. Objetivo

El dashboard de la **Estación Terrena de Telemetría** debe presentar la información de telemetría de forma clara, compacta y orientada al monitoreo en tiempo real.

La interfaz se organizará sobre una **grid de 4 columnas × 2 filas**, pero los componentes no estarán obligados a ocupar todos el mismo espacio.

La intención es establecer una jerarquía visual:

* **Métricas principales:** valores grandes y fáciles de identificar.
* **Estado del enlace:** información crítica siempre visible.
* **GPS / mapa:** componente visual dominante.
* **Información técnica:** disponible sin competir con las métricas principales.
* **Eventos:** visualización cronológica de hitos.

---

# 2. Layout general

La interfaz tendrá tres zonas principales:

### Header

El encabezado ocupará todo el ancho.

Debe mostrar:

* Nombre del sistema: `Estación Terrena`
* Tiempo transcurrido desde el inicio: `T+ 00:03:42`
* Estado del enlace: `● LINK CONNECTED`

Ejemplo:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ HEADER — Estación Terrena                  T+ 00:03:42    ● LINK CONNECTED │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Grid principal

La zona de contenido utilizará una grid de **4 columnas × 2 filas**.

No todos los tiles tendrán necesariamente el mismo ancho.

| Tile              |      Ancho |   Alto |
| ----------------- | ---------: | -----: |
| Barómetro         |  1 columna | 1 fila |
| Altitud           |  1 columna | 1 fila |
| Aceleración       |  1 columna | 1 fila |
| Salud de conexión |  1 columna | 1 fila |
| GPS / Mapa        | 2 columnas | 1 fila |
| Log de hitos      |  1 columna | 1 fila |
| Datos de Frame    |  1 columna | 1 fila |

La distribución resultante es:

```text
┌──────────┬──────────┬──────────┬──────────┐
│ BARÓMETRO│ ALTITUD  │ ACELER.  │ LINK     │
├──────────┴──────────┼──────────┼──────────┤
│                     │ LOG      │ FRAME    │
│       GPS / MAP     │ HITOS    │ DATA     │
└─────────────────────┴──────────┴──────────┘
```

Esto permite que el mapa tenga mayor presencia visual sin sacrificar la densidad de información.

---

# 3. Barómetro

El componente de barómetro debe mostrar la presión atmosférica como métrica principal.

No se utilizará una tabla como elemento principal.

### Información

* Presión actual
* Temperatura
* Variación de presión
* Presión mínima
* Presión máxima

### Diseño

```text
BAROMETER

        1008.42
          hPa

        24.3 °C

       ↓ 0.8 hPa

MIN     1006.12
MAX     1012.83
```

La presión actual debe tener mayor jerarquía visual que el resto de los datos.

### Evolución futura

Si se incorpora información histórica, podrá agregarse una **mini línea de tendencia**.

El gráfico debe ser pequeño y secundario; no debe convertir el componente en un gráfico grande.

---

# 4. Altitud

La altitud será una de las métricas principales del dashboard.

### Información

* Altitud actual
* Velocidad vertical
* Altitud máxima alcanzada

### Diseño

```text
ALTITUDE

       124.8
         m

       ↑ 2.4 m/s

MAX    181.2 m
```

El valor actual debe ser uno de los elementos tipográficos más grandes de la interfaz.

Referencia:

```text
124.8
  m
```

El valor puede utilizar aproximadamente **42–48 px**, dependiendo de la resolución final del dashboard.

---

# 5. Aceleración

El componente mostrará la aceleración en los tres ejes.

### Información

* Eje X
* Eje Y
* Eje Z
* Magnitud total

### Diseño

```text
ACCELERATION

 X       +0.12 g
 Y       -0.03 g
 Z       +1.01 g
 ─────────────────
 MAGNITUDE  1.01 g
```

La magnitud total tendrá una jerarquía ligeramente superior a los valores individuales.

### Evolución futura

Podrá incorporarse una representación visual de los tres ejes.

No es necesaria para la primera versión.

---

# 6. Salud de conexión

El componente de salud del enlace debe proporcionar una visión inmediata del estado de comunicación con el sistema remoto.

### Información

* Estado de conexión
* RSSI
* SNR
* Paquetes recibidos
* Paquetes perdidos
* Porcentaje de pérdida
* Tiempo desde el último paquete
* Tasa de recepción

### Diseño

```text
LINK HEALTH

● CONNECTED

RSSI              -64 dBm
SNR                 +9 dB

PACKETS          18,452
LOST                  3
LOSS              0.02 %

LAST PACKET       0.1 s
RX RATE          10.0 Hz
```

### Estados

El indicador de estado utilizará una codificación visual:

| Estado       | Indicador |
| ------------ | --------- |
| Conectado    | Verde     |
| Degradado    | Amarillo  |
| Desconectado | Rojo      |

El estado deberá ser identificable sin necesidad de interpretar los valores RSSI/SNR.

Además, este componente deberá aprovechar los datos de **RSSI y SNR asociados a cada trama recibida**.

---

# 7. GPS / Mapa

El mapa será el componente visual dominante del dashboard y ocupará **2 columnas**.

### Información

Debe mostrar:

* Posición actual
* Trayectoria recorrida
* Punto de inicio
* Hitos georreferenciados, cuando estén disponibles

### Diseño inicial

```text
GPS / MAP

┌─────────────────────────────────────────────┐
│                                             │
│                     MAP                     │
│                                             │
│                         ●                   │
│                       /                     │
│                     /                       │
│                   ●                         │
│                                             │
└─────────────────────────────────────────────┘

LAT       -34.600123
LON       -58.650421
ALT       124.8 m
SAT       11
```

La posición GPS no debe implementarse como una imagen estática.

### Implementación futura

Se podrá integrar un mapa interactivo mediante:

* **Leaflet**
* **OpenStreetMap**

Sobre el mapa se podrán dibujar:

* Posición actual
* Trayectoria
* Punto de inicio
* Hitos georreferenciados

El mapa deberá ser interactivo cuando esta funcionalidad sea implementada.

---

# 8. Log de hitos

El componente de eventos mostrará los hitos registrados durante el vuelo o sesión de telemetría.

Los eventos se representan como información temporal: **texto + timestamp**.

### Diseño

```text
FLIGHT EVENTS

09:42:13    HITO 1
09:42:48    HITO 2
09:43:12    HITO 3
09:43:41    HITO 4
09:44:02    HITO 5
```

En la parte superior se destacará el último evento:

```text
CURRENT
HITO 4
```

### Decisión de diseño

No se utilizarán campos `STATE` ni `MODE` en este componente.

Los hitos representan **eventos temporales**, por lo que el componente debe mantener una representación cronológica.

---

# 9. Datos de Frame

Este componente estará orientado a información técnica y debugging.

### Información

* Número de secuencia
* Timestamp
* Tamaño de la trama
* Estado del CRC
* Cantidad de frames válidos
* Cantidad de frames inválidos

### Diseño

```text
FRAME

SEQ             18452
TIMESTAMP       182340 ms
SIZE            53 B
CRC             OK
```

Información adicional:

```text
VALID FRAMES    18452
INVALID             2
```

Este componente debe tener menor jerarquía visual que las métricas de telemetría.

Su objetivo principal es facilitar la validación y diagnóstico del sistema durante las pruebas.

---

# 10. Jerarquía visual

La interfaz debe priorizar la información en este orden:

1. **Estado del enlace**
2. **Altitud**
3. **Posición / mapa**
4. **Aceleración**
5. **Barómetro**
6. **Eventos**
7. **Información técnica de frames**

Los valores principales deben utilizar tipografía grande y alto contraste.

La información secundaria debe utilizar tamaños menores para evitar saturación visual.

---

# 11. Principios de diseño

### Densidad

El dashboard debe mostrar mucha información sin convertirse en una tabla de datos.

### Jerarquía

Cada componente debe tener claramente:

* Título
* Valor principal
* Valores secundarios
* Unidades

### Tiempo real

Los valores deberán actualizarse sin provocar cambios bruscos o innecesarios en el layout.

### Estado

Los estados críticos deben poder identificarse visualmente de forma inmediata.

### Extensibilidad

El diseño debe permitir agregar posteriormente:

* Gráficos históricos
* Tendencias
* Mapa interactivo
* Más métricas de telemetría
* Diagnóstico avanzado
* Exportación de datos

sin tener que rediseñar completamente la estructura.

---

# 12. Resumen de la arquitectura visual

La composición final queda definida como:

```text
┌──────────────────────────────────────────────────────────────┐
│                         HEADER                               │
├──────────┬──────────┬──────────┬──────────┤
│ BARÓMETRO│ ALTITUD  │ ACELER.  │ LINK     │
├──────────┴──────────┼──────────┼──────────┤
│                     │          │          │
│      GPS / MAP      │   LOG    │  FRAME   │
│                     │  HITOS   │   DATA   │
│                     │          │          │
└─────────────────────┴──────────┴──────────┘
```

La regla principal es **4 columnas × 2 filas con tiles de tamaño variable**, utilizando el espacio adicional para destacar aquellos componentes que aportan mayor valor operativo, especialmente **GPS / MAP** y **Altitud**.
