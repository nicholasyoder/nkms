import notify2


INITIALIZED = False


def initialize_notify2():
    global INITIALIZED
    if INITIALIZED:
        return True

    try:
        notify2.init('NKMS')
        INITIALIZED = True
    except Exception:
        print("Warning: notify2 init failed")

    return INITIALIZED


def notify(title, text, icon="application-x-executable", timeout=8000):
    global INITIALIZED
    print(f"{title}: {text}")

    if not initialize_notify2():
        return

    try:
        n = notify2.Notification(title, text, icon)
        n.set_timeout(timeout)
        n.show()
    except Exception:
        INITIALIZED = False
        if initialize_notify2():
            notify(title, text, icon, timeout)


def warning_notify(msg):
    notify("Warning", msg, "dialog-warning")


def error_notify(msg):
    notify("Error", msg, "dialog-error")


def info_notify(msg):
    notify("Notice", msg, "dialog-information", 4000)
