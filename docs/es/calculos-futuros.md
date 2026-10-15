# Referencia de Cálculos Matemáticos y Métricas Derivadas

> **Idioma / Language:** [ 🇪🇸 Español ](calculos-futuros.md) | [ 🇬🇧 English ](../calculos-futuros.md)

---

## 1. Objetivo y Alcance Técnico

Este documento recopila la especificación matemática de las métricas derivadas, algoritmos de fusión sensorial y filtros de estimación de estado que fueron retirados temporalmente del tablero en vivo (`frontend/index.html`).

Actualmente, el tablero de producción muestra **los valores directos de telemetría tal como son recibidos en la trama binaria**, garantizando la máxima fiabilidad y el menor retardo de procesamiento en operaciones de vuelo. Todas las estimaciones secundarias quedan documentadas aquí para su reintegración progresiva.

> **Implementación Histórica de Referencia:**
> El código funcional completo en JavaScript que implementa estos cálculos se encuentra archivado en [`docs/referencia/index_con_calculos.html`](../referencia/index_con_calculos.html). Puede ser probado sirviéndolo directamente o copiándolo sobre `frontend/index.html`.

---

## 2. Métricas Directas Actuales (Tablero de Producción)

El tablero actual procesa directamente:

| Instrumento | Campo Origen | Unidades y Conversión Física |
|---|---|---|
| **Altitud, Cinta, Apogeo y Gráfico** | `altitude` / `altura_actual` | Altitud barométrica/geométrica directa en metros ($m$). |
| **Barómetro** | `pressure` | Presión atmosférica convertida de $\text{Pa}$ a $\text{hPa}$ ($\times 0.01$). |
| **Aceleración Triaxial ($a_x, a_y, a_z$)** | `accel_x`, `accel_y`, `accel_z` | Aceleración en unidades de gravedad ($g$). |
| **Posición y Traza en Mapa** | `latitude`, `longitude` | Grados decimales WGS-84 ($^{\circ}$). |
| **Fase de Vuelo** | `status` | Códigos de la máquina de estados mapeados a `status_label`. |
| **Tiempo de Misión (MET)** | `timestamp` | Milisegundos formateados a `T+ HH:MM:SS`. |
| **Diagnóstico de Enlace** | `statistics` | Contadores acumulados y ventana deslizante de pérdida de paquetes. |

> **Métrica Combinada:**
> El tablero retiene la magnitud de la aceleración resultante total:
> $$G_{\text{total}} = \sqrt{a_x^2 + a_y^2 + a_z^2}$$

---

## 3. Algoritmos Matemáticos Extendidos (Reintegración Futura)

### 3.1 Altitud Barométrica y Filtro de Kalman 1D

#### Fórmula Barométrica Estándar:
$$h_{\text{baro}} = h_0 + 44330 \times \left(1 - \left(\frac{p}{p_0}\right)^{0.190295}\right)$$
donde $p_0$ y $h_0$ son la presión y altitud de referencia en plataforma calibradas antes del encendido del motor.

#### Filtro de Kalman 1D (Vector de Estado: $[h, v]^T$):
Fusiona la presión barométrica (alta frecuencia, baja latencia, deriva por turbulencia) con la altitud GPS (baja frecuencia, precisión absoluta sin deriva) para obtener una estimación óptima de altitud $h$ y velocidad vertical $v$.

1. **Vector de Estado y Matriz de Transición:**
   $$\mathbf{x} = \begin{bmatrix} h \\ v \end{bmatrix}, \quad \mathbf{F} = \begin{bmatrix} 1 & \Delta t \\ 0 & 1 \end{bmatrix}$$
   donde $\Delta t$ es el intervalo temporal entre tramas sucesivas ($\Delta t \le 1.0\text{ s}$).

2. **Paso de Predicción:**
   $$\hat{\mathbf{x}}_{k|k-1} = \mathbf{F} \hat{\mathbf{x}}_{k-1|k-1}$$
   Con varianza de ruido de proceso $q = 20\text{ (m/s²)}²$, la propagación de covarianza es:
   $$P_{00} \leftarrow P_{00} + \Delta t (P_{10} + P_{01}) + \Delta t^2 P_{11} + \frac{q \Delta t^4}{4}$$
   $$P_{01} \leftarrow P_{01} + \Delta t P_{11} + \frac{q \Delta t^3}{2}, \quad P_{10} \leftarrow P_{01}$$
   $$P_{11} \leftarrow P_{11} + q \Delta t^2$$

3. **Actualización Secuencial por Medición ($\mathbf{H} = [1 \quad 0]$):**
   - **Actualización Barométrica:** $R_{\text{baro}} = 4.0\text{ m}^2$.
   - **Actualización GPS:** $R_{\text{GPS}} = 25.0\text{ m}^2$.
   - Ganancia de Kalman: $\mathbf{K} = \mathbf{P} \mathbf{H}^T ( \mathbf{H} \mathbf{P} \mathbf{H}^T + R )^{-1}$.

---

### 3.2 Variómetro Barométrico ($V_z$)
Calculado por diferenciación numérica con filtro de media móvil o regresión lineal sobre los últimos 5 puntos temporales:
$$V_z(t) = \frac{\Delta h}{\Delta t}$$

---

### 3.3 Elipse de Dispersión de Aterrizaje
Estimación geométrica del área de impacto basada en la velocidad de descenso actual bajo paracaídas y el vector de viento medio:
$$x_{\text{impacto}} = x_{\text{actual}} + V_{\text{viento}, x} \times \frac{h_{\text{actual}}}{V_{\text{descenso}}}$$
$$y_{\text{impacto}} = y_{\text{actual}} + V_{\text{viento}, y} \times \frac{h_{\text{actual}}}{V_{\text{descenso}}}$$

---

## 4. Documentación Relacionada

- **[Especificación del Protocolo Binario](protocol.md):** Estructura de la trama de 65 bytes.
- **[Diseño del Frontend y Tablero](frontend-dashboard.md):** Guía de visualización y jerarquía.
- **[Implementación Histórica en JavaScript](../referencia/index_con_calculos.html):** Código fuente archivado.
