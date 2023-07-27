"""
pdcontrolRX3.py

This program resides on the receiving pico and
listens at one second intervals for signals from the master station
The output pins on the Pico are normally high and momentarily
made low to trigger the latching circuit

version 3 : no change
"""

from PiicoDev_Transceiver import PiicoDev_Transceiver
from PiicoDev_Unified import sleep_ms
from machine import Pin

st = Pin(2, Pin.OUT)
rs = Pin(3, Pin.OUT)

radio = PiicoDev_Transceiver()
st.value(1)
rs.value(1)
spot = "o"

while True:
    if radio.receive():
        message = radio.message
        if message == "Set" :
            st.value(0)
            print(f"message acted on {message}")
            sleep_ms(10)
            st.value(1)
        if message == "Reset" :
            rs.value(0)
            sleep_ms(10)
            print(f"message acted on {message}")
            rs.value(1)
    sleep_ms(1000)

    if spot == "o" :
        spot = "."
    else :
        spot = "o"

    print(f'{spot}')
