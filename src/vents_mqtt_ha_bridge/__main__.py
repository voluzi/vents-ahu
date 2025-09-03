"""MQTT bridge for Vents AHU exposing registers to Home Assistant."""

import json
import logging
import os
import time
from typing import Any, Dict

import paho.mqtt.client as mqtt

from vents_ahu.vents import Vents
import vents_ahu.constant as c

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---- Environment ----
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "ventsahu")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "ventsahu")

DEVICE_ID = os.getenv("VENTS_DEVICE_ID")
DEVICE_HOST = os.getenv("VENTS_DEVICE_HOST")
DEVICE_PORT = int(os.getenv("VENTS_DEVICE_PORT", "4000"))
POLL_INTERVAL_S = float(os.getenv("VENTS_POLL_INTERVAL_S", "5"))

# ---- Register sets ----
# Collect registers from constant module
_ALL_REGS: Dict[str, c.Register] = {
    k: v
    for k, v in vars(c).items()
    if isinstance(v, dict) and v.get("parameter") and v.get("fmt")
}
SENSOR_REGS = {k: r for k, r in _ALL_REGS.items() if r.get("read_only")}
ACTUATOR_REGS = {k: r for k, r in _ALL_REGS.items() if not r.get("read_only")}

COMMAND_TOPIC_MAP: Dict[str, c.Register] = {}


def _publish_discovery(mqtt_client: mqtt.Client, client_id: str, state_base: str) -> None:
    """Publish Home Assistant discovery configs and subscribe to command topics."""
    device_payload = {
        "identifiers": [client_id],
        "manufacturer": "Vents",
        "name": f"Vents AHU {client_id}",
    }

    # Sensors (read-only)
    for reg in SENSOR_REGS.values():
        reg_name = reg.get("name", "unknown")
        topic = f"homeassistant/sensor/{client_id}/{reg_name}/config"
        payload = {
            "name": reg_name,
            "state_topic": f"{state_base}/{reg_name}",
            "unique_id": f"{client_id}_{reg_name}",
            "device": device_payload,
        }
        mqtt_client.publish(topic, json.dumps(payload), retain=True)

    # Actuators
    for reg in ACTUATOR_REGS.values():
        reg_name = reg.get("name", "unknown")
        if reg["fmt"] is bool:
            comp = "switch"
            payload = {
                "name": reg_name,
                "state_topic": f"{state_base}/{reg_name}",
                "command_topic": f"{state_base}/{reg_name}/set",
                "payload_on": "1",
                "payload_off": "0",
                "unique_id": f"{client_id}_{reg_name}",
                "device": device_payload,
            }
        else:
            comp = "number"
            payload = {
                "name": reg_name,
                "state_topic": f"{state_base}/{reg_name}",
                "command_topic": f"{state_base}/{reg_name}/set",
                "unique_id": f"{client_id}_{reg_name}",
                "device": device_payload,
                "step": 1,
            }
            if "min" in reg:
                payload["min"] = reg["min"]
            if "max" in reg:
                payload["max"] = reg["max"]

        topic = f"homeassistant/{comp}/{client_id}/{reg_name}/config"
        mqtt_client.publish(topic, json.dumps(payload), retain=True)

        cmd_topic = f"{state_base}/{reg_name}/set"
        COMMAND_TOPIC_MAP[cmd_topic] = reg
        mqtt_client.subscribe(cmd_topic)


def _on_message_factory(vents: Vents, state_base: str):
    def _on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        reg = COMMAND_TOPIC_MAP.get(msg.topic)
        if not reg:
            return

        reg_name = reg.get("name", "unknown")
        raw = msg.payload.decode(errors="ignore").strip()
        try:
            if reg["fmt"] is bool:
                value: Any = raw.lower() in ("1", "true", "on")
            elif reg["fmt"] is float:
                value = float(raw)
            else:
                value = int(raw)

            confirmed = vents.write_register(reg, value)
            client.publish(f"{state_base}/{reg_name}", str(confirmed), retain=True)
            logging.info("Wrote %s=%s (confirmed=%s)", reg_name, value, confirmed)
        except Exception as exc:
            logging.error("Failed to write %s (payload=%r): %s", reg_name, raw, exc)

    return _on_message


def main() -> None:
    # Validate required env
    if not DEVICE_ID or not DEVICE_HOST:
        raise SystemExit("VENTS_DEVICE_ID and VENTS_DEVICE_HOST must be set")

    client_id = f"vents_{DEVICE_ID}"
    state_base = f"vents/{DEVICE_ID}"

    # Create device client inside main
    vents = Vents(DEVICE_ID, DEVICE_HOST, port=DEVICE_PORT, debug=False)

    # MQTT client
    mqtt_client = mqtt.Client(client_id=client_id, clean_session=True)
    if MQTT_USER:
        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    # Hook callbacks
    mqtt_client.on_message = _on_message_factory(vents, state_base)

    # Connect & start loop
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()
    logging.info("Connected to MQTT %s:%s as %s", MQTT_HOST, MQTT_PORT, client_id)

    # Discovery (retain)
    _publish_discovery(mqtt_client, client_id, state_base)

    # Poll loop
    try:
        while True:
            try:
                all_values = vents.read_registers(list(_ALL_REGS.values()))
                logging.info(all_values)
                for name, value in all_values.items():
                    mqtt_client.publish(f"{state_base}/{name}", str(value), retain=True)
            except Exception as exc:
                logging.error("Read/publish error: %s", exc)
            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        logging.info("Stopping…")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()