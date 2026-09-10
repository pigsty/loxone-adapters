import logging
import os
import re
import time
import xml.etree.ElementTree as ET

import requests
import yaml

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("loxone-to-obs")

LOXONE_BASE_URL = os.environ["LOXONE_BASE_URL"].rstrip("/")
LOXONE_USERNAME = os.environ["LOXONE_USERNAME"]
LOXONE_PASSWORD = os.environ["LOXONE_PASSWORD"]

OBS_BASE_URL = os.environ["OBS_BASE_URL"].rstrip("/")
OBS_API_KEY = os.environ["OBS_API_KEY"]
OBS_AUTH_HEADER = os.environ.get("OBS_AUTH_HEADER", "")

POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))

MAPPING_FILE = os.environ.get("MAPPING_FILE", "config/field_mapping.yaml")

_NUMERIC_RE = re.compile(r"[^0-9.\-]")


def load_mapping(path):
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("fields", {})


FIELDS = load_mapping(MAPPING_FILE)
log.info("Loaded %d field mapping(s) from %s", len(FIELDS), MAPPING_FILE)


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


def send_to_obs(obs_field, value):
    url = f"{OBS_BASE_URL}/{obs_field}/{value}"
    headers = {"x-api-key": OBS_API_KEY}
    if OBS_AUTH_HEADER:
        headers["Authorization"] = OBS_AUTH_HEADER

    response = requests.put(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    log.info("Sent %s=%s to OBS", obs_field, value)


def run_cycle():
    for object_name, obs_field in FIELDS.items():
        try:
            raw_value = fetch_loxone_value(object_name)
        except Exception:
            log.exception("Failed to fetch %s from Loxone", object_name)
            continue

        cleaned_value = _NUMERIC_RE.sub("", raw_value)
        try:
            float(cleaned_value)
        except ValueError:
            log.warning("Value %r for %s is not numeric, skipping", raw_value, object_name)
            continue

        try:
            send_to_obs(obs_field, cleaned_value)
        except Exception:
            log.exception("Failed to send %s=%s to OBS", obs_field, cleaned_value)


def main():
    log.info("Starting loxone-to-obs, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
