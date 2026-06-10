# macOS Client Port Plan

## Overview

The goal is to make the **client only** (`nkms/core/client.py`) run on macOS. The server, applet, and daemon are Linux-only and will not be ported.

## Implementation phases

- **[Phase 1 — Linux workstation](macos-phase1-linux.md):** All structural refactoring, abstraction layer, `virtual_input_macos.py` skeleton with full key table. Can be done without a Mac.
- **[Phase 2 — Mac](macos-phase2-mac.md):** Environment setup, testing checklist, known gotchas, launchd service setup. Requires a Mac.

---

---

## Problem 1: Virtual input device (`evdev.UInput`)

The client uses `UInput` to replay events — this is Linux-only (`/dev/uinput` kernel module). On macOS the equivalent is `CGEvent.post()` from `Quartz` (pyobjc). The two APIs are very different, so the right approach is to introduce a thin abstraction layer.

### Files to create

**`nkms/core/virtual_input.py`** — factory that returns the right backend:
```python
import sys
if sys.platform == 'darwin':
    from nkms.core.virtual_input_macos import MacOSVirtualInput as VirtualInput
else:
    from nkms.core.virtual_input_linux import LinuxVirtualInput as VirtualInput
```

**`nkms/core/virtual_input_linux.py`** — thin wrapper around the existing `UInput` usage extracted from `client.py`:
```python
class LinuxVirtualInput:
    def __init__(self, capabilities): ...  # wraps UInput(events=capabilities)
    def write(self, type, code, value): ...
    def syn(self): ...
    def close(self): ...
```

**`nkms/core/virtual_input_macos.py`** — `CGEvent`-based implementation:
```python
class MacOSVirtualInput:
    def __init__(self, capabilities): ...  # capabilities unused, CGEvent needs no pre-declaration
    def write(self, type, code, value): ...  # buffers events
    def syn(self): ...  # flushes buffered events as CGEvent posts
    def close(self): ...  # no-op
```

### Modify `nkms/core/client.py`

Replace direct `UInput` import with `VirtualInput` from the factory.

---

## Problem 2: Event translation (Linux evdev codes → macOS CGEvent)

The server sends events as `[type, code, value]` using Linux evdev constants. macOS `CGEvent` uses entirely different code spaces. `MacOSVirtualInput.syn()` will translate and post buffered events.

### Translation table

| evdev | macOS CGEvent API |
|---|---|
| `EV_KEY` (1) + keyboard key code + value 0/1 | `CGEventCreateKeyboardEvent(None, mac_vk, key_down)` |
| `EV_KEY` (1) + `BTN_LEFT/RIGHT/MIDDLE` (272/273/274) + 0/1 | `CGEventCreateMouseEvent(...)` with button down/up type |
| `EV_REL` (2) + `REL_X`/`REL_Y` (0/1) + delta | accumulate into pending `(dx, dy)` |
| `EV_REL` (2) + `REL_WHEEL` (8) / `REL_HWHEEL` (6) + delta | `CGEventCreateScrollWheelEvent(...)` |
| `EV_SYN` (0) | flush accumulated mouse deltas |
| `EV_MSC` (4) | ignore |

### Linux keycode → macOS virtual key code table (partial)

`virtual_input_macos.py` contains a static mapping. Representative entries:

```
KEY_ESC (1)        → kVK_Escape (53)
KEY_1 (2)          → kVK_ANSI_1 (18)
KEY_A (30)         → kVK_ANSI_A (0)
KEY_ENTER (28)     → kVK_Return (36)
KEY_LEFTSHIFT (42) → kVK_Shift (56)
KEY_SPACE (57)     → kVK_Space (49)
KEY_UP (103)       → kVK_UpArrow (126)
```

Full table is derived from Linux `input-event-codes.h` and macOS `HIToolbox/Events.h`.

### Mouse movement handling

`EV_REL` events arrive as individual X and Y lines followed by `EV_SYN`. The implementation must:
1. Accumulate `(dx, dy)` across `write()` calls
2. On `syn()`, read current cursor position with `CGEventGetLocation(CGEventCreate(None))`
3. Post a single `kCGEventMouseMoved` event at `current_pos + (dx, dy)`

### Accessibility permission

`CGEvent.post()` requires macOS Accessibility permission. At startup, check with `AXIsProcessTrusted()` and print a clear error message if missing, directing the user to System Settings → Privacy & Security → Accessibility.

---

## Problem 3: Settings file path

`NkmsSettings` hardcodes `/etc/nkms/nkms.conf` which doesn't exist on macOS.

### Modify `nkms/core/settings.py`

```python
import sys, os
if sys.platform == 'darwin':
    _config_path = os.path.expanduser('~/.config/nkms/nkms.conf')
else:
    _config_path = '/etc/nkms/nkms.conf'
```

Add `os.makedirs(os.path.dirname(_config_path), exist_ok=True)` before constructing `QSettings`.

---

## Problem 4: `constants.py` evdev import

`FALLBACK_DEVICE_CAPABILITIES` uses `evdev.ecodes` for dict keys (`EV_KEY`, `EV_REL`, `EV_MSC`). `MacOSVirtualInput` doesn't use capabilities at all, but the import still runs and will fail.

### Modify `nkms/core/constants.py`

Drop the `evdev` import and replace symbolic keys with their raw integer values: `EV_KEY=1`, `EV_REL=2`, `EV_MSC=4`.

---

## Problem 5: Daemon entry point (no D-Bus on macOS)

`daemon.py` imports `QDBusConnection` at the top level and will crash on import on macOS. Since no applet is needed for the macOS client, the fix is a standalone launcher.

### Create `nkms/macos_client.py`

A simple entry point that:
1. Checks `AXIsProcessTrusted()` and exits with a message if Accessibility is not granted
2. Loads settings from `~/.config/nkms/nkms.conf`
3. Starts `NkmsClient` directly in the main thread
4. Installs a `SIGINT`/`SIGTERM` handler for clean shutdown

Requires no D-Bus, no daemon wrapper, and no PyQt6 (unless `QSettings` in `NkmsSettings` is kept — if desired, that class could be refactored to use `configparser` to remove the Qt dependency entirely on macOS).

---

## Problem 6: Autostart on login (no systemd on macOS)

macOS uses **launchd** for service management. A user-scoped Launch Agent (a `.plist` file in `~/Library/LaunchAgents/`) is the direct equivalent of a systemd user service: it starts at login, restarts on crash, and is controlled with `launchctl`.

### Create `nkms/macos_launchagent.plist`

Ship this template in the repo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nkms.client</string>

    <key>ProgramArguments</key>
    <array>
        <string>__PYTHON__</string>
        <string>__SCRIPT__</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/tmp/nkms-client.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/nkms-client.err</string>
</dict>
</plist>
```

`__PYTHON__` and `__SCRIPT__` are substituted by the install script below.

### Create `nkms/install_macos_service.sh`

```bash
#!/usr/bin/env bash
set -e

PYTHON=$(which python3)
SCRIPT=$(realpath "$(dirname "$0")/macos_client.py")
PLIST_SRC="$(dirname "$0")/macos_launchagent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.nkms.client.plist"

sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__SCRIPT__|$SCRIPT|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl load "$PLIST_DST"
echo "nkms client service installed and started."
echo "Logs: /tmp/nkms-client.log  /tmp/nkms-client.err"
```

### Manual commands (for reference)

| Action | Command |
|---|---|
| Install & start | `bash nkms/install_macos_service.sh` |
| Stop & unload | `launchctl unload ~/Library/LaunchAgents/com.nkms.client.plist` |
| Reload after change | `launchctl unload …plist && launchctl load …plist` |
| View live logs | `tail -f /tmp/nkms-client.log /tmp/nkms-client.err` |

### Note on Accessibility permission

The Accessibility permission granted to the Terminal (or whichever app ran the installer) applies to that app, not to the launchd agent. When the agent first posts a `CGEvent`, macOS may silently drop events or prompt the user. The reliable fix is to grant Accessibility to the **Python interpreter** itself (`/usr/local/bin/python3` or wherever the venv python lives) in System Settings → Privacy & Security → Accessibility.

`macos_client.py` should call `AXIsProcessTrusted()` at startup and print a clear error if the permission is missing (see Problem 5 above).

---

## Dependencies

Update `requirements.txt` with platform markers:

```
evdev; sys_platform == "linux"
pyobjc-framework-Quartz; sys_platform == "darwin"
```

---

## Summary of changes

| File | Action | Why |
|---|---|---|
| `nkms/core/virtual_input.py` | Create | Platform selector |
| `nkms/core/virtual_input_linux.py` | Create | Extracted Linux UInput wrapper |
| `nkms/core/virtual_input_macos.py` | Create | CGEvent-based event replay + key code table |
| `nkms/core/client.py` | Modify | Use `VirtualInput` instead of `UInput` directly |
| `nkms/core/constants.py` | Modify | Remove `evdev` import, use raw int keys |
| `nkms/core/settings.py` | Modify | Platform-aware config path |
| `nkms/macos_client.py` | Create | Standalone launcher (no D-Bus) |
| `requirements.txt` | Modify | Platform-conditional dependencies |
| `nkms/macos_launchagent.plist` | Create | launchd Launch Agent template |
| `nkms/install_macos_service.sh` | Create | Installs and loads the Launch Agent |

`daemon.py`, `applet.py`, `settings_window.py`, `server.py`, and `event_handler.py` are untouched — they are Linux-only components.
