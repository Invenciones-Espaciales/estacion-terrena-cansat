# Esquema genérico de definición de tramas

## 1. Objetivo

El sistema de la estación terrena debe poder interpretar diferentes tipos de tramas sin modificar el código del programa.

Para lograrlo, cada trama se describe mediante un archivo YAML externo.

El programa de la PC:

1. Carga la definición YAML.
2. Recibe los bytes mediante el puerto serie.
3. Identifica y valida la trama.
4. Extrae los campos según la definición.
5. Convierte los valores crudos a valores físicos.
6. Entrega los datos interpretados al resto de la aplicación.

De esta forma, modificar el formato de una trama requiere modificar únicamente su archivo de definición.

---

# 2. Estructura general

Una definición de trama tiene la siguiente estructura:

```yaml
name: "Nombre de la trama"
id: 1
description: "Descripción"

frame:
  length: 30
  byte_order: "big_endian"

  crc:
    ...

fields:
  - ...
```

Está dividida en tres componentes principales:

* **Identificación de la trama**
* **Configuración general de la trama**
* **Definición de los campos**

---

# 3. Identificación

## `name`

Nombre legible de la trama.

```yaml
name: "Trama A"
```

Es metadato: el parser actual no usa este valor para seleccionar una trama ni
compararlo automáticamente con un campo.

---

## `id`

Identificador numérico de la trama.

```yaml
id: 1
```

Debe coincidir con el campo utilizado por el protocolo para identificar el tipo de trama.

Por ejemplo:

```text
0x01 → Trama A
0x02 → Trama B
0x03 → Trama C
```

---

## `description`

Descripción opcional de la trama.

```yaml
description: "Telemetría de alta frecuencia"
```

Sirve como documentación; el parser no lo agrega a los datos de telemetría.

---

# 4. Configuración de la trama

La sección `frame` contiene las propiedades generales del paquete.

```yaml
frame:
  length: 30
  byte_order: "big_endian"
```

## `length`

Cantidad total de bytes de la trama.

```yaml
length: 30
```

En este ejemplo la trama completa ocupa 30 bytes.

El parser debe utilizar este valor para determinar cuándo recibió una trama completa.

---

## `byte_order`

Define el orden de los bytes para los campos que ocupan más de un byte.

Valores posibles:

```yaml
byte_order: "big_endian"
```

o:

```yaml
byte_order: "little_endian"
```

En `big_endian`, el byte más significativo aparece primero.

Ejemplo:

```text
0x01 0x9F
```

representa:

```text
0x019F = 415
```

---

# 5. CRC

La sección `crc` define cómo validar la integridad de la trama.

Ejemplo:

```yaml
crc:
  enabled: true
  algorithm: "CRC-16/CCITT-FALSE"
  polynomial: 0x1021
  initial_value: 0xFFFF
  final_xor: 0x0000
  reflect_input: false
  reflect_output: false

  offset: 28
  length: 2
  byte_order: "big_endian"

  calculate_from: 0
  calculate_to: 27
```

## `enabled`

Indica si la trama utiliza CRC.

```yaml
enabled: true
```

---

## `algorithm`

Nombre del algoritmo utilizado.

```yaml
algorithm: "CRC-16/CCITT-FALSE"
```

El nombre permite identificar rápidamente el algoritmo, mientras que los parámetros siguientes permiten implementarlo de forma determinista.

---

## `polynomial`

Polinomio utilizado por el algoritmo.

```yaml
polynomial: 0x1021
```

---

## `initial_value`

Valor inicial del cálculo.

```yaml
initial_value: 0xFFFF
```

---

## `final_xor`

Valor aplicado mediante XOR al resultado final.

```yaml
final_xor: 0x0000
```

---

## `reflect_input`

Indica si los bits de entrada deben reflejarse.

```yaml
reflect_input: false
```

---

## `reflect_output`

Indica si los bits del resultado deben reflejarse.

```yaml
reflect_output: false
```

---

## `offset`

Posición del primer byte correspondiente al CRC.

```yaml
offset: 28
```

En la trama de ejemplo:

```text
Byte 28 → CRC MSB
Byte 29 → CRC LSB
```

---

## `length`

Cantidad de bytes utilizados por el CRC.

```yaml
length: 2
```

---

## `byte_order`

Orden de los bytes del CRC.

```yaml
byte_order: "big_endian"
```

---

## `calculate_from`

Primer byte incluido en el cálculo.

```yaml
calculate_from: 0
```

---

## `calculate_to`

Último byte incluido en el cálculo.

```yaml
calculate_to: 27
```

Por lo tanto, el CRC se calcula sobre:

```text
Byte 0 ──────────────── Byte 27
        datos de trama
```

Los bytes 28 y 29 contienen el CRC recibido y no participan en su propio cálculo.

---

# 6. Campos

La sección `fields` contiene la definición de cada dato presente en la trama.

Ejemplo:

```yaml
fields:

  - name: "rocket_id"
    offset: 0
    length: 1
    type: "uint8"
```

Cada campo posee una posición, tamaño y tipo.

---

# 7. `name`

Nombre interno del campo.

```yaml
name: "rocket_id"
```

Este nombre será utilizado por el software.

Por ejemplo, después del procesamiento podríamos obtener:

```python
data["rocket_id"]
```

---

# 8. `description`

Descripción del campo.

```yaml
description: "Identificador del cohete"
```

Es opcional y sirve para documentación, interfaces gráficas y mantenimiento.

---

# 9. `offset`

Posición del primer byte del campo dentro de la trama.

```yaml
offset: 8
```

La numeración comienza en cero.

Ejemplo:

```text
Byte 0
Byte 1
Byte 2
...
Byte 8  ← inicio del campo
Byte 9
```

---

# 10. `length`

Cantidad de bytes ocupados por el campo.

```yaml
length: 2
```

Por ejemplo:

```yaml
offset: 8
length: 2
```

significa:

```text
Byte 8
Byte 9
```

---

# 11. `type`

Define cómo interpretar los bytes.

Tipos implementados:

```text
uint8
int8

uint16
int16

uint24
int24

uint32
int32

uint64
int64

float32
float64

bytes
```

Los tipos enteros pueden utilizar `byte_order` de la trama. Los campos
`bytes` requieren declarar `length` y se entregan como una cadena hexadecimal.
El largo declarado debe coincidir con el tamaño fijo del tipo en los demás
casos.

---

# 12. Escalado

Los datos transmitidos pueden ser valores enteros que posteriormente deben convertirse a valores físicos.

Para esto se utiliza:

```yaml
scale: 0.1
```

La conversión se realiza conceptualmente como:

```text
valor_físico = valor_crudo × scale
```

Ejemplo:

```yaml
type: "int16"
scale: 0.1
unit: "°C"
```

Si se recibe:

```text
185
```

el resultado será:

```text
18.5 °C
```

---

# 13. Offset físico

Además de escala, puede existir un desplazamiento:

```yaml
scale: 0.1
offset_value: -40
```

La conversión será:

```text
valor_físico =
    valor_crudo × scale
    + offset_value
```

Por ejemplo:

```text
valor_crudo = 500
scale = 0.1
offset = -40

500 × 0.1 - 40 = 10 °C
```

Esto permite representar sensores que utilizan fórmulas de conversión simples.

---

# 14. Unidad

El campo `unit` define la unidad del valor ya convertido.

Ejemplos:

```yaml
unit: "g"
```

```yaml
unit: "Pa"
```

```yaml
unit: "m"
```

```yaml
unit: "deg"
```

La unidad no modifica el valor. Es información utilizada por la aplicación, principalmente para mostrar los datos.

---

# 15. Valores enumerados

Algunos campos representan estados en lugar de valores físicos.

Para estos casos se puede utilizar `values`.

Ejemplo:

```yaml
- name: "status"
  offset: 27
  length: 1
  type: "uint8"

  values:
    0x00: "Standby"
    0x01: "Pre-launch"
    0x02: "Motor encendido / Ascenso"
    0x03: "Apogeo"
    0x04: "Descenso"
    0x05: "Aterrizaje"
```

Si la PC recibe:

```text
0x02
```

el resultado conserva el valor numérico en `status` y agrega la etiqueta
correspondiente en `status_label`:

```text
status = 2
status_label = "Motor encendido / Ascenso"
```

Si no existe una etiqueta para un valor recibido, `status_label` será `null`.

---

# 16. Valores esperados

Algunos campos pueden utilizarse para identificar o validar una trama.

Por ejemplo:

```yaml
- name: "frame_type"
  offset: 1
  length: 1
  type: "uint8"
  expected_value: 0x01
```

El parser debe comprobar que el valor recibido sea `0x01`.

Esto permite descartar paquetes que no corresponden a la definición cargada.

---

# 17. Comportamiento del parser

Los `offset` de los campos y del CRC se cuentan desde el byte cero de la trama
completa. El parser valida el tamaño total, el CRC y todos los campos con
`expected_value` antes de entregar los datos.

Los campos numéricos se convierten con `raw × scale + offset_value`. `values`
agrega una clave `<nombre>_label` sin reemplazar el valor numérico. `unit` y
`description` son metadatos: el parser no los agrega al objeto de telemetría.

El lector acepta `fields` en el nivel raíz, como en este documento, y también
`frame.fields` para definiciones anteriores. La secuencia se toma de
`frame.sequence_field`; si no está declarada, se detecta `frame_number` o
`sequence`.

Para CRC-16/CCITT-FALSE se admiten `polynomial`, `initial_value` y `final_xor`.
La reflexión de entrada y salida debe estar desactivada. El rango
`calculate_from`–`calculate_to` es inclusivo.

---

# 18. Ejemplo completo

Una definición completa podría ser:

```yaml
name: "Trama A"
id: 1
description: "Telemetría de alta frecuencia"

frame:
  length: 30
  byte_order: "big_endian"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false
    offset: 28
    length: 2
    byte_order: "big_endian"
    calculate_from: 0
    calculate_to: 27

fields:
  - name: "rocket_id"
    offset: 0
    length: 1
    type: "uint8"

  - name: "frame_type"
    offset: 1
    length: 1
    type: "uint8"
    expected_value: 0x01

  - name: "frame_number"
    offset: 2
    length: 2
    type: "uint16"

  - name: "timestamp"
    offset: 4
    length: 4
    type: "uint32"
    unit: "ms"

  - name: "accel_x"
    offset: 8
    length: 2
    type: "int16"
    scale: 0.001
    offset_value: 0
    unit: "g"

  - name: "accel_y"
    offset: 10
    length: 2
    type: "int16"
    scale: 0.001
    offset_value: 0
    unit: "g"

  - name: "accel_z"
    offset: 12
    length: 2
    type: "int16"
    scale: 0.0005
    offset_value: 0
    unit: "g"

  - name: "pressure"
    offset: 14
    length: 3
    type: "uint24"
    unit: "Pa"

  - name: "latitude"
    offset: 17
    length: 4
    type: "int32"
    scale: 0.000001
    unit: "deg"

  - name: "longitude"
    offset: 21
    length: 4
    type: "int32"
    scale: 0.000001
    unit: "deg"

  - name: "altitude"
    offset: 25
    length: 2
    type: "int16"
    unit: "m"

  - name: "status"
    offset: 27
    length: 1
    type: "uint8"
    values:
      0x00: "Standby"
      0x01: "Pre-launch"
      0x02: "Motor encendido / Ascenso"
      0x03: "Apogeo"
      0x04: "Descenso"
      0x05: "Aterrizaje"
```
