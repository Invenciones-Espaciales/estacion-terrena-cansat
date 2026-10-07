# Dashboard de Telemetría — Especificación

## 1. Objetivo

El dashboard de la **Estación Terrena de Telemetría** debe presentar la información de telemetría de forma clara, compacta y orientada al monitoreo en tiempo real.

La interfaz usa una grilla de 12 columnas: paneles de 4 columnas arriba y
paneles inferiores con anchos ajustados a su contenido.

La intención es establecer una jerarquía visual:

* **Métricas principales:** valores grandes y fáciles de identificar.
* **Estado del enlace:** información crítica siempre visible.
* **GPS y coordenadas:** agrupados en el mismo panel.
* **Eventos:** solo transiciones de etapa atravesadas por el cohete.

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

La grilla principal tiene 12 columnas. Barómetro, altitud y aceleración ocupan
4 columnas cada uno. En la siguiente fila mapa+coordenadas ocupa 6 columnas,
y salud de conexión e hitos ocupan 3 columnas cada uno.

La distribución resultante es:

```text
┌──────────┬──────────┬──────────┐
│ BARÓMETRO│ ALTITUD  │ ACELER.  │
├──────────┼──────────┼──────────┤
│ MAPA + COORDENADAS │ SALUD │ HITOS │
└────────────────────┴───────┴───────┘
```

Esto permite que el mapa tenga mayor presencia visual sin sacrificar la densidad de información.

---

# 3. Barómetro

El componente de barómetro debe mostrar la presión atmosférica como métrica principal.

No se utilizará una tabla como elemento principal.

### Información

* Presión actual
* Variación de presión
* Presión mínima
* Presión máxima

### Diseño

```text
BAROMETER

        1008.42
          hPa

       ↓ 0.8 hPa

MIN     1006.12
MAX     1012.83
```

La presión actual debe tener mayor jerarquía visual que el resto de los datos.

La presión incluye una mini línea de tendencia.

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

Cada eje incluye una gráfica de tendencia.

---

# 6. Salud de conexión

El componente de salud del enlace debe proporcionar una visión inmediata del estado de comunicación con el sistema remoto.

### Información

* Estado de conexión
* Número del último paquete enviado (secuencia)
* Cantidad de paquetes recibidos
* Cantidad de paquetes perdidos
* Tiempo desde el último paquete
* Tasa de recepción

### Diseño

```text
LINK HEALTH

● CONNECTED

SENT (SEQ)       18,452
RECEIVED         18,449
LOST                  3

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

El estado deberá ser identificable visualmente sin depender de otros valores.

---

# 7. GPS / Mapa

El mapa y las coordenadas comparten un panel de **6/12 columnas**.

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
│                     MAP                     │
│                 ●────●                      │
│                                             │
├─────────────────────────────────────────────┤
│ LATITUD                 LONGITUD             │
└─────────────────────────────────────────────┘
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

El componente muestra solo los hitos que atraviesa el cohete durante el vuelo.

Se registran únicamente las transiciones de etapa que atraviesa el cohete,
representadas como **etapa + tiempo de misión**. No se incluyen conexión,
pérdida de paquetes ni mensajes técnicos.

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

El primer estado recibido solo inicializa la etapa actual; el log comienza al
detectar una transición posterior.

---

# 9. Coordenadas GPS

Las coordenadas aparecen fuera del mapa en un panel propio:

* Latitud
* Longitud

Los datos técnicos del frame no se muestran en el dashboard.

---

# 10. Jerarquía visual

La interfaz debe priorizar la información en este orden:

1. **Estado del enlace**
2. **Altitud**
3. **Posición / mapa**
4. **Aceleración**
5. **Barómetro**
6. **Eventos de vuelo**
7. **Coordenadas GPS**

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
┌──────────┬──────────┬──────────┐
│ BARÓMETRO│ ALTITUD  │ ACELER.  │
├──────────┼──────────┼──────────┤
│ MAPA + COORDENADAS │ SALUD │ HITOS │
└────────────────────┴───────┴───────┘
```

En pantallas amplias, mapa+coordenadas/salud/hitos tienen proporción 6/3/3.
No hay panel de datos de frame.

---

# 13. Requisitos G7, G8 y G12

* **G7:** altitud y aceleración XYZ se grafican en tiempo real. Batería y tasas
  de giro quedan fuera hasta que exista una fuente definida.
* **G8:** tiempo de misión, GPS, paquetes recibidos/perdidos y estado del vuelo
  se muestran. Temperatura queda fuera por ahora.
* **G12:** tema claro de alto contraste para uso bajo luz solar; textos de al
  menos 14 pt y trazos/ejes de gráficos en negrita.

Las actualizaciones visuales se limitan a 10 Hz y suavizan los valores para
reducir saltos sin modificar los datos recibidos. Se mantiene fija la trama
binaria actual de 30 bytes. Temperatura, batería, giroscopio, RSSI y SNR no se
muestran ni se envían por ahora.

Los gráficos conservan escala fija para comparar lecturas entre actualizaciones:
presión **800–1100 hPa**, altitud **0–1200 m**, aceleración X/Y **−0,5 a +0,5 g**
y Z **−1,5 a +4,5 g**. Cada gráfico etiqueta esos límites y el tiempo de misión
correspondiente al primer y último dato visible.
