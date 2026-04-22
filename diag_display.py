#!/usr/bin/env python3
"""
OLED display diagnostic for RPi5.
Tests SPI communication and SSD1351 initialization.

Usage:
    cd ~/PiFinder5
    source python/.venv/bin/activate
    python diag_display.py
"""

import os
import sys
import time
import traceback
import inspect

# Detect SPI port (RPi5 uses port 10)
SPI_PORT = 10 if os.path.exists("/dev/spidev10.0") and not os.path.exists("/dev/spidev0.0") else 0
SPI_DEVICE = 0

print("=== PiFinder OLED Display Diagnostic ===")
print(f"SPI devices: {[f for f in os.listdir('/dev') if 'spi' in f]}")
print(f"Using: /dev/spidev{SPI_PORT}.{SPI_DEVICE}")

# Step 1: raw SPI open
print("\n[1] Opening SPI device...")
try:
    import spidev
    spi_raw = spidev.SpiDev()
    spi_raw.open(SPI_PORT, SPI_DEVICE)
    spi_raw.max_speed_hz = 1_000_000
    spi_raw.writebytes([0x00])
    spi_raw.close()
    print("    OK - SPI device opened and write succeeded")
except Exception as e:
    print(f"    FAIL - {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: GPIO test — no cleanup so luma can reuse
print("\n[2] Testing GPIO pins...")
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    for pin in [24, 25, 27]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        GPIO.output(pin, GPIO.LOW)
        print(f"    GPIO {pin} - toggled OK")
    print("    (no cleanup — luma will reuse)")
except Exception as e:
    print(f"    FAIL - {e}")
    traceback.print_exc()

# Step 3: luma spi() default DC/RST pins
print("\n[3] Checking luma spi() default DC/RST pin numbers...")
try:
    from luma.core.interface.serial import spi as luma_spi
    sig = inspect.signature(luma_spi.__init__)
    dc  = sig.parameters.get("gpio_DC",  sig.parameters.get("dc",  None))
    rst = sig.parameters.get("gpio_RST", sig.parameters.get("rst", None))
    print(f"    luma default DC  pin: {dc.default  if dc  else 'unknown'}")
    print(f"    luma default RST pin: {rst.default if rst else 'unknown'}")
except Exception as e:
    print(f"    FAIL - {e}")

# Step 4: check available SPI devices
print("\n[4] Available SPI devices...")
spi_devs = sorted([f for f in os.listdir("/dev") if f.startswith("spidev")])
for d in spi_devs:
    print(f"    /dev/{d}")

# Step 5: try all combinations of CS device and DC pin
print("\n[5] Trying SSD1351 init — all CS/DC combinations...")
from luma.core.interface.serial import spi as luma_spi
from luma.oled.device import ssd1351
from PIL import Image, ImageDraw
import RPi.GPIO as GPIO

device = None
working_dc = None
working_cs = None

def try_rst(rst_pin):
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(rst_pin, GPIO.OUT)
        GPIO.output(rst_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(rst_pin, GPIO.HIGH)
        time.sleep(0.1)
    except Exception:
        pass

cs_devices = list(set([int(d.split(".")[1]) for d in spi_devs if d.startswith(f"spidev{SPI_PORT}.")]))
dc_pins = [24, 25, 27]
rst_pins = [25, 27, 24]

for cs in cs_devices:
    for dc_pin in dc_pins:
        rst_pin = next((p for p in rst_pins if p != dc_pin), 25)
        print(f"\n    --- CS=CE{cs}  DC=GPIO{dc_pin}  RST=GPIO{rst_pin} ---")
        try:
            try_rst(rst_pin)
            serial = luma_spi(device=cs, port=SPI_PORT,
                              bus_speed_hz=8_000_000, gpio_DC=dc_pin, gpio_RST=rst_pin)
            dev = ssd1351(serial, rotate=0, bgr=True)
            img = Image.new("RGB", (128, 128), (255, 0, 0))
            dev.display(img)
            print(f"    OK - initialized")
            print(f"    >>> OLED RED? (waiting 3s) <<<")
            time.sleep(3)
            answer = input(f"    Did you see RED? [y/n]: ").strip().lower()
            if answer == "y":
                device = dev
                working_dc = dc_pin
                working_cs = cs
                print(f"    ✓ FOUND: CS=CE{cs} DC=GPIO{dc_pin} RST=GPIO{rst_pin}")
                break
            else:
                try:
                    serial.cleanup()
                except Exception:
                    pass
        except Exception as e:
            print(f"    FAIL - {e!r}")
    if device:
        break

if device is None:
    print("\n=== RESULT: No combination worked ===")
    print("Hardware check needed:")
    print("  - Measure VCC pin on OLED (should be 3.3V)")
    print("  - Run: pinctrl get 7 8 9 10 11  (verify SPI pin modes)")
    print("  - Check OLED CS wire goes to GPIO8 (CE0) or GPIO7 (CE1)")
    sys.exit(1)

# Step 6: full color test
print(f"\n[6] Drawing test pattern with CS=CE{working_cs} DC=GPIO{working_dc}...")
colors = [
    ("Red",   (255,   0,   0)),
    ("Green", (  0, 255,   0)),
    ("Blue",  (  0,   0, 255)),
    ("White", (255, 255, 255)),
]
for name, rgb in colors:
    img = Image.new("RGB", (128, 128), rgb)
    device.display(img)
    print(f"    {name} {rgb} - displayed")
    time.sleep(1)

# Step 7: text
print("\n[7] Drawing text overlay...")
img = Image.new("RGB", (128, 128), (0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rectangle([0, 0, 127, 127], outline=(255, 255, 0))
draw.text((10, 50), "PiFinder", fill=(255, 255, 0))
draw.text((10, 65), f"CS={working_cs} DC={working_dc}", fill=(0, 255, 0))
device.display(img)
print("    Text drawn")

print(f"\n=== Diagnostic complete ===")
print(f"Working config: CS=CE{working_cs}, DC=GPIO{working_dc}")
print(f"Update displays.py: spi(device={working_cs}, port=_SPI_PORT, bus_speed_hz=40000000, gpio_DC={working_dc})")
