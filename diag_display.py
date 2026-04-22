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

# Detect SPI port (RPi5 uses port 10)
SPI_PORT = 10 if os.path.exists("/dev/spidev10.0") and not os.path.exists("/dev/spidev0.0") else 0
SPI_DEVICE = 0

print(f"=== PiFinder OLED Display Diagnostic ===")
print(f"SPI devices: {os.listdir('/dev') and [f for f in os.listdir('/dev') if 'spi' in f]}")
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
    sys.exit(1)

# Step 2: GPIO test (DC pin = GPIO 24) — no cleanup so luma can reuse GPIO
print("\n[2] Testing GPIO (DC pin = GPIO 24)...")
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(24, GPIO.OUT)
    GPIO.output(24, GPIO.HIGH)
    GPIO.output(24, GPIO.LOW)
    print("    OK - GPIO 24 toggled successfully (no cleanup, luma will reuse)")
except Exception as e:
    import traceback
    print(f"    FAIL - {e}")
    traceback.print_exc()

# Step 3: luma SSD1351 init
print("\n[3] Initializing SSD1351 via luma (10 MHz, BGR)...")
try:
    from luma.core.interface.serial import spi as luma_spi
    from luma.oled.device import ssd1351
    serial = luma_spi(device=SPI_DEVICE, port=SPI_PORT, bus_speed_hz=10_000_000)
    device = ssd1351(serial, rotate=0, bgr=True)
    print("    OK - SSD1351 initialized")
except Exception as e:
    import traceback
    print(f"    FAIL - {e!r}")
    traceback.print_exc()
    sys.exit(1)

# Step 4: draw solid colors
print("\n[4] Drawing test pattern (red → green → blue → white, 1s each)...")
from PIL import Image, ImageDraw, ImageFont

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

# Step 5: text overlay
print("\n[5] Drawing text overlay...")
img = Image.new("RGB", (128, 128), (0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rectangle([0, 0, 127, 127], outline=(255, 255, 0))
draw.text((10, 50), "PiFinder", fill=(255, 255, 0))
draw.text((10, 65), "RPi5 OK", fill=(0, 255, 0))
device.display(img)
print("    Text drawn - check OLED for yellow text on black background")

print("\n=== Diagnostic complete ===")
print("If OLED showed colors and text, the display is working correctly.")
print("If OLED stayed blank, check wiring: MOSI, SCLK, CS, DC (GPIO24), RST (GPIO25), VCC, GND")
