# Inventario de Archivos Reorganizados y Propuestos para Limpieza

> **Idioma / Language:** [ 🇪🇸 Español ](pending-deletions-list.md) | [ 🇬🇧 English ](../pending-deletions-list.md)

> **Instrucción Directa del Usuario:**
> *"Todo lo que necesites borrar agrégalo a una lista y lo vemos mañana. Opera con la máxima autonomía que puedas."*
> Este documento registra todos los archivos reubicados, preparados para eliminación o propuestos para limpieza en el marco de la reorganización del repositorio y la unificación bilingüe de la documentación.

---

## 1. Resumen de Acciones y Eliminaciones Propuestas

| Archivo / Directorio | Ubicación Original | Acción Realizada / Propuesta | Nueva Ubicación | Justificación y Seguridad |
|---|---|---|---|---|
| **`config.md`** | Raíz (`/config.md`) | Eliminado de raíz / Migrado | [`docs/es/frame-schema.md`](frame-schema.md) | Estandariza la documentación dentro de `docs/`. El contenido se amplió para cubrir el esquema activo de trama de 65 bytes (`config/frame.yaml`). |
| **`front.md`** | Raíz (`/front.md`) | Eliminado de raíz / Migrado | [`docs/es/frontend-dashboard.md`](frontend-dashboard.md) | Estandariza la documentación visual dentro de `docs/`. Actualizado con especificaciones completas de instrumentos y jerarquía ergonómica. |
| **`test_telemetry_65b.py`** | Raíz (`/test_telemetry_65b.py`) | Reubicado en paquete dedicado | [`tests/test_telemetry_65b.py`](../../tests/test_telemetry_65b.py) | Los proyectos de software requieren tests dentro de una carpeta `tests/` con `__init__.py`. La suite fue ampliada a 8 verificaciones automatizadas. |
| **`.agents/`** | Raíz (`/.agents/`) | Ignorado en `.gitignore` | N/A (caché local) | Registros de agentes internos. No deben ingresar al historial de control de versiones. |
| **`data/telemetry.*`** | `data/telemetry.csv`, `data/telemetry.db*` | Ignorado en `.gitignore` | Carpeta local `data/` (preservada en disco) | Archivos de telemetría de misiones generados en tiempo de ejecución. Preservados localmente pero excluidos del repositorio para evitar sobrecarga binaria. |

---

## 2. Lista de Verificación para Revisión

- [ ] **Elemento 1:** Aprobar eliminación definitiva de `/config.md` (reemplazado por `docs/frame-schema.md` y `docs/es/frame-schema.md`).
- [ ] **Elemento 2:** Aprobar eliminación definitiva de `/front.md` (reemplazado por `docs/frontend-dashboard.md` y `docs/es/frontend-dashboard.md`).
- [ ] **Elemento 3:** Aprobar reubicación de `test_telemetry_65b.py` a `tests/test_telemetry_65b.py`.
- [ ] **Elemento 4:** Confirmar reglas de `.gitignore` para bases de datos SQLite en `data/` y bloqueos temporales de escritura.
