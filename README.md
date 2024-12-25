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


## Options

* `Mode` Controls whether the daemon is running as `Server` or `Client`

**Server Mode:**  
Captures keyboard and mouse input and forwards it to the clients.
This mode should be enabled **only** on the machine where your physical 
keyboard and mouse are plugged in.
* `Input Switch Keys` - Default: `Left Meta + Grave (Tilde)`  
    Hotkey used to switch input between machines in the following order:  
    - Server
    - Each client in the order they connected
    - Back to server again
* `Bind Address` - Default: `0.0.0.0`  
    Address to bind to when listening for client connections.
* `Port` - Default: `4777`  
    Port to listen for client connections on. The next higher port will also 
    be used for the actual transfer of events from server to client.  

**Client Mode:**  
Receives input from the server and sends it to the system 
through a virtual input device. This mode must be used on all machines 
you want to control from the server.
* `Server` - Blank by default. **Must be configured by user.**  
    IP Address or hostname of the server machine
* `Port` - Default: `4777`  
    Port to connect to the server on. The next higher port will also be used for 
    the actual transfer of events from server to client.  

**Important:** Ensure all machines are configured to use the same port number.
