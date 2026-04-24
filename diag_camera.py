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

BIAS_OFFSET = 50  # IMX462 expected dark-frame mean (ADU)
DARK_THRESHOLD = 500   # Mean ADU above which image is considered overexposed
NOISE_THRESHOLD = 200  # Std-dev above which sensor is considered noisy


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
    return raw, cam_id


def print_stats(label: str, arr: np.ndarray):
    print(f"\n--- {label} ---")
    print(f"  Shape : {arr.shape}")
    print(f"  Min   : {arr.min()}")
    print(f"  Max   : {arr.max()}")
    print(f"  Mean  : {arr.mean():.1f}")
    print(f"  Std   : {arr.std():.1f}")

    mean = arr.mean()
    if mean < BIAS_OFFSET + 100:
        verdict = "OK - sensor is dark (good for lens-cap test)"
    elif mean < DARK_THRESHOLD:
        verdict = "MODERATE - some ambient light detected"
    else:
        verdict = "HIGH - likely overexposed or light leak"
    print(f"  Verdict: {verdict}")


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
    print_stats("Dark frame (lens covered)", raw_dark)

    dark_mean = raw_dark.mean()
    dark_std = raw_dark.std()

    # --- Test 2: Open sky / scene ---
    print("\n[Test 2] Live frame - UNCOVER THE LENS / POINT AT SKY")
    if not args.quick:
        input("  Press Enter when ready...")

    print(f"  Capturing with gain={args.gain}x, exposure={args.exp}ms ...")
    raw_live, _ = capture_raw(args.gain, exposure_us)
    print_stats("Live frame (sky / scene)", raw_live)

    live_mean = raw_live.mean()

    # --- Summary ---
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    sensor_ok = True

    if dark_mean < BIAS_OFFSET + 150:
        print("  [PASS] Dark frame mean is low  → sensor not generating excess dark current")
    else:
        print(f"  [WARN] Dark frame mean={dark_mean:.0f} is HIGH → possible hot sensor / dark current issue")
        sensor_ok = False

    if dark_std < NOISE_THRESHOLD:
        print("  [PASS] Dark frame noise is low → read noise in normal range")
    else:
        print(f"  [WARN] Dark frame std={dark_std:.0f} is HIGH → noisy sensor or gain too high")
        sensor_ok = False

    if live_mean > dark_mean + 100:
        print("  [PASS] Live frame is brighter than dark → sensor responds to light")
    else:
        print("  [WARN] Live frame is NOT brighter than dark → possible light path issue")
        sensor_ok = False

    if live_mean > DARK_THRESHOLD:
        print(f"  [INFO] Live frame mean={live_mean:.0f} is very high → lower gain/exposure or check for light leak")
    else:
        print(f"  [INFO] Live frame mean={live_mean:.0f} looks reasonable at gain={args.gain}x")

    print()
    if sensor_ok:
        print("  CONCLUSION: Sensor appears healthy.")
        print("              If PiFinder still shows white screen,")
        print("              the issue is gain/exposure settings in the app.")
        if live_mean > DARK_THRESHOLD:
            print(f"              Recommended starting gain for night use: 10x or less")
    else:
        print("  CONCLUSION: Sensor may have issues. Check connections and temperature.")
        print("              If dark frame is very bright, sensor might be damaged.")

    print("=" * 50)


if __name__ == "__main__":
    main()
