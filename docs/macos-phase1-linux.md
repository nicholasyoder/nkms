# macOS Port — Phase 1 (Linux workstation)

## Goal

Make the macOS client code **compile and import without errors** on both platforms, and keep the Linux client working identically. The CGEvent implementation in `virtual_input_macos.py` is written here but cannot be verified until Phase 2 (Mac).

Phase 1 produces a repo that can be cloned on a Mac and run immediately for testing.

---

## Files to change / create

| File | Action |
|---|---|
| `requirements.txt` | Add platform markers |
| `nkms/core/constants.py` | Remove `evdev` import |
| `nkms/core/settings.py` | Platform-aware path + configparser backend for macOS |
| `nkms/core/virtual_input.py` | **New** — platform selector factory |
| `nkms/core/virtual_input_linux.py` | **New** — thin UInput wrapper extracted from client.py |
| `nkms/core/virtual_input_macos.py` | **New** — CGEvent implementation (full key table + mouse) |
| `nkms/core/client.py` | Use `VirtualInput` instead of `UInput` |
| `nkms/macos_client.py` | **New** — standalone launcher (no D-Bus / Qt) |
| `nkms/macos_launchagent.plist` | **New** — launchd agent template |
| `nkms/install_macos_service.sh` | **New** — install script |

`daemon.py`, `applet.py`, `server.py`, `event_handler.py`, `settings_window.py` — **untouched**.

---

## Step-by-step changes

### 1. `requirements.txt`

Replace:
```
PyQt6
evdev
```
With:
```
PyQt6; sys_platform == "linux"
evdev; sys_platform == "linux"
pyobjc-framework-Quartz; sys_platform == "darwin"
pyobjc-framework-ApplicationServices; sys_platform == "darwin"
```

---

### 2. `nkms/core/constants.py`

`evdev.ecodes` is imported only to get integer values for `EV_KEY`, `EV_REL`, `EV_MSC`. Replace with raw ints (values from `linux/input-event-codes.h`).

Replace entire file with:
```python
from typing import Final

EV_SYN: Final = 0
EV_KEY: Final = 1
EV_REL: Final = 2
EV_MSC: Final = 4

FALLBACK_DEVICE_CAPABILITIES: Final = {
    EV_KEY: [
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
        31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58,
        59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87,
        88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 113, 114,
        115, 116, 117, 119, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138,
        140, 142, 150, 152, 158, 159, 161, 163, 164, 165, 166, 173, 176, 177, 178, 179, 180, 183, 184, 185, 186, 187,
        188, 189, 190, 191, 192, 193, 194, 240, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287,
    ],
    EV_REL: [0, 1, 6, 8, 11, 12],
    EV_MSC: [4],
    17: [0, 1, 2, 3, 4],
}
```

Note: `EV_SYN` is added here for use in `virtual_input_macos.py`; it was not in the original constants.

---

### 3. `nkms/core/settings.py`

Two problems:
- Hardcoded `/etc/nkms/nkms.conf` path
- `PyQt6.QSettings` import fails on macOS (Qt not installed)

Solution: move the import inside `__init__`, add a `_ConfigParserAdapter` that presents the same `value()` / `setValue()` / `sync()` interface as `QSettings`. Top-level INI keys (no `/`) live in a `[General]` section to match QSettings INI format.

**Design note on `sync()`:** QSettings.sync() both reads external changes and flushes pending writes. The adapter tracks a `_dirty` flag — if dirty, `sync()` writes to disk; otherwise it re-reads from disk. This matches how NkmsSettings calls it: `load()` calls `sync()` before reading values; `save()` sets values then calls `sync()`.

Replace entire file with:
```python
import sys
import os
import configparser
from typing import Any

if sys.platform == 'darwin':
    _CONFIG_PATH = os.path.expanduser('~/.config/nkms/nkms.conf')
    _USE_QT = False
else:
    _CONFIG_PATH = '/etc/nkms/nkms.conf'
    _USE_QT = True


class _ConfigParserAdapter:
    """QSettings-compatible adapter backed by configparser (macOS only)."""

    def __init__(self, path: str):
        self._path = path
        self._cp = configparser.ConfigParser()
        self._dirty = False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._cp.read(path)

    def value(self, key: str, default=None):
        section, option = self._split_key(key)
        try:
            return self._cp.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def setValue(self, key: str, value) -> None:
        section, option = self._split_key(key)
        if not self._cp.has_section(section):
            self._cp.add_section(section)
        self._cp.set(section, option, str(value))
        self._dirty = True

    def sync(self) -> None:
        if self._dirty:
            with open(self._path, 'w') as f:
                self._cp.write(f)
            self._dirty = False
        else:
            self._cp.clear()
            self._cp.read(self._path)

    @staticmethod
    def _split_key(key: str) -> tuple[str, str]:
        if '/' in key:
            section, option = key.split('/', 1)
            return section, option
        return 'General', key


class NkmsSettings:
    def __init__(self):
        if _USE_QT:
            from PyQt6.QtCore import QSettings
            self.settings = QSettings(_CONFIG_PATH, QSettings.Format.IniFormat)
        else:
            self.settings = _ConfigParserAdapter(_CONFIG_PATH)
        # Defaults
        self.mode = "Client"
        self.client_server = ""
        self.client_port = 4777
        self.server_address = "0.0.0.0"
        self.server_port = 4777
        self.server_key1 = 125
        self.server_key2 = 41
        # Load saved values
        self.load()

    def load(self):
        self.settings.sync()
        self.mode = self.settings.value("mode", self.mode)
        self.client_server = self.settings.value("client/server", self.client_server)
        self.client_port = int(self.settings.value("client/port", self.client_port))
        self.server_address = self.settings.value("server/bind_address", self.server_address)
        self.server_port = int(self.settings.value("server/port", self.server_port))
        self.server_key1 = int(self.settings.value("server/key1", self.server_key1))
        self.server_key2 = int(self.settings.value("server/key2", self.server_key2))

    def save(self):
        for key, value in self.get_settings_dict().items():
            self.settings.setValue(key, value)
        self.settings.sync()

    def get_settings_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "client/server": self.client_server,
            "client/port": self.client_port,
            "server/bind_address": self.server_address,
            "server/port": self.server_port,
            "server/key1": self.server_key1,
            "server/key2": self.server_key2,
        }

    def save_settings_dict(self, settings_dict: dict[str, Any]) -> None:
        for key, value in settings_dict.items():
            self.settings.setValue(key, value)
```

Note: `save()` in the original code had a bug — `for key, value in self.get_settings_dict()` iterates over dict keys only, not (key, value) pairs. Fixed above to `.items()`.

---

### 4. `nkms/core/virtual_input.py` (new file)

```python
import sys

if sys.platform == 'darwin':
    from nkms.core.virtual_input_macos import MacOSVirtualInput as VirtualInput
else:
    from nkms.core.virtual_input_linux import LinuxVirtualInput as VirtualInput

__all__ = ['VirtualInput']
```

---

### 5. `nkms/core/virtual_input_linux.py` (new file)

Thin wrapper extracted from the `UInput` usage in `client.py`. No behaviour changes.

```python
from evdev import UInput


class LinuxVirtualInput:
    def __init__(self, capabilities: dict):
        self._ui = UInput(events=capabilities, name='NetKMSwitch Keyboard and Mouse')

    def write(self, type: int, code: int, value: int) -> None:
        self._ui.write(type, code, value)

    def syn(self) -> None:
        self._ui.syn()

    def close(self) -> None:
        self._ui.close()
```

---

### 6. `nkms/core/virtual_input_macos.py` (new file)

Full CGEvent implementation. Written on Linux, **tested on Mac in Phase 2**.

Key design decisions:
- `write()` buffers events; `syn()` flushes them as CGEvent posts
- When `write(EV_SYN=0, ...)` is received (EV_SYN event in the stream), also flush — this handles both call patterns from `client.process_data()`
- Mouse `REL_X`/`REL_Y` are accumulated across `write()` calls; a single `kCGEventMouseMoved` (or dragged) event is posted on flush
- When a mouse button is pressed the flush posts `kCGEventLeftMouseDragged` / `kCGEventRightMouseDragged` instead of `kCGEventMouseMoved`
- Scroll: `REL_WHEEL` (code 8) = vertical, `REL_HWHEEL` (code 6) = horizontal; accumulated and posted as `CGEventCreateScrollWheelEvent`

```python
import sys
assert sys.platform == 'darwin', "virtual_input_macos only runs on macOS"

import Quartz
from ApplicationServices import AXIsProcessTrusted

from nkms.core.constants import EV_SYN, EV_KEY, EV_REL, EV_MSC

# Linux evdev key code → macOS virtual key code
# Source: linux/input-event-codes.h and HIToolbox/Events.h
_KEY_MAP: dict[int, int] = {
    1:   53,   # KEY_ESC        → kVK_Escape
    2:   18,   # KEY_1          → kVK_ANSI_1
    3:   19,   # KEY_2          → kVK_ANSI_2
    4:   20,   # KEY_3          → kVK_ANSI_3
    5:   21,   # KEY_4          → kVK_ANSI_4
    6:   23,   # KEY_5          → kVK_ANSI_5
    7:   22,   # KEY_6          → kVK_ANSI_6
    8:   26,   # KEY_7          → kVK_ANSI_7
    9:   28,   # KEY_8          → kVK_ANSI_8
    10:  25,   # KEY_9          → kVK_ANSI_9
    11:  29,   # KEY_0          → kVK_ANSI_0
    12:  27,   # KEY_MINUS      → kVK_ANSI_Minus
    13:  24,   # KEY_EQUAL      → kVK_ANSI_Equal
    14:  51,   # KEY_BACKSPACE  → kVK_Delete
    15:  48,   # KEY_TAB        → kVK_Tab
    16:  12,   # KEY_Q          → kVK_ANSI_Q
    17:  13,   # KEY_W          → kVK_ANSI_W
    18:  14,   # KEY_E          → kVK_ANSI_E
    19:  15,   # KEY_R          → kVK_ANSI_R
    20:  17,   # KEY_T          → kVK_ANSI_T
    21:  16,   # KEY_Y          → kVK_ANSI_Y
    22:  32,   # KEY_U          → kVK_ANSI_U
    23:  34,   # KEY_I          → kVK_ANSI_I
    24:  31,   # KEY_O          → kVK_ANSI_O
    25:  35,   # KEY_P          → kVK_ANSI_P
    26:  33,   # KEY_LEFTBRACE  → kVK_ANSI_LeftBracket
    27:  30,   # KEY_RIGHTBRACE → kVK_ANSI_RightBracket
    28:  36,   # KEY_ENTER      → kVK_Return
    29:  59,   # KEY_LEFTCTRL   → kVK_Control
    30:  0,    # KEY_A          → kVK_ANSI_A
    31:  1,    # KEY_S          → kVK_ANSI_S
    32:  2,    # KEY_D          → kVK_ANSI_D
    33:  3,    # KEY_F          → kVK_ANSI_F
    34:  5,    # KEY_G          → kVK_ANSI_G
    35:  4,    # KEY_H          → kVK_ANSI_H
    36:  38,   # KEY_J          → kVK_ANSI_J
    37:  40,   # KEY_K          → kVK_ANSI_K
    38:  37,   # KEY_L          → kVK_ANSI_L
    39:  41,   # KEY_SEMICOLON  → kVK_ANSI_Semicolon
    40:  39,   # KEY_APOSTROPHE → kVK_ANSI_Quote
    41:  50,   # KEY_GRAVE      → kVK_ANSI_Grave
    42:  56,   # KEY_LEFTSHIFT  → kVK_Shift
    43:  42,   # KEY_BACKSLASH  → kVK_ANSI_Backslash
    44:  6,    # KEY_Z          → kVK_ANSI_Z
    45:  7,    # KEY_X          → kVK_ANSI_X
    46:  8,    # KEY_C          → kVK_ANSI_C
    47:  9,    # KEY_V          → kVK_ANSI_V
    48:  11,   # KEY_B          → kVK_ANSI_B
    49:  45,   # KEY_N          → kVK_ANSI_N
    50:  46,   # KEY_M          → kVK_ANSI_M
    51:  43,   # KEY_COMMA      → kVK_ANSI_Comma
    52:  47,   # KEY_DOT        → kVK_ANSI_Period
    53:  44,   # KEY_SLASH      → kVK_ANSI_Slash
    54:  60,   # KEY_RIGHTSHIFT → kVK_RightShift
    55:  67,   # KEY_KPASTERISK → kVK_ANSI_KeypadMultiply
    56:  58,   # KEY_LEFTALT    → kVK_Option
    57:  49,   # KEY_SPACE      → kVK_Space
    58:  57,   # KEY_CAPSLOCK   → kVK_CapsLock
    59:  122,  # KEY_F1         → kVK_F1
    60:  120,  # KEY_F2         → kVK_F2
    61:  99,   # KEY_F3         → kVK_F3
    62:  118,  # KEY_F4         → kVK_F4
    63:  96,   # KEY_F5         → kVK_F5
    64:  97,   # KEY_F6         → kVK_F6
    65:  98,   # KEY_F7         → kVK_F7
    66:  100,  # KEY_F8         → kVK_F8
    67:  101,  # KEY_F9         → kVK_F9
    68:  109,  # KEY_F10        → kVK_F10
    69:  71,   # KEY_NUMLOCK    → kVK_ANSI_KeypadClear
    70:  107,  # KEY_SCROLLLOCK → kVK_F14 (closest equivalent)
    71:  89,   # KEY_KP7        → kVK_ANSI_Keypad7
    72:  91,   # KEY_KP8        → kVK_ANSI_Keypad8
    73:  92,   # KEY_KP9        → kVK_ANSI_Keypad9
    74:  78,   # KEY_KPMINUS    → kVK_ANSI_KeypadMinus
    75:  86,   # KEY_KP4        → kVK_ANSI_Keypad4
    76:  87,   # KEY_KP5        → kVK_ANSI_Keypad5
    77:  88,   # KEY_KP6        → kVK_ANSI_Keypad6
    78:  69,   # KEY_KPPLUS     → kVK_ANSI_KeypadPlus
    79:  83,   # KEY_KP1        → kVK_ANSI_Keypad1
    80:  84,   # KEY_KP2        → kVK_ANSI_Keypad2
    81:  85,   # KEY_KP3        → kVK_ANSI_Keypad3
    82:  82,   # KEY_KP0        → kVK_ANSI_Keypad0
    83:  65,   # KEY_KPDOT      → kVK_ANSI_KeypadDecimal
    87:  103,  # KEY_F11        → kVK_F11
    88:  111,  # KEY_F12        → kVK_F12
    96:  76,   # KEY_KPENTER    → kVK_ANSI_KeypadEnter
    97:  62,   # KEY_RIGHTCTRL  → kVK_RightControl
    98:  75,   # KEY_KPSLASH    → kVK_ANSI_KeypadDivide
    100: 61,   # KEY_RIGHTALT   → kVK_RightOption
    102: 115,  # KEY_HOME       → kVK_Home
    103: 126,  # KEY_UP         → kVK_UpArrow
    104: 116,  # KEY_PAGEUP     → kVK_PageUp
    105: 123,  # KEY_LEFT       → kVK_LeftArrow
    106: 124,  # KEY_RIGHT      → kVK_RightArrow
    107: 119,  # KEY_END        → kVK_End
    108: 125,  # KEY_DOWN       → kVK_DownArrow
    109: 121,  # KEY_PAGEDOWN   → kVK_PageDown
    110: 114,  # KEY_INSERT     → kVK_Help (macOS has no Insert; Help is the closest)
    111: 117,  # KEY_DELETE     → kVK_ForwardDelete
    125: 55,   # KEY_LEFTMETA   → kVK_Command
    126: 54,   # KEY_RIGHTMETA  → kVK_RightCommand
}

# evdev BTN_* codes for mouse buttons (272–276)
_BTN_LEFT   = 272
_BTN_RIGHT  = 273
_BTN_MIDDLE = 274
_BTN_SIDE   = 275
_BTN_EXTRA  = 276

# evdev REL codes
_REL_X      = 0
_REL_Y      = 1
_REL_HWHEEL = 6
_REL_WHEEL  = 8


class MacOSVirtualInput:
    def __init__(self, capabilities: dict):
        # capabilities unused — CGEvent needs no pre-declaration
        self._pending_dx: float = 0.0
        self._pending_dy: float = 0.0
        self._pending_scroll_v: int = 0
        self._pending_scroll_h: int = 0
        self._btn_pressed: set[int] = set()  # tracks held buttons for dragged events

    def write(self, type: int, code: int, value: int) -> None:
        if type == EV_SYN:
            self._flush()
        elif type == EV_KEY:
            if code in (_BTN_LEFT, _BTN_RIGHT, _BTN_MIDDLE, _BTN_SIDE, _BTN_EXTRA):
                self._post_mouse_button(code, bool(value))
            else:
                self._post_key(code, bool(value))
        elif type == EV_REL:
            if code == _REL_X:
                self._pending_dx += value
            elif code == _REL_Y:
                self._pending_dy += value
            elif code == _REL_WHEEL:
                self._pending_scroll_v += value
            elif code == _REL_HWHEEL:
                self._pending_scroll_h += value
        # EV_MSC (4) — ignored

    def syn(self) -> None:
        self._flush()

    def close(self) -> None:
        pass

    def _flush(self) -> None:
        if self._pending_dx or self._pending_dy:
            self._post_mouse_move(self._pending_dx, self._pending_dy)
            self._pending_dx = 0.0
            self._pending_dy = 0.0
        if self._pending_scroll_v or self._pending_scroll_h:
            self._post_scroll(self._pending_scroll_v, self._pending_scroll_h)
            self._pending_scroll_v = 0
            self._pending_scroll_h = 0

    def _post_key(self, linux_code: int, key_down: bool) -> None:
        mac_vk = _KEY_MAP.get(linux_code)
        if mac_vk is None:
            return
        event = Quartz.CGEventCreateKeyboardEvent(None, mac_vk, key_down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _post_mouse_button(self, btn_code: int, pressed: bool) -> None:
        pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        if btn_code == _BTN_LEFT:
            event_type = Quartz.kCGEventLeftMouseDown if pressed else Quartz.kCGEventLeftMouseUp
            btn_num = Quartz.kCGMouseButtonLeft
        elif btn_code == _BTN_RIGHT:
            event_type = Quartz.kCGEventRightMouseDown if pressed else Quartz.kCGEventRightMouseUp
            btn_num = Quartz.kCGMouseButtonRight
        else:
            event_type = Quartz.kCGEventOtherMouseDown if pressed else Quartz.kCGEventOtherMouseUp
            btn_num = btn_code - _BTN_LEFT  # 2=middle, 3=side, 4=extra
        if pressed:
            self._btn_pressed.add(btn_code)
        else:
            self._btn_pressed.discard(btn_code)
        event = Quartz.CGEventCreateMouseEvent(None, event_type, pos, btn_num)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _post_mouse_move(self, dx: float, dy: float) -> None:
        current = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        new_pos = Quartz.CGPoint(current.x + dx, current.y + dy)
        if _BTN_LEFT in self._btn_pressed:
            move_type = Quartz.kCGEventLeftMouseDragged
            btn_num = Quartz.kCGMouseButtonLeft
        elif _BTN_RIGHT in self._btn_pressed:
            move_type = Quartz.kCGEventRightMouseDragged
            btn_num = Quartz.kCGMouseButtonRight
        else:
            move_type = Quartz.kCGEventMouseMoved
            btn_num = Quartz.kCGMouseButtonLeft
        event = Quartz.CGEventCreateMouseEvent(None, move_type, new_pos, btn_num)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _post_scroll(self, v: int, h: int) -> None:
        event = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitPixel, 2, v, h
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
```

---

### 7. `nkms/core/client.py`

Two changes only:
1. Replace `from evdev import UInput` with `from nkms.core.virtual_input import VirtualInput`
2. Replace `self.ui: UInput | None = None` with `self.ui: VirtualInput | None = None`
3. Replace `self.ui = UInput(events=..., name=...)` with `self.ui = VirtualInput(self.parse_capabilities(data))`

The `write()`, `syn()`, and `close()` call sites remain identical.

Diff:
```diff
-from evdev import UInput
+from nkms.core.virtual_input import VirtualInput
 
 ...
 
-    self.ui: UInput | None = None
+    self.ui: VirtualInput | None = None
 
 ...
 
-        self.ui = UInput(
-            events=self.parse_capabilities(data),
-            name='NetKMSwitch Keyboard and Mouse',
-        )
+        self.ui = VirtualInput(self.parse_capabilities(data))
```

---

### 8. `nkms/macos_client.py` (new file)

Standalone entry point — no D-Bus, no Qt (other than what `NkmsSettings` pulls in, which is now configparser-backed on macOS).

```python
import signal
import sys

def _check_accessibility():
    from ApplicationServices import AXIsProcessTrusted
    if not AXIsProcessTrusted():
        print(
            "ERROR: Accessibility permission not granted.\n"
            "Open System Settings → Privacy & Security → Accessibility\n"
            "and add the Python interpreter running this script."
        )
        sys.exit(1)

def main():
    _check_accessibility()

    from nkms.core.client import NkmsClient
    client = NkmsClient()

    def _shutdown(signum, frame):
        print("\nShutting down...")
        client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    client.run()

if __name__ == '__main__':
    main()
```

---

### 9. `nkms/macos_launchagent.plist` (new file)

See `docs/macos-client-plan.md` § Problem 6 for the full plist and install script. These are already documented there and are straightforward to create once Phase 1 code is complete.

---

## Linux regression check after Phase 1

After making all changes, verify the Linux client still works:

```bash
python -c "from nkms.core.constants import FALLBACK_DEVICE_CAPABILITIES; print('constants ok')"
python -c "from nkms.core.settings import NkmsSettings; print('settings ok')"
python -c "from nkms.core.virtual_input import VirtualInput; print('virtual_input ok')"
python -c "from nkms.core.client import NkmsClient; print('client ok')"
```

The daemon and applet are untouched and should continue to work as before.

---

## What Phase 1 does NOT do

- Does not test CGEvent posting — requires a Mac
- Does not test the Accessibility permission flow
- Does not test the key code table accuracy
- Does not test the launchd service
- Does not handle the case where `pyobjc-framework-Quartz` import itself fails gracefully (not needed — on Linux the `darwin` branch is never entered; on Mac it must be installed)

See `docs/macos-phase2-mac.md` for the Mac testing guide.
