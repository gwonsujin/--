
import evdev
import sys

device_path = '/dev/input/event5'

REMOTE_MAP = {
    0x16: "BUTTON_0",
    0x0c: "BUTTON_1",
    0x18: "BUTTON_2",
    0x5E: "BUTTON_3"
}

try:
    device = evdev.InputDevice(device_path)
    print(f"Listening on {device_path}...")

    for event in device.read_loop():
        if event.type == evdev.ecodes.EV_MSC:
            scancode = event.value

            if scancode in REMOTE_MAP:
                btn_name = REMOTE_MAP[scancode]
                print(f"Button Pressed: {btn_name} (Code: {hex(scancode)})")

                if btn_name == "BUTTON_1":
                    print(">>>")
                elif btn_name == "BUTTON_0":
                    print("SYSTEM OFF")
                    
            else:
                print(f"Unknown Button Code: {hex(scancode)}")

except FileNotFoundError:
    print(f"Error: Device not found at {device_path}")
except Exception as e:
    print(f"Error: {e}")
