"""
Mini keyboard firmware (CircuitPython)
Seeed XIAO RP2040 + 4x MX switches (arrow keys) + EC11E encoder + 7x SK6812 MINI-E

Layout (inverted T, like a real arrow cluster):
            [SW1 = UP]
  [SW2 = DOWN] [SW4 = LEFT] [SW3 = RIGHT]

Pins and LED chain order are taken from schematic
"""

import time
import board
import keypad
import rotaryio
import neopixel
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode

# ----------------------------------------------------------------------------
# PINS
# ----------------------------------------------------------------------------
LED_PIN = board.D3          # LED data (into D3's DIN)

PINS = {
    "SW1": board.D10,
    "SW2": board.D8,
    "SW3": board.D7,
    "SW4": board.D9,
    "ENC": board.D2,        # encoder push button (S2; S1 and C go to GND)
}
ENC_A_PIN = board.D0        # encoder A  (swap A and B if the volume goes backwards)
ENC_B_PIN = board.D1        # encoder B

# ----------------------------------------------------------------------------
# KEYS
# ----------------------------------------------------------------------------
KEYMAP = {
    "SW1": Keycode.UP_ARROW,
    "SW2": Keycode.DOWN_ARROW,
    "SW3": Keycode.RIGHT_ARROW,
    "SW4": Keycode.LEFT_ARROW,
}

# ----------------------------------------------------------------------------
# LEDs - numbered like on your PCB: the first LED in the chain is number 3,
# so your 7 LEDs are 3, 4, 5, 6, 7, 8, 9.
# ----------------------------------------------------------------------------
NUM_LEDS = 7
# LED number (D3..D9) of each LED in data-chain order, read from the schematic:
# DIN -> D3 -> D5 -> D4 -> D6 -> D7 -> D9 -> D8
# If a button lights the wrong LED, fix the order here.
LED_ORDER = (3, 5, 4, 6, 7, 9, 8)

WHITE = (255, 255, 255)
LED_MAP = {
    "SW1": ((3, 9), WHITE),     
    "SW2": ((5,), WHITE),
    "SW3": ((3, 4), WHITE),
    "SW4": ((9, 6), WHITE),
    "ENC": ((8, 9), WHITE),
}

ENC_STEPS_PER_DETENT = 4    # EC11: usually 2 or 4
BRIGHTNESS = 0.3
FADE = 0.88                 # closer to 1 = slower fade after release

# ----------------------------------------------------------------------------
# SETUP
# ----------------------------------------------------------------------------
NAMES = ("SW1", "SW2", "SW3", "SW4", "ENC")

kbd = Keyboard(usb_hid.devices)
cc = ConsumerControl(usb_hid.devices)

keys = keypad.Keys(tuple(PINS[n] for n in NAMES), value_when_pressed=False, pull=True)

encoder = rotaryio.IncrementalEncoder(ENC_A_PIN, ENC_B_PIN)
last_pos = encoder.position

pixels = neopixel.NeoPixel(
    LED_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False, pixel_order=neopixel.GRB
)
pixels.fill((0, 0, 0))
pixels.show()

targets = {}
for name in NAMES:
    leds, color = LED_MAP[name]
    idx = [LED_ORDER.index(n) for n in leds if n in LED_ORDER]
    bad = [n for n in leds if n not in LED_ORDER]
    if bad:
        print("WARNING:", name, "uses LED", bad, "which does not exist (valid: 3-9)")
    targets[name] = (idx, color)

held = {n: False for n in NAMES}
level = [0.0] * NUM_LEDS
color_of = [WHITE] * NUM_LEDS

# ----------------------------------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------------------------------
while True:
    # --- buttons ---
    while True:
        event = keys.events.get()
        if event is None:
            break
        name = NAMES[event.key_number]
        held[name] = event.pressed
        if name == "ENC":
            if event.pressed:
                cc.send(ConsumerControlCode.MUTE)
        elif event.pressed:
            kbd.press(KEYMAP[name])
        else:
            kbd.release(KEYMAP[name])

    # --- encoder rotation -> volume ---
    delta = encoder.position - last_pos
    if abs(delta) >= ENC_STEPS_PER_DETENT:
        detents = int(delta / ENC_STEPS_PER_DETENT)
        last_pos += detents * ENC_STEPS_PER_DETENT
        code = (
            ConsumerControlCode.VOLUME_INCREMENT
            if detents > 0
            else ConsumerControlCode.VOLUME_DECREMENT
        )
        for _ in range(abs(detents)):
            cc.send(code)

    # --- LEDs: full while held, then fade out ---
    for i in range(NUM_LEDS):
        level[i] *= FADE
        if level[i] < 0.02:
            level[i] = 0.0
    for name in NAMES:
        if held[name]:
            idx, color = targets[name]
            for i in idx:
                level[i] = 1.0
                color_of[i] = color
    for i in range(NUM_LEDS):
        r, g, b = color_of[i]
        pixels[i] = (int(r * level[i]), int(g * level[i]), int(b * level[i]))
    pixels.show()

    time.sleep(0.01)
