#!/usr/bin/env python3
from src.vents_ahu.vents import Vents
from src.vents_ahu.constant import *

if __name__ == "__main__":
    v = Vents("0020003935325105", "192.168.132.50", debug=False)

    print(v.read_registers([EXHAUST_IN_TEMPERATURE, EXHAUST_OUT_TEMPERATURE, SUPPLY_IN_TEMPERATURE, SUPPLY_OUT_TEMPERATURE]))
