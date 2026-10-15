# Pending Cleanups & File Deletion Inventory

> **Language / Idioma:** [ 🇬🇧 English ](pending-deletions-list.md) | [ 🇪🇸 Español ](es/pending-deletions-list.md)

> **User Direct Instruction Note:**
> *"Todo lo que necesites borrar agrégalo a una lista y lo vemos mañana. Opera con la máxima autonomía que puedas."*
> This document records all files relocated, staged for deletion, or proposed for cleanup as part of the repository reorganization and documentation unification effort. Review this list to verify all proposed removals before final commit/merge.

---

## 1. Summary of Actions & Proposed Deletions

| File / Directory | Original Location | Action Taken / Proposed | New Location | Rationale & Safety Impact |
|---|---|---|---|---|
| **`config.md`** | Repository root (`/config.md`) | Staged for removal / Migrated | [`docs/frame-schema.md`](frame-schema.md) | Standardizes documentation under `docs/`. Content expanded to cover the definitive 65-byte LoRa telemetry frame schema (`config/frame.yaml`). Root file is no longer needed. |
| **`front.md`** | Repository root (`/front.md`) | Staged for removal / Migrated | [`docs/frontend-dashboard.md`](frontend-dashboard.md) | Standardizes UI documentation under `docs/`. Upgraded with complete visual hierarchy, telemetry instrument descriptions, and updated hyperlinks. |
| **`test_telemetry_65b.py`** | Repository root (`/test_telemetry_65b.py`) | Removed from root / Relocated | [`tests/test_telemetry_65b.py`](../tests/test_telemetry_65b.py) | Python repositories require tests to reside in a dedicated `tests/` directory with `tests/__init__.py`. Test suite expanded to 8 automated verification tests (fragmentation, false syncs, packet loss metrics). |
| **`.agents/`** | Repository root (`/.agents/`) | Added to `.gitignore` | N/A (local cache) | Internal AI agent workspace logs and intermediate cache. Should never be committed to source control. |
| **`data/telemetry.*`** | `data/telemetry.csv`, `data/telemetry.db`, `data/*.db-journal` | Added to `.gitignore` | Local data folder (preserved on disk) | Live mission telemetry logs generated at runtime. Retained locally for flight data integrity but excluded from Git history to prevent database bloat. |

---

## 2. Detailed Review of Each Item

### 2.1 `config.md` (Root)
- **Status:** Staged deletion in Git (`deleted: config.md`).
- **Destination:** [`docs/frame-schema.md`](frame-schema.md).
- **Why it was changed:**
  - The repository had loose markdown files scattered in the project root.
  - The content was focused on the declarative YAML schema for telemetry frames.
  - The documentation was rewritten in clean technical English, synchronized with the active 65-byte LoRa packet structure (`config/frame.yaml`), and cross-referenced with `docs/protocol.md` and `docs/architecture.md`.
- **Action for Tomorrow:** Confirm permanent deletion from repository root.

---

### 2.2 `front.md` (Root)
- **Status:** Staged deletion in Git (`deleted: front.md`).
- **Destination:** [`docs/frontend-dashboard.md`](frontend-dashboard.md).
- **Why it was changed:**
  - The file contained notes and layout specifications for the telemetry frontend dashboard (`frontend/index.html` and `frontend/gonogo.html`).
  - Moved into `docs/frontend-dashboard.md` alongside the rest of the documentation suite.
  - Updated with instrument tables, ergonomic considerations, high-contrast mission theme guidelines, and cross-links to `docs/api.md` and `docs/future-calculations.md`.
- **Action for Tomorrow:** Confirm permanent deletion from repository root.

---

### 2.3 `test_telemetry_65b.py` (Root)
- **Status:** Staged deletion from root; recreated under `tests/`.
- **Destination:** [`tests/test_telemetry_65b.py`](../tests/test_telemetry_65b.py).
- **Why it was changed:**
  - Running automated tests in standard Python tooling (e.g. `python -m unittest discover tests` or `pytest`) requires test modules inside a dedicated `tests/` package.
  - Keeping standalone test scripts in the project root creates confusion for new contributors.
  - The test suite was upgraded with `TestTelemetry65BSuite(unittest.TestCase)` runner and 8 verification tests (100% pass rate).
  - Both `.github/workflows/build-exe.yml` and `build_windows.bat` now run `python -m unittest discover tests` before compiling executables.
- **Action for Tomorrow:** Confirm permanent relocation to `tests/`.

---

### 2.4 Internal & Runtime Logs (`.agents/`, `data/*.db-journal`)
- **Status:** Added to `.gitignore`.
- **Files Affected:**
  - `.agents/`
  - `data/*.db-journal`
  - `data/*.db-wal`
  - `data/*.db-shm`
  - `/data/*.csv`
  - `/data/*.db`
- **Why it was changed:**
  - The active FastAPI ground station creates temporary SQLite journal files (`telemetry.db-journal`) while receiving live data.
  - Previously, `git status` showed untracked database files and SQLite journal locks.
  - Updated `.gitignore` ensures a pristine `git status` without untracked runtime artifacts.
- **Action for Tomorrow:** Keep ignored in `.gitignore`.

---

## 3. Review Checklist for Tomorrow

- [ ] **Item 1:** Approve deletion of `/config.md` (Replaced by `docs/frame-schema.md`).
- [ ] **Item 2:** Approve deletion of `/front.md` (Replaced by `docs/frontend-dashboard.md`).
- [ ] **Item 3:** Approve deletion of `/test_telemetry_65b.py` (Replaced by `tests/test_telemetry_65b.py`).
- [ ] **Item 4:** Confirm `.gitignore` patterns for `data/` telemetry databases and runtime journal files.
