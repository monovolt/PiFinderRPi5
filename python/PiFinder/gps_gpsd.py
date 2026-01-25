#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
This module is for GPS related functions
"""

import asyncio
from PiFinder.multiproclogging import MultiprocLogging
from gpsdclient import GPSDClient
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("GPS")

error_2d = 999
error_3d = 999
error_in_m = 999

lock_at = 6_000  # 1 km
fix_2d = 4_000  # m
fix_3d = 1_000  # m

def is_tpv_accurate(tpv_dict):
    """
    Check the accuracy of the GPS fix
    """
    global error_2d, error_3d, error_in_m
    # get the ecefpAcc if present, else get sep, else use 499
    # error = tpv_dict.get("ecefpAcc", tpv_dict.get("sep", 499))
    mode = tpv_dict.get("mode")
    logger.info(
        "GPS: TPV: mode=%s, ecefpAcc=%s, sep=%s, error_2d=%s, error_3d=%s",
        mode,
        # error,
        tpv_dict.get("ecefpAcc", -1),
        tpv_dict.get("sep", -1),
        error_2d,
        error_3d,
    )
    if mode == 2 and error_2d < 1000:
        error_in_m = error_2d
        return True
    if mode == 3 and error_3d < 500:
        error_in_m = error_3d
        return True
    else:
        return False


async def aiter_wrapper(sync_iter):
    """Wrap a synchronous iterable into an asynchronous one."""
    for item in sync_iter:
        yield item
        await asyncio.sleep(0)  # Yield control to the event loop


async def process_sky_messages(client, gps_queue):
    sky_stream = client.dict_stream(filter=["SKY"])
    global error_2d, error_3d
    async for result in aiter_wrapper(sky_stream):
        logger.info("GPS: SKY: %s", result)
        if result["class"] == "SKY":
            error_2d = result.get("hdop", 999)
            error_3d = result.get("pdop", 999)
        if result["class"] == "SKY" and "nSat" in result:
            sats_seen = result["nSat"]
            sats_used = result["uSat"]
            num_sats = (sats_seen, sats_used)
            msg = ("satellites", num_sats)
            logger.info("Number of sats seen: %i", sats_seen)
            gps_queue.put(msg)
        await asyncio.sleep(0)  # Yield control to the event loop


async def process_reading_messages(client, gps_queue, console_queue, gps_locked):
    global error_in_m
    tpv_stream = client.dict_stream(convert_datetime=True, filter=["TPV"])
    async for result in aiter_wrapper(tpv_stream):
        if is_tpv_accurate(result):
            # if True:
            logger.info("last reading is %s", result)
            if result.get("lat") and result.get("lon") and result.get("altHAE"):
                if not gps_locked:
                    gps_locked = True
                    console_queue.put("GPS: Locked")
                    logger.info("GPS locked")

                if error_in_m < lock_at:
                    lock_type = 0
                if error_in_m < fix_2d:
                    lock_type = 2
                if error_in_m < fix_3d:
                    lock_type = 3
                    
                msg = (
                    "fix",
                    {
                        "lat": result.get("lat"),
                        "lon": result.get("lon"),
                        "altitude": result.get("altHAE"),
                        "source": "GPS",
                        "lock": True,
                        "lock_type": lock_type,
                        "error_in_m": error_in_m,
                    },
                )
                logger.info("GPS fix: %s", msg)
                gps_queue.put(msg)

            if result.get("time"):
                msg = ("time", result.get("time"))
                logger.info("Setting time to %s", result.get("time"))
                gps_queue.put(msg)
        await asyncio.sleep(0)  # Yield control to the event loop


async def gps_main(gps_queue, console_queue, log_queue):
    MultiprocLogging.configurer(log_queue)
    logger.info("Using GPSD GPS code")
    gps_locked = False

    while True:
        try:
            with GPSDClient(host="127.0.0.1") as client:
                while True:
                    logger.info("GPS waking")

                    # Run both functions concurrently
                    await asyncio.gather(
                        process_sky_messages(client, gps_queue),
                        process_reading_messages(
                            client, gps_queue, console_queue, gps_locked
                        ),
                    )

                    logger.info("GPS sleeping now for 7s")
                    await asyncio.sleep(7)
        except Exception as e:
            logger.error(f"Error in GPS monitor: {e}")
            await asyncio.sleep(5)  # Wait before attempting to reconnect


# To run the GPS monitor
def gps_monitor(gps_queue, console_queue, log_queue):
    asyncio.run(gps_main(gps_queue, console_queue, log_queue))
