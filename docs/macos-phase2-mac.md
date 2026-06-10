# macOS Port — Phase 2 (Mac)

## Prerequisites

Phase 1 (Linux) must be complete and pushed/available on the Mac before starting here.

---

## Environment setup

```bash
# Clone or pull the repo
git clone <repo> nkms   # or git pull on existing clone

# Create a virtual env (use the system Python 3 or a Homebrew one)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (evdev is skipped automatically on macOS)
pip install -e .
# or if not using pyproject.toml properly:
pip install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
```

Check pyobjc installed correctly:
```bash
python3 -c "import Quartz; print('Quartz ok')"
python3 -c "from ApplicationServices import AXIsProcessTrusted; print(AXIsProcessTrusted())"
```

The second line returns `True` if Accessibility is already granted, `False` if not.

---

## Grant Accessibility permission

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** and add the Python binary being used: `which python3` (or the venv path, e.g. `.venv/bin/python3`)
3. If the binary path changes later (Homebrew upgrade, new venv), you must re-add it — macOS silently revokes the permission when the binary path changes

Verify:
```bash
python3 -c "from ApplicationServices import AXIsProcessTrusted; print(AXIsProcessTrusted())"
# Should print True
```

---

## Create the config file

```bash
mkdir -p ~/.config/nkms
cat > ~/.config/nkms/nkms.conf << EOF
[General]
mode = Client

[client]
server = 192.168.x.x   # replace with your Linux server IP
port = 4777
EOF
```

---

## Run the client manually (before setting up the service)

```bash
python3 nkms/macos_client.py
```

Expected output:
```
Starting NKMS client
```

If the Linux server is running and reachable, the client will connect and begin receiving events.

---

## Testing checklist

Work through these in order — stop and fix issues before moving on.

### Connectivity
- [ ] Client starts without import errors
- [ ] Client connects to the Linux server (look for `Successfully connected to ...` log line)
- [ ] Keep-alive ping/pong works (no timeout messages after connection)

### Keyboard
- [ ] Basic alphanumeric keys (a–z, 0–9)
- [ ] Modifier keys: Shift, Ctrl, Alt/Option, Command (⌘), Caps Lock
- [ ] Special keys: Enter, Backspace/Delete, Tab, Escape
- [ ] Arrow keys and Home/End/PageUp/PageDown
- [ ] F1–F12
- [ ] Numpad keys (if server machine has numpad)
- [ ] Key repeat works (hold a key down)

### Mouse movement
- [ ] Cursor moves in expected direction (no inversion)
- [ ] Speed feels proportional to physical movement
- [ ] Movement near screen edges (no clamping issues)

### Mouse buttons
- [ ] Left click
- [ ] Right click
- [ ] Middle click
- [ ] Click-and-drag (left button held + movement → dragged event, not moved)

### Scroll wheel
- [ ] Vertical scroll
- [ ] Horizontal scroll (if server mouse supports it)

### Reconnect
- [ ] Disconnect the server and reconnect — client re-establishes without restart

---

## Known issues to watch for

### Mouse movement feels jerky or slow
`REL_X` and `REL_Y` arrive as separate lines; `syn()` is called after each one so the accumulator may flush with only dx or dy. This produces two small moves instead of one diagonal move per event cycle, which is usually imperceptible but may feel slightly off. If noticeable, the fix is to buffer events until `EV_SYN` (type=0) arrives in the stream rather than flushing on every `syn()` call — change `process_data()` in `client.py` to not call `syn()` for non-SYN events.

### Key codes wrong for non-US keyboard layouts
The `_KEY_MAP` in `virtual_input_macos.py` maps evdev scancode positions (US ANSI physical layout). If the Mac is set to a different layout, some keys will produce wrong characters. This is a known limitation — the server sends hardware scancodes, and macOS interprets them through its own keyboard layout. Usually fine for standard typing; may need adjustments for special characters.

### CGEvent.post silently drops events
If Accessibility permission is not granted to the exact Python binary, all events are silently discarded. `AXIsProcessTrusted()` returns `False`. Re-grant in System Settings.

### Scroll direction inverted
macOS default is "natural" scrolling (content follows finger). The server sends Linux wheel delta signs. If scroll feels inverted, negate `v` and `h` in `MacOSVirtualInput._post_scroll()`.

---

## Setting up the launchd service

Once manual testing passes:

```bash
bash nkms/install_macos_service.sh
```

Verify it started:
```bash
launchctl list | grep nkms
tail -f /tmp/nkms-client.log
```

The service runs as the logged-in user — no root required.

**Important:** grant Accessibility permission to the Python binary that the service uses (same path as `which python3` or the venv python). The service runs with the same environment as your shell, so this is usually the same binary you tested with.

---

## Iterating on `virtual_input_macos.py`

After testing, the most likely changes needed:

1. **Key code corrections** — edit `_KEY_MAP` for any wrong keys
2. **Scroll direction** — negate delta signs in `_post_scroll` if inverted
3. **Mouse speed** — `CGEventCreateMouseEvent` with absolute position means mouse speed is determined entirely by the server's delta values, which are the raw evdev deltas. Usually fine; macOS pointer acceleration is applied on top
4. **Missing keys** — add entries to `_KEY_MAP` for any unmapped codes (the `_post_key` method silently skips unknown codes)

---

## Feeding changes back

After Phase 2 iteration, commit and push from the Mac. Any changes to `virtual_input_macos.py` (key table corrections, scroll direction, etc.) should be committed with a note about what was observed on the Mac so the Linux session can continue from a known-good state.
