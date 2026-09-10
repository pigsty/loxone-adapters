import logging
import os
import time

import requests

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("obs-to-loxone")

OBS_SCHEDULE_URL = os.environ["OBS_SCHEDULE_URL"]

LOXONE_BASE_URL = os.environ["LOXONE_BASE_URL"].rstrip("/")
LOXONE_USERNAME = os.environ["LOXONE_USERNAME"]
LOXONE_PASSWORD = os.environ["LOXONE_PASSWORD"]
LOXONE_RATE_INPUT = os.environ.get("LOXONE_RATE_INPUT", "VI34")

POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))


def fetch_schedule_rate():
    response = requests.get(OBS_SCHEDULE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
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


def run_cycle():
    try:
        action, rate = fetch_schedule_rate()
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
