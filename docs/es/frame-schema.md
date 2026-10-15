# Especificación del Esquema Declarativo de Trama (YAML)

> **Idioma / Language:** [ 🇪🇸 Español ](frame-schema.md) | [ 🇬🇧 English ](../frame-schema.md)

---

## 1. Objetivo y Filosofía de Diseño

El motor de la Estación Terrena decodifica y valida tramas binarias de telemetría de forma completamente dinámica sin requerir ninguna modificación en el código fuente de Python.

Para lograr esto, el diseño de la trama se define declarativamente mediante un archivo YAML externo ([`config/frame.yaml`](../../config/frame.yaml)).

Durante la ejecución en tiempo real, el motor de la estación:

1. Carga el esquema de especificación de trama YAML.
2. Ingresa el flujo continuo de bytes binarios provenientes de la interfaz serie.
3. Identifica los límites de trama y valida su integridad mediante la longitud configurada y el algoritmo CRC.
4. Extrae los campos discretos según offsets en bytes, longitudes y tipos de datos primitivos.
5. Convierte los valores enteros crudos a unidades físicas de ingeniería aplicando escala lineal y desplazamientos ($y = ax + b$).
6. Mapea códigos de estado discretos a etiquetas legibles y entrega diccionarios estructurados a los motores de persistencia (SQLite/CSV) y difusión WebSocket.

> **Ventaja de Ingeniería:** Modificar la disposición de telemetría del cohete o incorporar nuevos sensores solo requiere editar el archivo YAML: **cero líneas de código Python deben modificarse**.

---

## 2. Estructura General del Esquema

El archivo declarativo se organiza en tres secciones fundamentales:

```yaml
name: "Definitive LoRa Telemetry Frame"
id: 1
description: "Trama de telemetría de 65 bytes con CRC-16 para enlace LoRa"

frame:
  length: 65
  byte_order: "little_endian"
  sync: "0xAA"

  crc:
    enabled: true
    algorithm: "CRC-16/CCITT-FALSE"
    polynomial: 0x1021
    initial_value: 0xFFFF
    final_xor: 0x0000
    reflect_input: false
    reflect_output: false
    offset: 63
    length: 2
    byte_order: "little_endian"
    calculate_from: 0
    calculate_to: 62

fields:
  - name: "sync"
    offset: 0
    length: 1
    type: "uint8"
    expected_value: 0xAA

  - name: "frame_number"
    offset: 1
    length: 2
    type: "uint16"

  - name: "timestamp"
    offset: 3
    length: 4
    type: "uint32"

  - name: "status"
    offset: 7
    length: 1
    type: "uint8"
    values:
      0: "STANDBY"
      1: "POWERED"
      3: "BURNOUT"
      7: "APOGEE"
      15: "DROGUE_ORD"
      31: "DROGUE_CONF"
      63: "MAIN_ORD"
      127: "MAIN_CONF"
      255: "LANDED"
  # Campos adicionales...
```

---

## 3. Sección `frame`: Propiedades Globales y Envoltura

Define las reglas de framing, sincronización y delimitación de paquetes:

| Clave | Tipo | Valor por Defecto | Descripción |
|---|---|---|---|
| `length` | Entero | Requerido | Longitud total exacta en bytes de cada trama completa ($65$). |
| `byte_order` | Cadena | `"little_endian"` | Orden de bytes predeterminado para campos de múltiples bytes (`"little_endian"` o `"big_endian"`). |
| `sync` | Cadena / Bytes | Opcional | Cabecera fija de sincronización (ej. `"0xAA"`). Utilizada por la ventana deslizante para descartar ruido previo. |
| `crc` | Diccionario | Opcional | Bloque de configuración del algoritmo de verificación por redundancia cíclica. |

### Configuración del Bloque `crc`

| Clave | Tipo | Descripción |
|---|---|---|
| `enabled` | Booleano | Habilita o deshabilita la verificación obligatoria de CRC (`true`/`false`). |
| `algorithm` | Cadena | Identificador del algoritmo (actualmente soporta `"CRC-16/CCITT-FALSE"` o `"CRC16CCITT"`). |
| `polynomial` | Entero | Polinomio generador hexadecimal (`0x1021`). |
| `initial_value` | Entero | Valor inicial del registro CRC (`0xFFFF`). |
| `final_xor` | Entero | Máscara XOR aplicada al resultado final (`0x0000`). |
| `offset` | Entero | Posición inicial en bytes donde se ubica el CRC dentro de la trama (`63`). |
| `length` | Entero | Tamaño en bytes del campo CRC ($2$ para CRC-16). |
| `byte_order` | Cadena | Orden de bytes con el que se empaqueta el CRC en el paquete (`"little_endian"`). |
| `calculate_from` | Entero | Byte inicial del rango sobre el cual se calcula el CRC ($0$). |
| `calculate_to` | Entero | Byte final inclusive sobre el cual se calcula el CRC ($62$). |

---

## 4. Sección `fields`: Definición de Variables y Métricas

La lista `fields` declara cada una de las variables empaquetadas en el payload.

### Atributos de Cada Campo

| Atributo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `name` | Cadena | **Sí** | Identificador único del campo en el diccionario de salida JSON y en columnas de CSV/SQLite. |
| `type` | Cadena | **Sí** | Tipo de dato binario primitivo (ver tabla de tipos). |
| `offset` | Entero | **Sí** | Desplazamiento en bytes desde el inicio de la trama ($0$-indexed). |
| `length` | Entero | Opcional | Longitud en bytes del campo. Obligatorio para tipo `bytes`; en otros tipos debe coincidir exactamente con el tamaño nativo. |
| `scale` | Flotante | No ($1.0$) | Factor multiplicador de conversión física ($y = \text{raw} \times \text{scale} + \text{offset\_value}$). |
| `offset_value` | Flotante | No ($0.0$) | Desplazamiento aditivo de calibración física. |
| `expected_value`| Entero | No | Valor exacto esperado en el campo. Si la trama recibida no coincide, el parser la descarta por corrupción. |
| `values` | Mapeo | No | Diccionario de enumeración (`código: "etiqueta"`). Genera automáticamente un campo adicional `{name}_label` en la salida. |

---

## 5. Tipos de Datos Primitivos Soportados

| Identificador | Tamaño | Formato `struct` Python | Descripción |
|---|---|---|---|
| `uint8` | $1\text{ byte}$ | `B` | Entero sin signo de 8 bits ($0$ a $255$). |
| `int8` | $1\text{ byte}$ | `b` | Entero con signo de 8 bits en complemento a 2 ($-128$ a $+127$). |
| `uint16` | $2\text{ bytes}$ | `H` | Entero sin signo de 16 bits ($0$ a $65,535$). |
| `int16` | $2\text{ bytes}$ | `h` | Entero con signo de 16 bits ($-32,768$ a $+32,767$). |
| `uint24` | $3\text{ bytes}$ | Personalizado | Entero sin signo de 24 bits ($0$ a $16,777,215$). |
| `int24` | $3\text{ bytes}$ | Personalizado | Entero con signo de 24 bits ($-8,388,608$ a $+8,388,607$). |
| `uint32` | $4\text{ bytes}$ | `I` | Entero sin signo de 32 bits ($0$ a $4,294,967,295$). |
| `int32` | $4\text{ bytes}$ | `i` | Entero con signo de 32 bits ($-2,147,483,648$ a $+2,147,483,647$). |
| `uint64` | $8\text{ bytes}$ | `Q` | Entero sin signo de 64 bits. |
| `int64` | $8\text{ bytes}$ | `q` | Entero con signo de 64 bits. |
| `float32` | $4\text{ bytes}$ | `f` | Número de coma flotante de precisión simple IEEE-754 ($\sim 7$ dígitos significativos). |
| `float64` | $8\text{ bytes}$ | `d` | Número de coma flotante de doble precisión IEEE-754 ($\sim 15$ dígitos significativos). |
| `bool` | $1\text{ byte}$ | `?` | Booleano lógico (`True` o `False`). |
| `bytes` | Variable | Personalizado | Secuencia de bytes crudos representada como cadena hexadecimal en la salida. |

---

## 6. Documentación Relacionada

- **[Especificación del Protocolo Binario](protocol.md):** Mapa de memoria detallado de la trama activa de 65 bytes.
- **[Arquitectura del Sistema](architecture.md):** Pipeline de procesamiento y despacho de eventos en tiempo real.
- **[Especificación de la API](api.md):** Esquemas de salida JSON consumidos por el frontend.
