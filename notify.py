#!/usr/bin/env python3

import os
import pwd
import subprocess


def get_display(username):
    cmd = f"who | grep {username} | grep -oP '\\(\\K:[0-9]+' | head -n 1"
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return None


SUDO_USER = os.environ.get('SUDO_USER') or os.environ.get('USER')
USER_ID = pwd.getpwnam(SUDO_USER).pw_uid
DISPLAY = get_display(SUDO_USER)


def notify(title, text, icon="application-x-executable", timeout=8000):
    print(f"{title}: {text}")

    dbus_address = f"unix:path=/run/user/{USER_ID}/bus"
    cmd = [
        'sudo', '-u', SUDO_USER,
        f'DISPLAY={DISPLAY}',
        'DBUS_SESSION_BUS_ADDRESS=' + dbus_address,
        'notify-send',
        '-a', 'NKMS',
        '-t', str(timeout),
        '-i', icon,
        title,
        text
    ]
    subprocess.run(cmd)


def warning_notify(msg):
    notify("Warning", msg, "dialog-warning")


def error_notify(msg):
    notify("Error", msg, "dialog-error")


def info_notify(msg):
    notify("Notice", msg, "dialog-information", 4000)
