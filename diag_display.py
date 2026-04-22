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

# Step 4: try SSD1351 with each likely DC pin
print("\n[4] Trying SSD1351 init with different DC pins (24, 25, 27)...")
from luma.core.interface.serial import spi as luma_spi
from luma.oled.device import ssd1351
from PIL import Image, ImageDraw

device = None
working_dc = None

for dc_pin in [24, 25, 27]:
    print(f"\n    --- DC=GPIO{dc_pin} ---")
    try:
        serial = luma_spi(device=SPI_DEVICE, port=SPI_PORT,
                          bus_speed_hz=8_000_000, gpio_DC=dc_pin)
        dev = ssd1351(serial, rotate=0, bgr=True)

        # Draw a bright red screen and wait
        img = Image.new("RGB", (128, 128), (255, 0, 0))
        dev.display(img)
        print(f"    OK - initialized with DC=GPIO{dc_pin}")
        print(f"    >>> Does the OLED show RED now? (waiting 3s) <<<")
        time.sleep(3)

        answer = input(f"    Did you see RED on the OLED? [y/n]: ").strip().lower()
        if answer == "y":
            device = dev
            working_dc = dc_pin
            print(f"    ✓ Working DC pin found: GPIO{dc_pin}")
            break
        else:
            serial.cleanup()
    except Exception as e:
        print(f"    FAIL - {e!r}")
        traceback.print_exc()

if device is None:
    print("\n=== RESULT: No DC pin worked — check wiring ===")
    print("Verify: MOSI=GPIO10, SCLK=GPIO11, CS=GPIO8(CE0), VCC=3.3V, GND")
    sys.exit(1)

# Step 5: full color test
print(f"\n[5] Drawing test pattern with DC=GPIO{working_dc}...")
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

# Step 6: text
print("\n[6] Drawing text overlay...")
img = Image.new("RGB", (128, 128), (0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rectangle([0, 0, 127, 127], outline=(255, 255, 0))
draw.text((10, 50), "PiFinder", fill=(255, 255, 0))
draw.text((10, 65), f"DC=GPIO{working_dc}", fill=(0, 255, 0))
device.display(img)
print("    Text drawn")

print(f"\n=== Diagnostic complete ===")
print(f"Working DC pin: GPIO{working_dc}")
print(f"Update displays.py: spi(..., gpio_DC={working_dc})")
