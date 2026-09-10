import json
import logging
import os
import socket

import requests
import yaml

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("loxone-events-to-emoncms")

UDP_LISTEN_HOST = os.environ.get("UDP_LISTEN_HOST", "0.0.0.0")
UDP_LISTEN_PORT = int(os.environ.get("UDP_LISTEN_PORT", "5001"))

EMONCMS_BASE_URL = os.environ.get("EMONCMS_BASE_URL", "https://emoncms.org/input/post")
EMONCMS_API_KEY = os.environ["EMONCMS_API_KEY"]
EMONCMS_NODE = os.environ.get("EMONCMS_NODE", "emontx")
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "10"))

MAPPING_FILE = os.environ.get("MAPPING_FILE", "config/field_mapping.yaml")


def load_mapping(path):
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    fields = raw.get("fields", {})
    binary_fields = set(raw.get("binary_fields", []))
    return fields, binary_fields


FIELDS, BINARY_FIELDS = load_mapping(MAPPING_FILE)
log.info("Loaded %d field mapping(s) from %s", len(FIELDS), MAPPING_FILE)


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

    if emoncms_name in BINARY_FIELDS:
        # Force a visible transition so emoncms registers the change even if
        # the new value matches whatever it last saw.
        if value == 0:
            send_to_emoncms(emoncms_name, 1)
            send_to_emoncms(emoncms_name, 0)
        elif value == 1:
            send_to_emoncms(emoncms_name, 0)
            send_to_emoncms(emoncms_name, 1)
    else:
        send_to_emoncms(emoncms_name, value)


def handle_event(data_str):
    _timestamp_str, name, value_str = (part.strip() for part in data_str.split(";")[:3])
    measurement = name.replace(" ", "-").replace(".", "-")

    emoncms_name = FIELDS.get(measurement)
    if emoncms_name is None:
        log.debug("Ignoring unmapped Loxone object: %s", measurement)
        return

    send_value(emoncms_name, value_str)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_LISTEN_HOST, UDP_LISTEN_PORT))
    log.info("Listening for Loxone UDP events on %s:%s", UDP_LISTEN_HOST, UDP_LISTEN_PORT)

    while True:
        data, _addr = sock.recvfrom(1024)
        data_str = data.decode()
        log.info("Received: %s", data_str)
        try:
            handle_event(data_str)
        except Exception:
            log.exception("Failed to handle Loxone event: %s", data_str)


if __name__ == "__main__":
    main()
