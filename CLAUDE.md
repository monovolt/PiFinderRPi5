# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Branch Model

- **`main`** is the integration / development branch. **All PRs target `main`.**
- **`release`** is the production branch — code is promoted from `main` to `release` as part of a release cut. Do not open PRs directly against `release`.
- Feature branches: branch off `main` and PR back to `main`.

Note: the auto-detected "Main branch" shown in the Claude Code env block may currently read `release` (because the GitHub default branch points there). Disregard that — the rule above is authoritative for this repo.

### Agent worktrees

Worktrees must be rooted on **`main`**. The harness's `fresh` base resolves to this clone's `origin/HEAD`, which may point at `release` (the GitHub default) — in which case `EnterWorktree` lands on `release`, not `main`. CLAUDE.md cannot change this; it is decided by the harness before any instruction here is read.

After `EnterWorktree`, **verify the base before making changes**: if `git merge-base HEAD origin/main` does not equal `origin/main`'s tip, the worktree is on the wrong branch — run `git reset --hard origin/main` and proceed from there.

Maintainers can make `fresh` root on `main` automatically per clone (without changing GitHub's default branch) by repointing the local default-branch pointer:

```bash
git remote set-head origin main
```

**Initialise the `tetra3` submodule in every new worktree.** `python/PiFinder/tetra3` is a git submodule (the `cedar-solve`/Tetra3 solver); the importable package is its inner `tetra3/tetra3/` dir, surfaced through the tracked symlink `python/tetra3`. `git worktree add` / `EnterWorktree` does **not** populate submodules, so a fresh worktree starts with an empty submodule dir and a dangling symlink. Any test that imports the solver then fails with `ModuleNotFoundError: No module named 'tetra3'` (or `cedar_detect_pb2`) — this is a missing checkout, **not** a code problem, so don't reach for `PYTHONPATH` hacks. Fix it once per worktree:

```bash
git submodule update --init python/PiFinder/tetra3
```

mypy also needs this: its config points at `python/PiFinder/tetra3/tetra3`, so `nox -s type_hints` can't run in a worktree until the submodule is initialised.

## Development Commands

**Running Python**
Developers may have created virtual environments in directories like ".venv" or "venv". Make sure these virtual
environments are activated before any of the python based tools below.

**Development workflow uses Nox for task automation:**
```bash
nox -s lint          # Code linting with Ruff (auto-fixes issues)
nox -s format        # Code formatting with Ruff
nox -s type_hints    # Type checking with MyPy
nox -s smoke_tests   # Quick functionality validation
nox -s unit_tests    # Full unit test suite
nox -s babel         # I18n message extraction and compilation
nox -s web_tests     # Testing the webserver, see below
```

**Direct testing with pytest:**
```bash
pytest -m smoke      # Smoke tests for core functionality
pytest -m unit       # Unit tests for isolated components
pytest -m integration # End-to-end integration tests
```

**Development setup:**
```bash
cd python/
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements_dev.txt
```
If the .venv dir already exists, you can directly source it and run the app.


Watch out for .venv directories containing virtual environments, that you need to activate first. 

**Running the application:**

First start the `cedar-detect-server` which is in `bin` (you need to use `-p 50551`, when invoking it).
Use the correct architecture suffix for cedar-detect-server according to the platform you're running on. 

Development setup has to have run and you should be in .venv virtual environment
```bash
cd python/
python -m PiFinder.main [options]
```
Usual startup:

```bash
python3.9 -m PiFinder.main -fh --camera debug --keyboard local -x
```

## Reference Documentation

Before working in an area of the codebase, check whether it has reference docs:

- **`CONTEXT-MAP.md`** (repo root) — index of bounded contexts and how they relate. Start here for any cross-context question.
- **`docs/ax/<area>/CONTEXT.md`** — canonical glossary for each context (Catalog, Positioning, SQM…). These define the project's vocabulary: what each domain term means, which words to avoid, and how related concepts compose. **Use these terms when reading, writing, and discussing code.**
- **`docs/ax/<area>.md`** — architecture deep-dives (data flow, lifecycle, gotchas) alongside each CONTEXT.md.
- **`docs/adr/NNNN-*.md`** — short architecture-decision records capturing the *why* behind non-obvious or hard-to-reverse choices.

When a `CONTEXT.md` defines a term, prefer that term over synonyms in code comments, commit messages, and PR descriptions. If you encounter language in code or chat that conflicts with a CONTEXT.md, flag it.

## Architecture Overview

**Multi-Process Design:** PiFinder uses a process-based architecture where each major subsystem runs in its own process, communicating via queues and shared state objects:

- **Main Process** (`main.py`) - UI event loop, menu system, user interaction
- **Camera Process** - Image capture from various camera types (Pi, ASI, debug)
- **Solver Process** - Plate solving using Tetra3/Cedar libraries for star pattern recognition
- **GPS Process** - Location/time via GPSD or UBlox direct interface
- **IMU Process** - Motion tracking with BNO055 sensor
- **Integrator Process** - Combines solver + IMU data for real-time positioning
- **Web Server Process** - Web interface and SkySafari integration as a telescope 
- **Position Server Process** - External protocol support

**State Management:**
- `SharedStateObj` - Process-shared state using multiprocessing managers
- `UIState` - UI-specific state management

**Database Layer:**
- SQLite backend (`astro_data/pifinder_objects.db`)
- `ObjectsDatabase` - Astronomical catalog management (NGC, Messier, etc.)
- `ObservationsDatabase` - Session logging and observation tracking
- Modular catalog import system supporting multiple astronomical databases

**Hardware Abstraction:**
- Camera interface supporting IMX296 (global shutter), IMX290/462, HQ cameras
- Display system for SSD1351 OLED and ST7789 LCD with night vision preservation using red channel only
- Hardware keypad with PWM brightness control
- GPS integration via GPSD or direct UBlox protocol
- IMU sensor integration for motion detection and telescope orientation

## Key Directories

- `python/PiFinder/` - Core application modules
- `python/PiFinder/ui/` - User interface components (menus, screens, charts)
- `python/PiFinder/db/` - Database abstraction layer
- `astro_data/` - Astronomical catalogs and object databases
- `python/tests/` - Test suite (smoke, unit, integration markers)
- `case/` - 3D printable enclosure files
- `docs/` - Documentation and build guides

## Configuration

**Config Files:**
- `default_config.json` - System defaults
- `~/PiFinder_data/config.json` - User settings
- Equipment profiles for telescopes and eyepieces
- Display, camera, GPS, and solver parameters

**Hardware Configuration:**
- Camera selection: Pi Camera, ASI cameras, debug mode
- Display type: OLED vs LCD with brightness/orientation settings
- Input method: hardware keypad, local keyboard, web interface
- GPS receiver: GPSD daemon vs direct UBlox protocol

## Testing Strategy

Tests use pytest with custom markers for different test types. The smoke tests provide quick validation while unit tests cover isolated functionality. Integration tests validate end-to-end workflows including the multi-process architecture.

**Key test areas:**
- Calculation utilities and coordinate transformations
- Catalog data validation and import processes
- Menu structure and navigation logic
- Multi-process logging and communication
- Hardware interface abstractions
- Website testing

### Website testing setup

**Testing Framework:** Uses Selenium WebDriver with Pytest for automated browser testing of the web interface

**Infrastructure Requirements:**
- Selenium Grid server at localhost:4444 (configurable via SELENIUM_GRID_URL environment variable). 
  This server is started outside of the test code, for maximum flexibility
- Chrome browser in headless mode for test execution
- Tests automatically skip if Selenium Grid is unavailable

**Test Coverage Areas:**
- **Web Interface** (`test_web_interface.py`): Basic page loading, image display, status table elements (Mode, coordinates, software version)
- **Location Management** (`test_web_locations.py`): Location CRUD operations, DMS coordinate entry, default switching, GPS integration via remote interface
- **Network Configuration** (`test_web_network.py`): WiFi settings form validation, network management, restart flows, modal dialogs
- **Remote Control** (`test_web_remote.py`): Authentication, virtual keypad, menu navigation, marking menus, API endpoint validation
- **Equipment Management** (`test_web_equipment.py`): Telescope and eyepiece CRUD operations, active equipment selection, form validation
- **Observation Tracking** (`test_web_observations.py`): Session list display, observation counters, detail pages, TSV export functionality

**Authentication:** All protected pages use default password "solveit"

**Responsive Testing:** Tests run on both desktop (1920x1080) and mobile (375x667) viewports

**API Integration:** Extensive use of `/api/current-selection` endpoint to validate UI state changes and ensure web interface accurately reflects PiFinder's internal state

**Helper Utilities:** Shared utilities in `web_test_utils.py` for login flows, key simulation, and state validation with recursive dictionary comparison

## Code Quality

- **Linting:** Ruff with Python 3.9 target, Black-compatible formatting
- **Type Checking:** MyPy with gradual typing adoption
- **Code Style:** 88-character line length, double quotes, space indentation
- **I18n Support:** Babel integration for multi-language UI

The codebase follows modern Python practices with type hints, comprehensive testing, and automated code quality checks integrated into the development workflow.

## RPi5 Fork - Key Differences from Upstream

This is a fork of the original PiFinder (RPi4) adapted for Raspberry Pi 5 / Raspberry Pi OS Bookworm.

**Repository:** `monovolt/PiFinderRPi5` (upstream: original PiFinder)
**Install directory on Pi:** `~/PiFinder5/`

### Raspberry Pi 5 Setup (Bookworm)

**Installation path on Pi:**
```bash
# Run as pifinder user
bash ~/PiFinder5/pifinder_setup.sh
```

**Service files use venv Python:**
- `pi_config_files/pifinder.service` → ExecStart uses `/home/pifinder/PiFinder5/python/.venv/bin/python`

**config.txt camera overlay (IMX462):**
```
dtoverlay=imx290,clock-frequency=74250000
```
Add under `[all]` section in `/boot/firmware/config.txt`.

### tetra3 / Cedar-Detect Submodule

Cedar-Detect runs as a **systemd service** (not spawned by PiFinder directly).

`solver.py` connects via gRPC using `PFCedarDetectClient` on port 50051.

`sys.path` in `solver.py` needs **two entries**:
```python
sys.path.append(str(utils.tetra3_dir))           # for `import tetra3`
sys.path.append(str(utils.tetra3_dir / "tetra3")) # for `import cedar_detect_client`
```

`utils.tetra3_dir` points to `../python/PiFinder/tetra3` (submodule root, NOT `tetra3/tetra3`).

If the submodule is not initialized:
```bash
git submodule update --init --recursive
```

### GPS Configuration

- Default baud rate: 9600 (standard GPSD)
- UBlox-10 supports 115200 — set via **Settings > Advanced > GPS Settings > GPS Baud Rate** (do NOT edit `/etc/default/gpsd` directly — PiFinder overwrites it at startup)
- `gps_gpsd.py` uses synchronous streaming (asyncio removed)
- Lock thresholds: `lock_at=6000`, `fix_2d=4000`, `fix_3d=1000` (ms)
- GPS device: `/dev/ttyAMA2` (uart2 overlay, GPIO4=TXD2, GPIO5=RXD2)

### RPi5 UART vs SPI Pin Conflict (Critical)

On RPi5 (RP1 chip), UART overlay GPIO assignments differ from RPi4:

| Overlay | RPi4 GPIO | RPi5 GPIO | Device |
|---------|-----------|-----------|--------|
| uart2 | GPIO0/1 | **GPIO4/5** | /dev/ttyAMA2 |
| uart3 | GPIO4/5 | **GPIO8/9** | /dev/ttyAMA3 |

`dtoverlay=uart3` on RPi5 **steals SPI0 pins** (GPIO8=CE0, GPIO9=MISO) → SPI driver fails to initialize → OLED goes blank.

**Fix**: Use `dtoverlay=uart2` (not uart3). The PiFinder v3 SMT board PCB traces GPS TX/RX to GPIO4/5.

Verified working pin state after `dtoverlay=uart2`:
```
GPIO4:  TXD2  (GPS UART TX)
GPIO5:  RXD2  (GPS UART RX)
GPIO8:  output (SPI CE0, luma-controlled)
GPIO9:  SPI0_MISO
GPIO10: SPI0_MOSI
GPIO11: SPI0_SCLK
```

### RPi5 Bookworm Fixes Applied

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| OLED blank | `uart3` conflicts with SPI on RPi5 | Changed to `uart2` in setup.sh |
| IMU crash | Duplicate `imu = Imu()` in `imu_pi.py` line 196 | Removed duplicate call |
| IMU AttributeError | `ImuFake` missing `calibration` attribute | Added `self.calibration = 0` |
| UISQM ImportError | `ui/sqm/` directory shadowed `ui/sqm.py` | Renamed to `ui/sqm_ui.py` |
| No `/dev/i2c-*` | Bookworm doesn't auto-load `i2c-dev` module | `modprobe i2c-dev` + `/etc/modules` |
| SPI port | RPi5 RP1 chip exposes SPI as `/dev/spidev10.0` | Auto-detect in `displays.py` via `_SPI_PORT` |
| Camera white screen (IMX462) | RPi5 PiSP raw format left-alignment (see below) | `raw_bit_shift=4` + `bias_offset=240` in camera profile |

### RPi5 PiSP Camera Raw Format (IMX462 White Screen Fix)

**Symptom:** Focus screen shows entirely white/bright image even at night. Stars barely visible. Plate solving fails.

**Root cause:** On RPi5, the PiSP camera pipeline stores 12-bit sensor values **left-aligned** in 16-bit words (SRGGB12_1X12 → RG16 CFE format). Raw uint16 values are therefore 16× the actual sensor ADU values. The original code assumed right-aligned values, causing every pixel to calculate as 238–255/255 → all white.

Confirmed via `diag_camera.py`:
```
Raw uint16: min=3632, max=5632, mean=3847  ← max > 4095 proves left-alignment
12-bit ADU: min=227,  max=352,  mean=240   ← actual sensor values after >>4
```

**Fix applied** (`python/PiFinder/sqm/camera_profiles.py` + `python/PiFinder/camera_pi.py`):
- Added `raw_bit_shift: int = 0` field to `CameraProfile` dataclass
- Set `raw_bit_shift=4` for IMX462 and IMX290 profiles (16 − 12 = 4 bits)
- Updated `bias_offset` from 50 → **240** ADU (measured actual dark-frame pedestal)
- In `camera_pi.py` `capture()`: apply `raw_capture >> self.profile.raw_bit_shift` before scaling
- Default `analog_gain` reduced from 30 → **10** (IMX462 STARVIS is extremely sensitive; 30× at 400ms causes overexposure)

**Diagnostic tool:** `diag_camera.py` at repo root — captures dark frame and live frame, auto-detects left-aligned format, reports sensor health.

### Optional Dependencies

- **PyIndi** (`mountcontrol_indi`): Only loaded when INDI mount control is active. Import is conditional in `main.py` — no startup error if not installed.

### WiFi Management

Uses **NetworkManager** (not wpa_supplicant) on Bookworm. `sys_utils.py` WiFi functions updated accordingly.

### Known Pending Items

- `sys_utils.py:47` `isAP()` is missing `@staticmethod` decorator

## v2.6.0 Upstream Merge (2026-06-26)

Merged upstream PiFinder v2.6.0 (48+ commits) into RPi5 fork. Common ancestor: `121ef12` (v2.5.1).

**Key RPi5-specific decisions during merge:**

| File | Decision |
|------|----------|
| `displays.py` | Added `_SPI_PORT` to new `DisplaySSD1333` class |
| `solver.py` | Took upstream `PFCedarDetectClient` (checks service → falls back to spawn). Kept tetra3 double sys.path. Removed duplicate class from fork. |
| `utils.py` | Took upstream file-anchored `pifinder_dir` resolution but kept `tetra3_dir` pointing to outer submodule dir (NOT `tetra3/tetra3`). |
| `sqm/camera_profiles.py` | Auto-merged. RPi5 `raw_bit_shift`, `bias_offset=240`, `analog_gain=10` preserved. |
| `camera_pi.py` | Auto-merged. RPi5 raw_bit_shift block + saved_gain preserved. |
| `composite_object.py` | Combined both: `catalog_code in ("PL", "Str", "OBS")` |
| `sys_utils.py` | Kept `wpa_cli` import removed (NetworkManager). Added both mount control functions AND new NixOS migration functions. |
| `callbacks.py` | Kept `sync_time_from_pi()` + added upstream `set_time()` |
| `menu_structure.py` | Kept "Set Time from Pi" + added upstream "Set Time/Date" (UITimeEntry) |
| `requirements.txt` | luma.oled 3.15.0, luma.lcd 2.13.0 (RPi5 versions), added numpy-quaternion |

**New in v2.6.0 (upstream):** Polar alignment, daytime align, EQ mount/quaternion IMU, focus HFD, contrast reserve, multi-format obslist import, Lynga catalog, SQM calibration UI, Flask/Jinja web rewrite, REST API, 10x faster startup.
