import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
import yaml

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("mbus-to-loxone")

MBUS_PROXY_URL = os.environ["MBUS_PROXY_URL"]
LOXONE_BASE_URL = os.environ["LOXONE_BASE_URL"].rstrip("/")
LOXONE_USERNAME = os.environ["LOXONE_USERNAME"]
LOXONE_PASSWORD = os.environ["LOXONE_PASSWORD"]
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))
MAPPING_FILE = os.environ.get("MAPPING_FILE", "config/field_mapping.yaml")


def load_mapping(path):
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("fields", {})


FIELDS = load_mapping(MAPPING_FILE)
log.info("Loaded %d field mapping(s) from %s", len(FIELDS), MAPPING_FILE)


def loxone_auth():
    return (LOXONE_USERNAME, LOXONE_PASSWORD)


def fetch_mbus_records():
    response = requests.post(MBUS_PROXY_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    records = {}
    for record in root.findall(".//DataRecord"):
        record_id = record.attrib.get("id")
        value_el = record.find("Value")
        if record_id is not None and value_el is not None and value_el.text is not None:
            records[record_id] = value_el.text.strip()
    return records


def push_to_loxone(virtual_input, value):
    url = f"{LOXONE_BASE_URL}/dev/sps/io/{virtual_input}/{value}"
    response = requests.get(url, auth=loxone_auth(), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()


def run_cycle():
    try:
        records = fetch_mbus_records()
    except Exception:
        log.exception("Failed to fetch M-Bus data from %s", MBUS_PROXY_URL)
        return

    for record_id, virtual_input in FIELDS.items():
        value = records.get(record_id)
        if value is None:
            log.warning("DataRecord id=%s not present in M-Bus response", record_id)
            continue
        try:
            push_to_loxone(virtual_input, value)
            log.info("Pushed DataRecord id=%s = %s to Loxone %s", record_id, value, virtual_input)
        except Exception:
            log.exception("Failed to push DataRecord id=%s = %s to Loxone %s", record_id, value, virtual_input)


def main():
    log.info("Starting mbus-to-loxone, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        run_cycle()
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
