from typing import TypedDict, Type, Union, Literal, NotRequired

# Header
PACKET_PREFIX: bytes = b'\xfd\xfd'
PROTOCOL_TYPE: bytes = b'\x03'
SIZE_ID: bytes = b'\x10'

# Functions
PARAMETER_READ: bytes = b'\x01'
PARAMETER_WRITE: bytes = b'\x02'
PARAMETER_WRITE_WITH_RESPONSE: bytes = b'\x03'
PARAMETER_INCREMENT_WITH_RESPONSE: bytes = b'\x04'
PARAMETER_DECREMENT_WITH_RESPONSE: bytes = b'\x05'
RESPONSE: bytes = b'\x06'

# Special in-stream markers
BGCP_CMD_FUNC: bytes = b'\xfc'
BGCP_CMD_NOT_SUP: bytes = b'\xfd'
BGCP_CMD_SIZE: bytes = b'\xfe'
BGCP_CMD_PAGE: bytes = b'\xff'

# fmt can be real Python types (int, bool, float, str) or special literals:
#  - "ip": 4-byte IPv4 rendered as dotted string
#  - "raw": opaque bytes, length per 'count'
FmtTag = Union[Type[int], Type[bool], Type[float], Type[str], Literal["ip", "raw"]]
EndianTag = Literal["big", "little"]


class Register(TypedDict):
    name: NotRequired[str]
    parameter: bytes  # 2-byte BE code (e.g., b"\x00\x02")
    count: int
    fmt: FmtTag
    read_only: NotRequired[bool]
    min: NotRequired[int]
    max: NotRequired[int]
    scale: NotRequired[float]
    endian: NotRequired[EndianTag]


MODE_VENTILATION = 0
MODE_HEATING = 1
MODE_COOLING = 2
MODE_AUTO = 3
MODE_MAP = {
    MODE_VENTILATION: "fan_only",
    MODE_HEATING: "heating",
    MODE_COOLING: "cooling",
    MODE_AUTO: "auto",
}
MODE_FROM_NAME = {v: k for k, v in MODE_MAP.items()}

# Read/Write
POWER_ON: Register = {"parameter": b"\x00\x01", "count": 1, "fmt": bool, "name": "power_on", "min": 0, "max": 1}
MODE = {"parameter": b"\x00\x0e", "count": 1, "fmt": int, "name": "mode", "min": 0, "max": 3}
SPEED: Register = {"parameter": b"\x00\x02", "count": 1, "fmt": int, "name": "speed", "min": 1, "max": 3}
TARGET_TEMP = {"parameter": b"\x00\x18", "count": 1, "fmt": int, "name": "target_temp", "min": 15, "max": 30}
SUPPLY_FAN_SPEED_1: Register = {"parameter": b"\x00\x3a", "count": 1, "fmt": int, "name": "supply_fan_speed_1"}
SUPPLY_FAN_SPEED_2: Register = {"parameter": b"\x00\x3c", "count": 1, "fmt": int, "name": "supply_fan_speed_2"}
SUPPLY_FAN_SPEED_3: Register = {"parameter": b"\x00\x3e", "count": 1, "fmt": int, "name": "supply_fan_speed_3"}
EXHAUST_FAN_SPEED_1: Register = {"parameter": b"\x00\x3b", "count": 1, "fmt": int, "name": "exhaust_fan_speed_1"}
EXHAUST_FAN_SPEED_2: Register = {"parameter": b"\x00\x3d", "count": 1, "fmt": int, "name": "exhaust_fan_speed_2"}
EXHAUST_FAN_SPEED_3: Register = {"parameter": b"\x00\x3f", "count": 1, "fmt": int, "name": "exhaust_fan_speed_3"}
WEEKLY_SCHEDULE_MODE: Register = {"parameter": b"\x00\x72", "count": 1, "fmt": bool, "name": "weekly_schedule_mode"}

# Read-only
BOOST_MODE: Register = {"parameter": b"\x00\x06", "count": 1, "fmt": bool, "name": "boost_mode", "read_only": True}
CURRENT_HUMIDITY: Register = {"parameter": b"\x00\x25", "count": 1, "fmt": float, "name": "current_humidity", "read_only": True}
EXHAUST_IN_TEMPERATURE = {"parameter": b"\x00\x1f", "count": 2, "fmt": float, "name": "exhaust_in_temperature", "read_only": True, "scale": 0.1, "endian": "little"}
SUPPLY_OUT_TEMPERATURE = {"parameter": b"\x00\x1e", "count": 2, "fmt": float, "name": "supply_out_temperature", "read_only": True, "scale": 0.1, "endian": "little"}
SUPPLY_IN_TEMPERATURE = {"parameter": b"\x00\x21", "count": 2, "fmt": float, "name": "supply_in_temperature", "read_only": True, "scale": 0.1, "endian": "little"}
EXHAUST_OUT_TEMPERATURE = {"parameter": b"\x00\x22", "count": 2, "fmt": float, "name": "exhaust_out_temperature", "read_only": True, "scale": 0.1, "endian": "little"}
FAN1_SPEED: Register = {"parameter": b"\x00\x4a", "count": 2, "fmt": int, "name": "fan1_speed", "read_only": True, "endian": "little"}
FAN2_SPEED: Register = {"parameter": b"\x00\x4b", "count": 2, "fmt": int, "name": "fan2_speed", "read_only": True, "endian": "little"}
ALARM_INDICATOR: Register = {"parameter": b"\x00\x83", "count": 1, "fmt": bool, "name": "alarm_indicator", "read_only": True}


# NOT TESTED. FOR FUTURE USE
# TIMER_MODE: Register = {"parameter": b"\x00\x07", "count": 1, "fmt": int, "name": "timer_mode"}
# COUNTDOWN_TIMER_MODE: Register = {"parameter": b"\x00\x0b", "count": 1, "fmt": int, "name": "countdown_timer"}
# HUMIDITY_SENSOR_ACTIVATION: Register = {"parameter": b"\x00\x0f", "count": 1, "fmt": bool, "name": "humidity_sensor_enable"}
# CURRENT_RTC_BATTERY_VOLTAGE: Register = {"parameter": b"\x00\x24", "count": 1, "fmt": int, "name": "rtc_battery_voltage", "read_only": True}
# CURRENT_ZERO_10V_SENSOR: Register = {"parameter": b"\x00\x2d", "count": 1, "fmt": int, "name": "zero_10v_current", "read_only": True}
# CURRENT_RELAY_SENSOR_STATE: Register = {"parameter": b"\x00\x32", "count": 1, "fmt": bool, "name": "relay_state", "read_only": True}
# RESET_ALARMS: Register = {"parameter": b"\x00\x80", "count": 1, "fmt": int, "name": "reset_alarms"}
# FILTER_REPLACEMENT_TIMER_COUNTDOWN: Register = {"parameter": b"\x00\x64", "count": 1, "fmt": int, "name": "filter_timer_countdown", "read_only": True}
# FILTER_REPLACEMENT_TIMER_SETUP: Register = {"parameter": b"\x00\x63", "count": 1, "fmt": int, "name": "filter_timer_setup"}
# FILTER_REPLACEMENT_TIMER_COUNTDOWN_RESET: Register = {"parameter": b"\x00\x65", "count": 1, "fmt": bool, "name": "filter_timer_reset"}
# FILTER_REPLACEMENT_INDICATOR: Register = {"parameter": b"\x00\x88", "count": 1, "fmt": bool, "name": "filter_indicator", "read_only": True}
# DEVICE_SEARCH: Register = {"parameter": b"\x00\x7c", "count": 16, "fmt": str, "name": "device_search", "read_only": True}
# DEVICE_PASSWORD: Register = {"parameter": b"\x00\x7d", "count": 4, "fmt": str, "name": "device_password"}
# MACHINE_HOURS: Register = {"parameter": b"\x00\x7e", "count": 2, "fmt": int, "name": "machine_hours", "read_only": True}
# CONTROLLER_BASE_FIRMWARE_AND_DATE: Register = {"parameter": b"\x00\x86", "count": 4, "fmt": "raw", "name": "firmware_and_date", "read_only": True}
# RESTORE_FACTORY_SETTINGS: Register = {"parameter": b"\x00\x87", "count": 1, "fmt": int, "name": "factory_reset"}
# UNIT_TYPE: Register = {"parameter": b"\x00\xb9", "count": 1, "fmt": int, "name": "unit_type", "read_only": True}
# CLOUD_SERVER_OPERATION_PERMISSION: Register = {"parameter": b"\x00\x85", "count": 1, "fmt": bool, "name": "cloud_permission"}
# VENTILATOR_OPERATOR_MODE: Register = {"parameter": b"\x00\xb7", "count": 1, "fmt": int, "name": "ventilator_operator_mode"}
# ZERO_10V_SENSOR_THRESHOLD_SETPOINT: Register = {"parameter": b"\x00\xb8", "count": 1, "fmt": int, "name": "zero_10v_threshold"}
# WIFI_OPERATOR_MODE: Register = {"parameter": b"\x00\x94", "count": 1, "fmt": int, "name": "wifi_operator_mode"}
# WIFI_NAME_IN_CLIENT_MODE: Register = {"parameter": b"\x00\x95", "count": 16, "fmt": str, "name": "wifi_ssid"}
# WIFI_PASSWORD: Register = {"parameter": b"\x00\x96", "count": 16, "fmt": str, "name": "wifi_password"}
# WIFI_ENCRYPTION: Register = {"parameter": b"\x00\x99", "count": 1, "fmt": int, "name": "wifi_encryption"}
# WIFI_CHANNEL: Register = {"parameter": b"\x00\x9a", "count": 1, "fmt": int, "name": "wifi_channel"}
# WIFI_IP_MODE: Register = {"parameter": b"\x00\x9b", "count": 1, "fmt": int, "name": "wifi_ip_mode"}
# WIFI_IP_ADDRESS: Register = {"parameter": b"\x00\x9c", "count": 4, "fmt": "ip", "name": "wifi_ip", "read_only": True}
# WIFI_NET_MASK: Register = {"parameter": b"\x00\x9d", "count": 4, "fmt": "ip", "name": "wifi_netmask", "read_only": True}
# WIFI_GATEWAY: Register = {"parameter": b"\x00\x9e", "count": 4, "fmt": "ip", "name": "wifi_gateway", "read_only": True}
# WIFI_APPLY_AND_QUIT: Register = {"parameter": b"\x00\xa0", "count": 1, "fmt": int, "name": "wifi_apply_and_quit"}
# WIFI_DISCARD_AND_QUIT: Register = {"parameter": b"\x00\xa2", "count": 1, "fmt": int, "name": "wifi_discard_and_quit"}
# WIFI_CURRENT_IP: Register = {"parameter": b"\x00\xa3", "count": 4, "fmt": "ip", "name": "wifi_current_ip", "read_only": True}
# NIGHT_MODE_TIMER_SETPOINT: Register = {"parameter": b"\x03\x02", "count": 1, "fmt": int, "name": "night_mode_timer_setpoint"}
# PARTY_MODE_TIMER_SETPOINT: Register = {"parameter": b"\x03\x03", "count": 1, "fmt": int, "name": "party_mode_timer_setpoint"}
# HUMIDITY_SENSOR_STATUS: Register = {"parameter": b"\x03\x04", "count": 1, "fmt": bool, "name": "humidity_sensor_status", "read_only": True}
# ZERO_10V_SENSOR_STATUS: Register = {"parameter": b"\x03\x05", "count": 1, "fmt": bool, "name": "zero_10v_sensor_status", "read_only": True}
# RTC_TIME: Register = {"parameter": b"\x00\x6f", "count": 3, "fmt": "raw", "name": "rtc_time"}
# RTC_CALENDAR: Register = {"parameter": b"\x00\x70", "count": 3, "fmt": "raw", "name": "rtc_calendar"}
# SCHEDULE_SETUP: Register = {"parameter": b"\x00\x77", "count": 4, "fmt": "raw", "name": "schedule_setup"}
