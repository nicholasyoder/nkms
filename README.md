# NKMS - Network Keyboard Mouse Switch

NKMS allows control of multiple computers 
on the local network using a single keyboard and mouse.

Response time is near-instantaneous when used with a stable ethernet connection, 
but some lag may occur when using Wi-Fi.


## Architecture

NKMS consists of two main components:

* `nkms-daemon`  
    This handles the core functionality of capturing, forwarding, and creating input events.
    It requires root privileges and is managed by a systemd service.
* `nkms-applet`  
    This provides a system tray icon for controlling the daemon via D-Bus.
    The tray icon's context menu allows you to open the settings, start/stop the daemon, etc.


## Configuration

NKMS can be configured via the GUI or by manually editing the configuration file.

**GUI Configuration:**

1. Right-click the NKMS system tray icon and click `Settings`.
2. Modify the settings as needed and click `Save`.
3. Restart the daemon via the `Stop` and `Start` menu items.

**Manual Configuration:**

1. Edit the configuration file located at `/etc/nkms/nkms.conf`.
2. Restart the systemd service: `sudo systemctl restart nkms`.


## Operation Modes

* **Server Mode:**  
    The server captures keyboard and mouse input and forwards it to the clients.
    This mode should be enabled **only** on the machine where your physical 
    keyboard and mouse are plugged in.
* **Client Mode:**  
    The client receives input from the server and sends it to the system 
    through a virtual input device. This mode must be enabled on all machines 
    you want to control from the server.
    You must configure the server's IP address or hostname in the client settings.

**Important:** Ensure all machines are configured to use the same port number.


## Usage

Press the right control key to switch input between machines.
The order is server, then each client in the order they connected,
then back to the server.

The hotkey is currently hardcoded to the right control key,
but this will be configurable in a future release.