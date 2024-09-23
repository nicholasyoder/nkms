# NKMS

NKMS is an acronym for Network Keyboard Mouse Switch. NKMS switches keyboard 
and mouse input between muliple computers connected via the network using TCP.
This allows you to only have one keyboard and mouse on your desk even if you 
are using mulitple computers at once. The right control key switches the input
between machines.

There is virtually no lag when used with a good ethernet connection, but 
it may lag a bit over wifi, especially if the signal is weak.


## Dependencies

NKMS depends on the following:
* PyQt6
* evdev

Install with `pip`:
```commandline
pip install PyQt6 evdev
```

Install with `apt`:
```commandline
sudo apt install python-pyqt6 python-evdev
```

## Configuration and Usage

NKMS is controlled via a system tray icon. The tray icon's context menu allows
you to open the settings, start / stop the NKMS daemon, etc.

The machine your keyboard and mouse are connected to should be set to `Server` 
mode, and all other machines should be set to `Client` mode as well as having
the `Server` address set. Be sure to set all machines to use the same port 
number.

NKMS must run as root, otherwise it cannot access the input devices.

## Autostart at login

First, since NKMS must run as root, you need to allow the `nkms` script 
to be run with sudo without requiring a password.

1. `sudo visudo`
2. Add this line: `yourusername ALL=(ALL) NOPASSWD: /path/to/nkms`

Then using your desktop's autostart functionality, set the following command
to autostart on login: `sudo /path/to/nkms`

