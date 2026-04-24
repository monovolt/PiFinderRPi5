#!/usr/bin/env python3
"""
Camera diagnostic script for PiFinder IMX462 (and other sensors).

Run on the Pi to check sensor health, dark current, and exposure levels.

Usage:
    python3 diag_camera.py              # Interactive test with prompts
    python3 diag_camera.py --quick      # Quick stats only, no prompts
    python3 diag_camera.py --gain N     # Override analog gain (default: 1)
    python3 diag_camera.py --exp MS     # Override exposure in ms (default: 100)
"""

import argparse
import sys
import time
import numpy as np

DARK_THRESHOLD_12BIT = 500   # Mean ADU (12-bit) above which image is considered overexposed
NOISE_THRESHOLD_12BIT = 50   # Std-dev (12-bit) above which sensor is considered noisy


def capture_raw(gain: float, exposure_us: int):
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("ERROR: picamera2 not found. Run this script on the Pi.")
        sys.exit(1)

    cam = Picamera2()
    cam_id = cam.camera.id
    print(f"  Camera ID : {cam_id}")

    cfg = cam.create_still_configuration(
        raw={"size": (1920, 1080), "format": "SRGGB12"}
    )
    cam.configure(cfg)
    cam.set_controls(
        {
            "AeEnable": False,
            "AnalogueGain": gain,
            "ExposureTime": exposure_us,
        }
    )
    cam.start()
    time.sleep(2)  # Let sensor settle

    req = cam.capture_request()
    raw = req.make_array("raw").copy().view(np.uint16)
    req.release()
    cam.stop()
    cam.close()  # Must explicitly close to release hardware for next capture
    return raw, cam_id


def normalize_to_12bit(arr: np.ndarray, sensor_bits: int = 12) -> tuple:
    """Normalize raw uint16 values to the sensor's native bit depth.

    RPi5 PiSP pipeline stores N-bit sensor values left-aligned in 16-bit words.
    The correct shift is always (16 - sensor_bits), e.g. 4 for 12-bit sensors.
    Returns (normalized_array, bit_shift_applied).
    """
    shift = 16 - sensor_bits  # e.g. 16-12=4 for SRGGB12 on RPi5
    if shift > 0 and arr.max() > (2**sensor_bits - 1):
        return arr >> shift, shift
    return arr, 0


def print_stats(label: str, arr: np.ndarray):
    arr_12, shift = normalize_to_12bit(arr)
    print(f"\n--- {label} ---")
    print(f"  Shape      : {arr.shape}")
    print(f"  Raw uint16 : min={arr.min()}, max={arr.max()}, mean={arr.mean():.1f}")
    if shift > 0:
        print(f"  Bit shift  : >>{shift} (RPi5 PiSP left-aligned format detected)")
        print(f"  12-bit ADU : min={arr_12.min()}, max={arr_12.max()}, mean={arr_12.mean():.1f}, std={arr_12.std():.1f}")
    else:
        print(f"  Std        : {arr.std():.1f}")

    mean = arr_12.mean()
    if mean < 400:
        verdict = "OK - sensor is dark (normal bias level)"
    elif mean < DARK_THRESHOLD_12BIT:
        verdict = "MODERATE - some ambient light detected"
    else:
        verdict = "HIGH - likely overexposed or light leak"
    print(f"  Verdict    : {verdict}")
    return arr_12


def main():
    parser = argparse.ArgumentParser(description="PiFinder camera diagnostic")
    parser.add_argument("--quick", action="store_true", help="Skip prompts")
    parser.add_argument("--gain", type=float, default=1.0, help="Analog gain (default: 1.0)")
    parser.add_argument("--exp", type=float, default=100.0, help="Exposure in ms (default: 100)")
    args = parser.parse_args()

    exposure_us = int(args.exp * 1000)

    print("=" * 50)
    print("PiFinder Camera Diagnostic")
    print("=" * 50)

    # --- Test 1: Lens cap (dark frame) ---
    print("\n[Test 1] Dark frame - COVER THE LENS NOW")
    if not args.quick:
        input("  Press Enter when lens is covered...")

    print(f"  Capturing with gain={args.gain}x, exposure={args.exp}ms ...")
    raw_dark, cam_id = capture_raw(args.gain, exposure_us)
    dark_12 = print_stats("Dark frame (lens covered)", raw_dark)

    dark_mean = dark_12.mean()
    dark_std = dark_12.std()

    # --- Test 2: Open sky / scene ---
    print("\n[Test 2] Live frame - UNCOVER THE LENS / POINT AT SKY")
    if not args.quick:
        input("  Press Enter when ready...")

    print(f"  Capturing with gain={args.gain}x, exposure={args.exp}ms ...")
    raw_live, _ = capture_raw(args.gain, exposure_us)
    live_12 = print_stats("Live frame (sky / scene)", raw_live)

    live_mean = live_12.mean()

    # --- Summary ---
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    sensor_ok = True

    if dark_mean < 400:
        print(f"  [PASS] Dark frame mean={dark_mean:.0f} ADU → normal bias level, no excess dark current")
    else:
        print(f"  [WARN] Dark frame mean={dark_mean:.0f} ADU is HIGH → possible hot sensor / dark current issue")
        sensor_ok = False

    if dark_std < NOISE_THRESHOLD_12BIT:
        print(f"  [PASS] Dark frame std={dark_std:.1f} ADU → read noise in normal range")
    else:
        print(f"  [WARN] Dark frame std={dark_std:.1f} ADU is HIGH → noisy sensor or gain too high")
        sensor_ok = False

    if live_mean > dark_mean + 50:
        print(f"  [PASS] Live frame ({live_mean:.0f}) > dark ({dark_mean:.0f}) → sensor responds to light")
    else:
        print(f"  [WARN] Live frame is NOT brighter than dark → possible light path issue")
        sensor_ok = False

    if live_mean > DARK_THRESHOLD_12BIT:
        print(f"  [INFO] Live frame mean={live_mean:.0f} ADU is high → overexposed or strong sky glow")
    else:
        print(f"  [INFO] Live frame mean={live_mean:.0f} ADU looks reasonable")

    print()
    if sensor_ok:
        print("  CONCLUSION: Sensor appears healthy.")
        print("              If PiFinder still shows white screen,")
        print("              update the firmware (git pull) — root cause was")
        print("              RPi5 PiSP raw format (left-aligned 12-bit) not handled correctly.")
    else:
        print("  CONCLUSION: Sensor may have issues. Check connections and temperature.")
        print("              If dark frame mean is very high (>1000 ADU), sensor may be damaged.")

    print("=" * 50)


if __name__ == "__main__":
    main()
