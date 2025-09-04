"""MQTT bridge for Vents AHU using entities.py with robust logging & per-entity polling."""

import json
import logging
import os
import time
from typing import Any, Dict, Iterable, List, TypedDict, NotRequired, Literal, Union

import paho.mqtt.client as mqtt
import vents_ahu.constant as c
from vents_ahu.vents import Vents

# ---------- logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("vents-ahu-bridge")

# ---------- env ----------
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "ventsahu")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "ventsahu")

DEVICE_ID = os.getenv("VENTS_DEVICE_ID")
DEVICE_HOST = os.getenv("VENTS_DEVICE_HOST")
DEVICE_PORT = int(os.getenv("VENTS_DEVICE_PORT", "4000"))

# polling knobs (tunable via env)
POLL_INTERVAL_S = float(os.getenv("VENTS_POLL_INTERVAL_S", "10"))
PER_REQUEST_DELAY_MS = max(0, int(os.getenv("VENTS_PER_REQUEST_DELAY_MS", "80")))
READ_RETRIES = max(0, int(os.getenv("VENTS_READ_RETRIES", "1")))  # retries per entity
SOCKET_TIMEOUT_S = float(os.getenv("VENTS_SOCKET_TIMEOUT_S", "10"))

CLIENT_ID = f"vents_{DEVICE_ID}" if DEVICE_ID else "vents_UNKNOWN"
STATE_BASE = f"vents/{DEVICE_ID}" if DEVICE_ID else "vents/UNKNOWN"

# ---------- Entities (kept inline for a single-file main) ----------
Component = Literal["sensor", "binary_sensor", "number", "switch", "select"]


class Entity(TypedDict):
    # descriptive
    name: str
    register: c.Register
    component: Component

    # presentation / semantics
    device_class: NotRequired[str]
    state_class: NotRequired[str]
    unit: NotRequired[str]
    icon: NotRequired[str]
    category: NotRequired[Literal["config", "diagnostic"]]

    # value formatting / rounding
    precision: NotRequired[int]

    # number-specific
    min: NotRequired[Union[int, float]]
    max: NotRequired[Union[int, float]]
    step: NotRequired[Union[int, float]]

    # switch-specific
    payload_on: NotRequired[str]
    payload_off: NotRequired[str]

    # select-specific
    options: NotRequired[List[str]]
    mode_map: NotRequired[Dict[int, str]]
    reverse_map: NotRequired[Dict[str, int]]


MODE_MAP = {
    c.MODE_AUTO: "auto",
    c.MODE_COOLING: "cool",
    c.MODE_HEATING: "heat",
    c.MODE_VENTILATION: "ventilation",
}
MODE_REVERSE = {v: k for k, v in MODE_MAP.items()}

SPEED_MAP = {1: "low", 2: "medium", 3: "high"}
SPEED_REVERSE = {v: k for k, v in SPEED_MAP.items()}

ENTITIES: List[Entity] = [
    {
        "name": "power",
        "register": c.POWER_ON,
        "component": "switch",
        "device_class": "switch",
        "payload_on": "1",
        "payload_off": "0",
    },
    {
        "name": "mode",
        "register": c.MODE,
        "component": "select",
        "options": list(MODE_REVERSE.keys()),
        "mode_map": MODE_MAP,
        "reverse_map": MODE_REVERSE,
        "icon": "mdi:cached",
    },
    {
        "name": "fan_mode",
        "register": c.SPEED,
        "component": "select",
        "options": list(SPEED_REVERSE.keys()),
        "mode_map": SPEED_MAP,
        "reverse_map": SPEED_REVERSE,
        "icon": "mdi:fan",
    },
    {
        "name": "target_temp",
        "register": c.TARGET_TEMP,
        "component": "number",
        "device_class": "temperature",
        "unit": "°C",
        "min": c.TARGET_TEMP.get("min", 15),
        "max": c.TARGET_TEMP.get("max", 30),
        "step": 1,
        "precision": 0,
        "icon": "mdi:thermostat",
    },
    # sensors
    {
        "name": "supply_in",
        "register": c.SUPPLY_IN_TEMPERATURE,
        "component": "sensor",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "precision": 1,
    },
    {
        "name": "supply_out",
        "register": c.SUPPLY_OUT_TEMPERATURE,
        "component": "sensor",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "precision": 1,
    },
    {
        "name": "exhaust_in",
        "register": c.EXHAUST_IN_TEMPERATURE,
        "component": "sensor",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "precision": 1,
    },
    {
        "name": "exhaust_out",
        "register": c.EXHAUST_OUT_TEMPERATURE,
        "component": "sensor",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "precision": 1,
    },
    {
        "name": "humidity",
        "register": c.CURRENT_HUMIDITY,
        "component": "sensor",
        "device_class": "humidity",
        "state_class": "measurement",
        "unit": "%",
        "precision": 0,
    },
    {
        "name": "fan1_speed",
        "register": c.FAN1_SPEED,
        "component": "sensor",
        "unit": "rpm",
        "state_class": "measurement",
        "precision": 0,
        "icon": "mdi:fan",
    },
    {
        "name": "fan2_speed",
        "register": c.FAN2_SPEED,
        "component": "sensor",
        "unit": "rpm",
        "state_class": "measurement",
        "precision": 0,
        "icon": "mdi:fan",
    },
    # binary sensors
    {
        "name": "boost_mode",
        "register": c.BOOST_MODE,
        "component": "binary_sensor",
        "device_class": "running",
        "icon": "mdi:run-fast",
    },
    {
        "name": "alarm",
        "register": c.ALARM_INDICATOR,
        "component": "binary_sensor",
        "device_class": "problem",
        "icon": "mdi:alert",
    },
    # config numbers
    {
        "name": "supply_fan_speed_1",
        "register": c.SUPPLY_FAN_SPEED_1,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-1",
    },
    {
        "name": "supply_fan_speed_2",
        "register": c.SUPPLY_FAN_SPEED_2,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-2",
    },
    {
        "name": "supply_fan_speed_3",
        "register": c.SUPPLY_FAN_SPEED_3,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-3",
    },
    {
        "name": "exhaust_fan_speed_1",
        "register": c.EXHAUST_FAN_SPEED_1,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-1",
    },
    {
        "name": "exhaust_fan_speed_2",
        "register": c.EXHAUST_FAN_SPEED_2,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-2",
    },
    {
        "name": "exhaust_fan_speed_3",
        "register": c.EXHAUST_FAN_SPEED_3,
        "component": "number",
        "unit": "%",
        "min": 0,
        "max": 100,
        "step": 1,
        "precision": 0,
        "category": "config",
        "icon": "mdi:fan-speed-3",
    },
]

# ---------- globals ----------
COMMAND_TOPIC_MAP: Dict[str, Entity] = {}
ENTITIES_BY_NAME: Dict[str, Entity] = {ent["name"]: ent for ent in ENTITIES}
LAST_STATE: Dict[str, str] = {}  # cache last published payloads


# ---------- helpers: formatting/parsing ----------
def _round_if_needed(ent: Entity, value: Any) -> Any:
    prec = ent.get("precision")
    if isinstance(value, (float, int)) and isinstance(prec, int):
        return round(float(value), prec)
    return value


def _format_state(ent: Entity, value: Any) -> str:
    comp = ent["component"]

    if comp == "binary_sensor":
        pay_on = ent.get("payload_on", "ON")
        pay_off = ent.get("payload_off", "OFF")
        return pay_on if bool(value) else pay_off

    if comp == "select":
        mode_map = ent.get("mode_map", {})
        try:
            return mode_map[int(value)]
        except Exception:
            return str(value)

    if comp == "switch":
        pay_on = ent.get("payload_on", "1")
        pay_off = ent.get("payload_off", "0")
        return pay_on if bool(value) else pay_off

    value = _round_if_needed(ent, value)
    return str(value)


def _parse_command(ent: Entity, raw: str) -> Any:
    comp = ent["component"]
    raw_norm = raw.strip()

    if comp == "binary_sensor":
        return None

    if comp == "switch":
        pay_on = ent.get("payload_on", "1")
        pay_off = ent.get("payload_off", "0")
        return True if raw_norm == pay_on else False if raw_norm == pay_off else raw_norm.lower() in ("1", "true", "on")

    if comp == "select":
        rev = ent.get("reverse_map", {})
        key = raw_norm.lower()
        for k, v in rev.items():
            if k.lower() == key:
                return v
        return raw_norm

    reg = ent["register"]
    if reg["fmt"] is float:
        return float(raw_norm)
    if reg["fmt"] is bool:
        return raw_norm.lower() in ("1", "true", "on")
    return int(float(raw_norm))


# ---------- MQTT discovery ----------
def _discovery_payload(ent: Entity, device_payload: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "name": ent["name"],
        "state_topic": f"{STATE_BASE}/{ent['name']}",
        "unique_id": f"{CLIENT_ID}_{ent['name']}",
        "device": device_payload,
    }
    if "device_class" in ent:
        base["device_class"] = ent["device_class"]
    if "state_class" in ent:
        base["state_class"] = ent["state_class"]
    if "unit" in ent:
        base["unit_of_measurement"] = ent["unit"]
    if "icon" in ent:
        base["icon"] = ent["icon"]
    if "category" in ent:
        base["entity_category"] = ent["category"]
    return base


def _publish_discovery(mqtt_client: mqtt.Client) -> None:
    device_payload = {
        "identifiers": [DEVICE_ID],
        "manufacturer": "Vents",
        "name": f"Vents AHU - {DEVICE_ID}",
    }

    count_subscribed = 0
    for ent in ENTITIES:
        comp = ent["component"]
        topic = f"homeassistant/{comp}/{CLIENT_ID}/{ent['name']}/config"
        payload = _discovery_payload(ent, device_payload)

        if comp in ("switch", "number", "select"):
            payload["command_topic"] = f"{STATE_BASE}/{ent['name']}/set"
            if comp == "switch":
                payload["payload_on"] = ent.get("payload_on", "1")
                payload["payload_off"] = ent.get("payload_off", "0")
            elif comp == "number":
                if "min" in ent:
                    payload["min"] = ent["min"]
                if "max" in ent:
                    payload["max"] = ent["max"]
                payload["step"] = ent.get("step", 1)
            elif comp == "select":
                payload["options"] = ent.get("options", [])

            cmd_topic = f"{STATE_BASE}/{ent['name']}/set"
            COMMAND_TOPIC_MAP[cmd_topic] = ent
            mqtt_client.subscribe(cmd_topic)
            count_subscribed += 1

        mqtt_client.publish(topic, json.dumps(payload), retain=True)

    log.info(
        "Published discovery for %d entities; subscribed to %d command topics",
        len(ENTITIES),
        count_subscribed,
    )

    climate_topic = f"homeassistant/climate/{CLIENT_ID}/climate/config"
    payload = {
        "name": device_payload["name"],
        "unique_id": f"{CLIENT_ID}_climate",
        "device": device_payload,
        "availability_topic": f"{STATE_BASE}/availability",

        # tie to existing topics
        "power_command_topic": f"{STATE_BASE}/power/set",
        "power_state_topic": f"{STATE_BASE}/power",

        "mode_command_topic": f"{STATE_BASE}/mode/set",
        "mode_state_topic": f"{STATE_BASE}/mode",
        "modes": ["auto", "cool", "heat", "ventilation"],

        "temperature_command_topic": f"{STATE_BASE}/target_temp/set",
        "temperature_state_topic": f"{STATE_BASE}/target_temp",
        "temperature_unit": "C",
        "min_temp": 15,
        "max_temp": 30,
        "temp_step": 1,

        "fan_mode_command_topic": f"{STATE_BASE}/fan_mode/set",
        "fan_mode_state_topic": f"{STATE_BASE}/fan_mode",
        "fan_modes": ["low", "medium", "high"],
    }
    mqtt_client.publish(climate_topic, json.dumps(payload), retain=True)
    log.info("Published MQTT discovery for climate entity")


# ---------- MQTT callbacks ----------
def _on_message_factory(vents: Vents):
    def _on_message(client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        ent = COMMAND_TOPIC_MAP.get(msg.topic)
        if not ent:
            log.debug("Unknown command topic %s", msg.topic)
            return
        try:
            raw = msg.payload.decode(errors="ignore")
            value = _parse_command(ent, raw)
            if value is None:
                return
            confirmed = vents.write_register(ent["register"], value)
            state_str = _format_state(ent, confirmed)
            LAST_STATE[ent["name"]] = state_str
            client.publish(f"{STATE_BASE}/{ent['name']}", state_str, retain=True)
            log.info("Wrote %s=%s (confirmed=%s)", ent["name"], value, confirmed)
        except Exception as exc:
            log.error("Failed to write %s (payload=%r): %s", ent["name"], msg.payload, exc)

    return _on_message


# ---------- per-entity polling ----------
def _read_entity_with_retries(vents: Vents, ent: Entity) -> Any:
    """Read a single entity with small retry loop and per-request delay."""
    last_exc: Exception | None = None
    for attempt in range(READ_RETRIES + 1):
        try:
            val = vents.read_register(ent["register"])
            log.debug("Read %-18s -> %r", ent["name"], val)
            return val
        except Exception as exc:
            last_exc = exc
            log.debug("Read failed (%s) for %s, attempt %d/%d", exc, ent["name"], attempt + 1, READ_RETRIES + 1)
            time.sleep(PER_REQUEST_DELAY_MS / 1000.0)
    # if we get here, all attempts failed
    raise last_exc if last_exc else RuntimeError("unknown read error")


def _publish_if_changed(cli: mqtt.Client, name: str, state_str: str) -> None:
    if LAST_STATE.get(name) != state_str:
        LAST_STATE[name] = state_str
        cli.publish(f"{STATE_BASE}/{name}", state_str, retain=True)
        log.info("Published %s=%s (changed)", name, state_str)


# ---------- main ----------
def main() -> None:
    if not DEVICE_ID or not DEVICE_HOST:
        raise SystemExit("VENTS_DEVICE_ID and VENTS_DEVICE_HOST must be set")
    if not ENTITIES:
        log.warning("ENTITIES list is empty — nothing to do.")

    log.info(
        "Config: device_id=%s host=%s:%d mqtt=%s:%d user=%s poll=%ss delay=%dms retries=%d timeout=%ss log=%s",
        DEVICE_ID, DEVICE_HOST, DEVICE_PORT,
        MQTT_HOST, MQTT_PORT, ("<set>" if MQTT_USER else "<none>"),
        POLL_INTERVAL_S, PER_REQUEST_DELAY_MS, READ_RETRIES, SOCKET_TIMEOUT_S, LOG_LEVEL,
    )

    # device client
    vents = Vents(DEVICE_ID, DEVICE_HOST, port=DEVICE_PORT, debug=False, timeout=SOCKET_TIMEOUT_S)

    # quick connectivity self-test
    try:
        test_ent = ENTITIES_BY_NAME.get("power") or ENTITIES_BY_NAME.get("fan_mode") or ENTITIES[0]
        test_val = vents.read_register(test_ent["register"])
        log.info("Connectivity OK: %s=%r", test_ent["name"], test_val)
    except Exception as e:
        log.error("Connectivity test failed: %s", e)

    # MQTT client
    mqtt_client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)
    if MQTT_USER:
        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    mqtt_client.on_message = _on_message_factory(vents)

    # Connect & loop
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()
    log.info("Connected to MQTT %s:%d as %s", MQTT_HOST, MQTT_PORT, CLIENT_ID)

    mqtt_client.publish(f"{STATE_BASE}/availability", "online", retain=True)
    _publish_discovery(mqtt_client)

    # Order entities: live-ish first
    poll_order = sorted(
        ENTITIES,
        key=lambda e: (
            0 if e["name"] in {"power", "mode", "fan_mode", "target_temp"} else
            1 if e["name"] in {"supply_in", "supply_out", "exhaust_in", "exhaust_out", "humidity", "fan1_speed", "fan2_speed"} else
            2
        )
    )

    # Bootstrap: one pass to publish initial states
    for ent in poll_order:
        try:
            val = _read_entity_with_retries(vents, ent)
            state = _format_state(ent, val)
            LAST_STATE[ent["name"]] = state
            mqtt_client.publish(f"{STATE_BASE}/{ent['name']}", state, retain=True)
        except Exception as e:
            log.warning("Bootstrap read failed for %s: %s", ent["name"], e)
        time.sleep(PER_REQUEST_DELAY_MS / 1000.0)

    log.info("Current state: %s", LAST_STATE)

    try:
        while True:
            loop_start = time.time()

            for ent in poll_order:
                try:
                    val = _read_entity_with_retries(vents, ent)
                    state = _format_state(ent, val)
                    _publish_if_changed(mqtt_client, ent["name"], state)
                except Exception as e:
                    log.warning("Read failed for %s: %s", ent["name"], e)

                time.sleep(PER_REQUEST_DELAY_MS / 1000.0)

            mqtt_client.publish(f"{STATE_BASE}/availability", "online", retain=True)

            elapsed = time.time() - loop_start
            if elapsed < POLL_INTERVAL_S:
                time.sleep(POLL_INTERVAL_S - elapsed)
    except KeyboardInterrupt:
        log.info("Stopping…")
    finally:
        mqtt_client.publish(f"{STATE_BASE}/availability", "offline", retain=True)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
