# Vents AHU Toolkit

Utilities for interacting with Vents air handling units.  
This package now includes an MQTT bridge exposing the unit to Home Assistant.

## Usage

### MQTT Bridge

Run the bridge with:

```bash
python -m vents_mqtt_ha_bridge
```

Required environment variables:

- `VENTS_DEVICE_ID` – device identifier of the AHU.
- `VENTS_DEVICE_HOST` – IP address of the AHU.

Optional variables:

- `VENTS_DEVICE_PORT` (default `4000`)
- `VENTS_POLL_INTERVAL_S` (default `5` seconds)
- `MQTT_HOST` (default `127.0.0.1`)
- `MQTT_PORT` (default `1883`)
- `MQTT_USER` / `MQTT_PASSWORD`

The bridge maps every read-only register to an MQTT sensor and writable registers to actuators. Discovery
messages are published under the `homeassistant/` topic so the device is automatically added to Home Assistant.
