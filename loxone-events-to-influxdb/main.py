import logging
import os
import socket

import dateutil.parser
from influxdb import InfluxDBClient

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("loxone-events-to-influxdb")

UDP_LISTEN_HOST = os.environ.get("UDP_LISTEN_HOST", "0.0.0.0")
UDP_LISTEN_PORT = int(os.environ.get("UDP_LISTEN_PORT", "5000"))

INFLUXDB_HOST = os.environ["INFLUXDB_HOST"]
INFLUXDB_PORT = int(os.environ.get("INFLUXDB_PORT", "8086"))
INFLUXDB_DATABASE = os.environ.get("INFLUXDB_DATABASE", "loxone")
INFLUXDB_USERNAME = os.environ.get("INFLUXDB_USERNAME", "loxone")
INFLUXDB_PASSWORD = os.environ.get("INFLUXDB_PASSWORD", "loxone")

client = InfluxDBClient(INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_USERNAME, INFLUXDB_PASSWORD)


def handle_event(data_str):
    timestamp_str, name, value_str = (part.strip() for part in data_str.split(";")[:3])
    measurement = name.replace(" ", "-").replace(".", "-")
    epoch_ms = int(dateutil.parser.parse(timestamp_str).timestamp() * 1000)

    line = f"{measurement},source=loxone value={value_str} {epoch_ms}"
    client.write_points([line], database=INFLUXDB_DATABASE, time_precision="ms", batch_size=1, protocol="line")
    log.info("Wrote to InfluxDB: %s", line)


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
