#!/usr/bin/env python3
"""
GPS 독립 테스트 스크립트
사용법:
  python3 gps_test.py            # GPSD 방식 (기본)
  python3 gps_test.py --raw      # Raw 시리얼 직접 읽기
  python3 gps_test.py --raw --port /dev/ttyAMA10 --baud 115200
"""

import argparse
import sys
import time


def test_gpsd():
    print("=== GPSD 방식 테스트 ===")
    try:
        from gpsdclient import GPSDClient
    except ImportError:
        print("ERROR: gpsdclient 없음. 설치: pip install gpsdclient")
        return

    print("GPSD 연결 중...")
    try:
        with GPSDClient(host="127.0.0.1") as client:
            print("연결 성공. 데이터 기다리는 중... (Ctrl+C로 종료)\n")
            for result in client.dict_stream(convert_datetime=True, filter=["TPV", "SKY"]):
                cls = result.get("class")
                if cls == "TPV":
                    mode = result.get("mode", 0)
                    mode_str = {0: "알 수 없음", 1: "fix 없음", 2: "2D fix", 3: "3D fix"}.get(mode, str(mode))
                    lat = result.get("lat", "없음")
                    lon = result.get("lon", "없음")
                    alt = result.get("altHAE", "없음")
                    print(f"[TPV] 모드: {mode_str} | 위도: {lat} | 경도: {lon} | 고도: {alt}m")
                elif cls == "SKY":
                    n_sat = result.get("nSat", "?")
                    u_sat = result.get("uSat", "?")
                    hdop = result.get("hdop", "?")
                    print(f"[SKY] 위성: {u_sat}/{n_sat}개 사용중 | HDOP: {hdop}")
    except ConnectionRefusedError:
        print("ERROR: GPSD가 실행 중이지 않음. 실행: sudo systemctl start gpsd")
    except KeyboardInterrupt:
        print("\n종료")


def test_raw(port, baud):
    print(f"=== Raw 시리얼 테스트: {port} @ {baud}bps ===")
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial 없음. 설치: pip install pyserial")
        return

    try:
        ser = serial.Serial(port, baud, timeout=2)
        print(f"포트 열림. NMEA 데이터 기다리는 중... (Ctrl+C로 종료)\n")
        empty_count = 0
        while True:
            line = ser.readline()
            if line:
                empty_count = 0
                try:
                    print(line.decode("ascii", errors="replace").strip())
                except Exception:
                    print(f"[바이너리] {line.hex()}")
            else:
                empty_count += 1
                if empty_count == 1:
                    print("데이터 없음 (2초 타임아웃)...")
                if empty_count >= 5:
                    print("데이터가 계속 없음. GPS TX 배선 확인 필요.")
                    break
    except PermissionError:
        print(f"ERROR: {port} 접근 권한 없음. sudo로 실행하거나 dialout 그룹 추가 필요")
        print("  sudo usermod -a -G dialout $USER")
    except serial.SerialException as e:
        print(f"ERROR: 포트 열기 실패 - {e}")
    except KeyboardInterrupt:
        print("\n종료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPS 테스트")
    parser.add_argument("--raw", action="store_true", help="Raw 시리얼 직접 읽기 (GPSD 우회)")
    parser.add_argument("--port", default="/dev/ttyAMA2", help="시리얼 포트 (기본: /dev/ttyAMA2)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (기본: 115200)")
    args = parser.parse_args()

    if args.raw:
        test_raw(args.port, args.baud)
    else:
        test_gpsd()
