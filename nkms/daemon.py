import sys
import threading
from typing import Any

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtDBus import QDBusConnection
from PyQt6.QtCore import QCoreApplication

from nkms.core.settings import NkmsSettings


class NkmsDaemon(QObject):

    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()
        self.nkms_thread = None
        self.nkms_daemon = None

    @pyqtSlot()
    def start(self) -> None:
        print(f"Starting NKMS daemon...")
        self.settings.load()
        if self.settings.mode == "Client":
            print(self.settings.mode)
            from nkms.core.client import NkmsClient
            self.nkms_daemon = NkmsClient()
        else:
            from nkms.core.server import NkmsServer
            self.nkms_daemon = NkmsServer()

        self.nkms_thread = threading.Thread(target=self.nkms_daemon.run)
        self.nkms_thread.daemon = True
        self.nkms_thread.start()

    @pyqtSlot()
    def stop(self) -> None:
        print(f"Stopping NKMS daemon...")
        if not (self.nkms_daemon or self.nkms_thread):
            print('Failed to stop.')
            return

        self.nkms_daemon.stop()
        self.nkms_thread.join(timeout=5)
        if self.nkms_thread.is_alive():
            print('Failed to stop.')
            return

    @pyqtSlot(result=bool)
    def is_running(self) -> bool:
        if self.nkms_daemon and self.nkms_daemon.running:
            return True

        return False

    @pyqtSlot('QVariantMap')
    def save_settings(self, settings_dict: dict[str, Any]) -> None:
        self.settings.save_settings_dict(settings_dict=settings_dict)


def register_on_dbus(nkms_daemon: NkmsDaemon) -> bool:
    """Register nkms daemon object on dbus.
    Returns True on success and False on failure.
    """
    bus = QDBusConnection.systemBus()
    if not bus.isConnected():
        print("Cannot connect to the D-Bus system bus.")
        return False

    object_path = "/org/nkms"
    service_name = "org.nkms"
    interface_name = "org.nkms"

    if not bus.registerObject(object_path, interface_name, nkms_daemon, QDBusConnection.RegisterOption.ExportAllSlots):
        print(bus.lastError())
        print(f"Failed to register object at {object_path} on D-Bus.")
        return False

    if not bus.registerService(service_name):
        print(bus.lastError().message())
        print(f"Failed to register service name {service_name} on D-Bus.")
        return False

    print(f"D-Bus service '{service_name}' is registered at '{object_path}'.")
    return True


if __name__ == "__main__":
    app = QCoreApplication(sys.argv)

    daemon = NkmsDaemon()
    if not register_on_dbus(nkms_daemon=daemon):
        print('Failed to register on D-Bus. The applet will be unable to control the daemon.')

    daemon.start()
    sys.exit(app.exec())