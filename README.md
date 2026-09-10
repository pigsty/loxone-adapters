# loxone-adapters

A monorepo of small, single-purpose adapter containers that move data
between a Loxone Miniserver and a handful of external services: an M-Bus
heat meter, InfluxDB, emoncms.org, and Open Battery Scheduler (OBS). Each
adapter has exactly one input and one output, and is its own container —
no shared runtime, no shared process. A crash or bad deploy in one adapter
never affects the others.

## Containers

### mbus-to-loxone
Polls a heat-pump flow/return meter over M-Bus, via a separate M-Bus proxy
reachable over HTTP, and writes each reading to a Loxone virtual input on a
fixed interval.

### loxone-events-to-influxdb
Listens on a UDP port for Loxone's push-event stream (Loxone sends a
message whenever a monitored object's value changes) and writes every
event straight to InfluxDB, unfiltered.

### loxone-events-to-emoncms
Also listens on Loxone's UDP push-event stream, on its own separate UDP
port, but only forwards a configured subset of objects to emoncms.org,
under whatever field name your emoncms account expects. Because it reacts
to Loxone's own change events rather than polling, it never sends stale
data.

### loxone-to-obs
Polls a configured set of Loxone objects (battery, grid, and solar
power/state-of-charge readings) and forwards them to Open Battery
Scheduler.

### obs-to-loxone
Polls Open Battery Scheduler's schedule endpoint and writes the current
recommended charge/discharge rate back to a Loxone virtual input.

## Configuring your own instance

Every container ships a `.env.example` (and, where it needs one, a
`config/field_mapping.example.yaml`). For each container:

```bash
cd <container>
cp .env.example .env
cp config/field_mapping.example.yaml config/field_mapping.yaml   # where present
```

Then edit both files with your own Loxone object names, meter address,
and API credentials. None of the real `.env` or `field_mapping.yaml` files
are committed to this repo (see `.gitignore`) — they're specific to one
person's install and contain credentials.

If you want a single reference table of which Loxone object/meter field
feeds which destination, keep one for yourself as `MAPPING.md` at the repo
root — that filename is already gitignored so it never gets published
alongside this repo.

## Running the full stack

```bash
docker compose up --build -d
```

`docker-compose.yml` at the repo root wires up all five containers. Each
one reads its own `.env`/`field_mapping.yaml` from its own directory, so
configure every container first.

| Service | Role |
| --- | --- |
| mbus-to-loxone | M-Bus meter → Loxone |
| loxone-events-to-influxdb | Loxone events → InfluxDB |
| loxone-events-to-emoncms | Loxone events → emoncms.org |
| loxone-to-obs | Loxone → OBS |
| obs-to-loxone | OBS schedule → Loxone |

## Loxone-side setup required

The two UDP-listening adapters depend on the Loxone Miniserver being
configured to push its events to them: add a UDP virtual output (or UDP
monitor action) for each object you want forwarded, targeting this host on
port `5000` for `loxone-events-to-influxdb` and port `5001` for
`loxone-events-to-emoncms`, in the `timestamp;object name;value` format
both containers parse.
