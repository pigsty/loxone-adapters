import logging
import os
import time

import requests
import xml.etree.ElementTree as ET

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("obs-to-loxone")

OBS_SCHEDULE_URL = os.environ["OBS_SCHEDULE_URL"]

LOXONE_BASE_URL = os.environ["LOXONE_BASE_URL"].rstrip("/")
LOXONE_USERNAME = os.environ["LOXONE_USERNAME"]
LOXONE_PASSWORD = os.environ["LOXONE_PASSWORD"]
LOXONE_RATE_INPUT = os.environ.get("LOXONE_RATE_INPUT", "VI34")
LOXONE_BATTERY_SOC_OUTPUT = os.environ.get("LOXONE_BATTERY_SOC_OUTPUT", "Battery SOC")

POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))


def fetch_schedule_rate(battery_soc):
    response = requests.get(OBS_SCHEDULE_URL, params={"battery_soc": battery_soc}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()

    schedule = data.get("schedule") or []
    if not schedule:
        raise ValueError("OBS schedule response has no entries")

    entry = schedule[0]
    action = entry.get("action")
    rate = entry.get("rate_kw")
    if rate is None:
        raise ValueError("OBS schedule entry has no rate_kw")

    return action, float(rate)


def push_to_loxone(value):
    url = f"{LOXONE_BASE_URL}/dev/sps/io/{LOXONE_RATE_INPUT}/{value}"
    response = requests.get(url, auth=(LOXONE_USERNAME, LOXONE_PASSWORD), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

def fetch_loxone_value(object_name):
    url = f"{LOXONE_BASE_URL}/dev/sps/io/{requests.utils.quote(object_name)}"
    response = requests.get(url, auth=(LOXONE_USERNAME, LOXONE_PASSWORD), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    code = root.attrib.get("Code")
    if code != "200":
        raise ValueError(f"Loxone returned non-success code {code!r} for {object_name}")

    value = root.attrib.get("value")
    if value is None:
        raise ValueError(f"Loxone response for {object_name} has no 'value' attribute")
    return value

def run_cycle():
    try:
        battery_soc = fetch_loxone_value(LOXONE_BATTERY_SOC_OUTPUT)
        log.info("Fetched battery SOC=%s from Loxone %s", battery_soc, LOXONE_BATTERY_SOC_OUTPUT)
    except Exception:   
        log.exception("Failed to fetch battery SOC from Loxone %s, using default value (0.5)", LOXONE_BATTERY_SOC_OUTPUT)
        battery_soc = 0.5
    
    try:
        action, rate = fetch_schedule_rate(battery_soc)
    except Exception:
        log.exception("Failed to fetch schedule from %s", OBS_SCHEDULE_URL)
        return

    try:
        push_to_loxone(rate)
        log.info("Pushed rate=%s (action=%s) to Loxone %s", rate, action, LOXONE_RATE_INPUT)
    except Exception:
        log.exception("Failed to push rate=%s to Loxone %s", rate, LOXONE_RATE_INPUT)


def main():
    log.info("Starting obs-to-loxone, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
