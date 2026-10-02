import json
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
import yaml

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("loxone-to-emoncms")

LOXONE_BASE_URL = os.environ["LOXONE_BASE_URL"].rstrip("/")
LOXONE_USERNAME = os.environ["LOXONE_USERNAME"]
LOXONE_PASSWORD = os.environ["LOXONE_PASSWORD"]
EMONCMS_BASE_URL = os.environ.get("EMONCMS_BASE_URL", "https://emoncms.org/input/post")
EMONCMS_API_KEY = os.environ["EMONCMS_API_KEY"]
EMONCMS_NODE = os.environ.get("EMONCMS_NODE", "emontx")
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))

MAPPING_FILE = os.environ.get("MAPPING_FILE", "config/field_mapping.yaml")


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


def send_to_emoncms(emoncms_name, value):
    params = {
        "node": EMONCMS_NODE,
        "json": json.dumps({emoncms_name: value}),
        "apikey": EMONCMS_API_KEY,
    }
    response = requests.get(EMONCMS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    log.info("Sent %s=%s to emoncms", emoncms_name, value)


def send_value(emoncms_name, value):
    try:
        value = int(value)
    except ValueError:
        pass

    send_to_emoncms(emoncms_name, value)


def run_cycle():
    for object_name, emoncms_name in FIELDS.items():
        try:
            value = fetch_loxone_value(object_name)
        except Exception:
            log.exception("Failed to fetch %s from Loxone", object_name)
            continue

        try:
            send_value(emoncms_name, value)
        except Exception:
            log.exception("Failed to send %s=%s to emoncms", emoncms_name, value)


def main():
    log.info("Starting loxone-to-emoncms, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
