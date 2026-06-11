import sys
assert sys.platform == 'darwin', "virtual_input_macos only runs on macOS"

import Quartz
from ApplicationServices import AXIsProcessTrusted

from nkms.core.constants import EV_SYN, EV_KEY, EV_REL

# Linux evdev modifier key codes → (macOS virtual key code, CGEvent flag mask)
_MODIFIER_FLAGS: dict[int, tuple[int, int]] = {
    29:  (59, Quartz.kCGEventFlagMaskControl),      # KEY_LEFTCTRL
    97:  (62, Quartz.kCGEventFlagMaskControl),      # KEY_RIGHTCTRL
    42:  (56, Quartz.kCGEventFlagMaskShift),        # KEY_LEFTSHIFT
    54:  (60, Quartz.kCGEventFlagMaskShift),        # KEY_RIGHTSHIFT
    56:  (55, Quartz.kCGEventFlagMaskCommand),       # KEY_LEFTALT  → kVK_Command
    100: (54, Quartz.kCGEventFlagMaskCommand),      # KEY_RIGHTALT → kVK_RightCommand
    125: (58, Quartz.kCGEventFlagMaskAlternate),    # KEY_LEFTMETA → kVK_Option
    126: (61, Quartz.kCGEventFlagMaskAlternate),    # KEY_RIGHTMETA → kVK_RightOption
}

# Linux evdev key code → macOS virtual key code
# Sources: linux/input-event-codes.h and HIToolbox/Events.h
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
    56:  55,   # KEY_LEFTALT    → kVK_Command
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
    100: 54,   # KEY_RIGHTALT   → kVK_RightCommand
    102: 115,  # KEY_HOME       → kVK_Home
    103: 126,  # KEY_UP         → kVK_UpArrow
    104: 116,  # KEY_PAGEUP     → kVK_PageUp
    105: 123,  # KEY_LEFT       → kVK_LeftArrow
    106: 124,  # KEY_RIGHT      → kVK_RightArrow
    107: 119,  # KEY_END        → kVK_End
    108: 125,  # KEY_DOWN       → kVK_DownArrow
    109: 121,  # KEY_PAGEDOWN   → kVK_PageDown
    110: 114,  # KEY_INSERT     → kVK_Help (macOS has no Insert key)
    111: 117,  # KEY_DELETE     → kVK_ForwardDelete
    125: 58,   # KEY_LEFTMETA   → kVK_Option
    126: 61,   # KEY_RIGHTMETA  → kVK_RightOption
}

# evdev BTN_* codes for mouse buttons
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
        self._btn_pressed: set[int] = set()
        self._active_flags: int = 0  # accumulated CGEvent modifier flags

    def write(self, type: int, code: int, value: int) -> None:
        if type == EV_SYN:
            self._flush()
        elif type == EV_KEY:
            if code in (_BTN_LEFT, _BTN_RIGHT, _BTN_MIDDLE, _BTN_SIDE, _BTN_EXTRA):
                self._flush()  # apply any pending movement before the click lands
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
        pass  # flush is triggered by write(EV_SYN=0, ...) in the event stream

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
        mod = _MODIFIER_FLAGS.get(linux_code)
        if mod is not None:
            mac_vk, flag = mod
            if key_down:
                if self._active_flags & flag:
                    return  # skip repeat events for modifiers
                self._active_flags |= flag
            else:
                self._active_flags &= ~flag
            # Modifier keys must use kCGEventFlagsChanged so macOS's internal
            # modifier-state machine updates correctly; KeyDown/Up leaves it stuck.
            event = Quartz.CGEventCreateKeyboardEvent(None, mac_vk, False)
            Quartz.CGEventSetType(event, Quartz.kCGEventFlagsChanged)
            Quartz.CGEventSetFlags(event, self._active_flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            return

        mac_vk = _KEY_MAP.get(linux_code)
        if mac_vk is None:
            return
        event = Quartz.CGEventCreateKeyboardEvent(None, mac_vk, key_down)
        # Always set flags explicitly to prevent CGEventCreateKeyboardEvent from
        # leaving default flags (e.g. kCGEventFlagMaskSecondaryFn) on some VK codes.
        Quartz.CGEventSetFlags(event, self._active_flags)
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
            None, Quartz.kCGScrollEventUnitLine, 2, v * 5, h * 5
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
