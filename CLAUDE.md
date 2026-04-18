# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Development workflow uses Nox for task automation:**
```bash
nox -s lint          # Code linting with Ruff (auto-fixes issues)
nox -s format        # Code formatting with Ruff
nox -s type_hints    # Type checking with MyPy
nox -s smoke_tests   # Quick functionality validation
nox -s unit_tests    # Full unit test suite
nox -s babel         # I18n message extraction and compilation
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


**Running the application:**
Development setup has to have run and you should be in .venv virtual environment
```bash
cd python/
python -m PiFinder.main [options]
```
Usual startup:

```bash
python3.9 -m PiFinder.main -fh --camera debug --keyboard local -x
```

## Architecture Overview

**Multi-Process Design:** PiFinder uses a process-based architecture where each major subsystem runs in its own process, communicating via queues and shared state objects:

- **Main Process** (`main.py`) - UI event loop, menu system, user interaction
- **Camera Process** - Image capture from various camera types (Pi, ASI, debug)
- **Solver Process** - Plate solving using Tetra3/Cedar libraries for star pattern recognition
- **GPS Process** - Location/time via GPSD or UBlox direct interface
- **IMU Process** - Motion tracking with BNO055 sensor
- **Integrator Process** - Combines solver + IMU data for real-time positioning
- **Web Server Process** - Web interface and SkySafari telescope control integration
- **Position Server Process** - External protocol support

**State Management:**
- `SharedStateObj` - Process-shared state using multiprocessing managers
- `UIState` - UI-specific state management
- Real-time synchronization of telescope position, GPS coordinates, and solved sky coordinates

**Database Layer:**
- SQLite backend (`astro_data/pifinder_objects.db`)
- `ObjectsDatabase` - Astronomical catalog management (NGC, Messier, etc.)
- `ObservationsDatabase` - Session logging and observation tracking
- Modular catalog import system supporting multiple astronomical databases

**Hardware Abstraction:**
- Camera interface supporting IMX296 (global shutter), IMX290/462, HQ cameras
- Display system for SSD1351 OLED and ST7789 LCD with red-light preservation
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
- UBlox-10 supports 115200 — set via Settings > Advanced > GPS Settings > GPS Baud Rate
- `gps_gpsd.py` uses synchronous streaming (asyncio removed)
- Lock thresholds: `lock_at=6000`, `fix_2d=4000`, `fix_3d=1000` (ms)

### Optional Dependencies

- **PyIndi** (`mountcontrol_indi`): Only loaded when INDI mount control is active. Import is conditional in `main.py` — no startup error if not installed.

### WiFi Management

Uses **NetworkManager** (not wpa_supplicant) on Bookworm. `sys_utils.py` WiFi functions updated accordingly.

### Known Pending Items

- `sys_utils.py:47` `isAP()` is missing `@staticmethod` decorator
