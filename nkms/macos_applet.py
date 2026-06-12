import importlib.resources
import signal
import sys
import threading
from typing import Any

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject

from nkms.core.settings import NkmsSettings
from nkms.core.settings_window import SettingsWindow


def _check_accessibility():
    from ApplicationServices import AXIsProcessTrusted
    if not AXIsProcessTrusted():
        print(
            "ERROR: Accessibility permission not granted.\n"
            "Open System Settings → Privacy & Security → Accessibility\n"
            "and add the Python interpreter running this script:\n"
            f"  {sys.executable}"
        )
        sys.exit(1)


class NkmsQt(QObject):
    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()
        self.settings_window = None
        self.tray_icon = None
        self.start_action = None
        self.stop_action = None
        self.tray_menu = None
        self._client = None
        self._client_thread = None

    def initialize(self):
        _bundled = importlib.resources.files("nkms") / "logo" / "nkms.png"
        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("nkms", QIcon(str(_bundled))), self)

        self.tray_menu = QMenu()
        show_action = self.tray_menu.addAction("Settings")
        show_action.triggered.connect(self.show_settings)
        self.start_action = self.tray_menu.addAction("Start")
        self.start_action.triggered.connect(self.start_nkms)
        self.stop_action = self.tray_menu.addAction("Stop")
        self.stop_action.triggered.connect(self.stop_nkms)
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

        self.tray_menu.aboutToShow.connect(self._update_menu_state)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        self.start_nkms()

    def is_running(self) -> bool:
        return bool(self._client and self._client.running)

    def _update_menu_state(self):
        running = self.is_running()
        self.stop_action.setDisabled(not running)
        self.start_action.setDisabled(running)

    def show_settings(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow(client_only=True)
            self.settings_window.settings_saved.connect(self.save_settings)
        self.settings_window.show()

    def save_settings(self, settings_dict: dict[str, Any]) -> None:
        self.settings.save_settings_dict(settings_dict=settings_dict)

    def start_nkms(self):
        if self.is_running():
            return
        self.settings.load()
        from nkms.core.client import NkmsClient
        self._client = NkmsClient()
        self._client_thread = threading.Thread(target=self._client.run, daemon=True)
        self._client_thread.start()

    def stop_nkms(self):
        if self._client:
            self._client.stop()
            self._client_thread.join(timeout=5)
            self._client = None
            self._client_thread = None

    def _quit(self):
        self.stop_nkms()
        QApplication.instance().quit()


def main():
    _check_accessibility()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from AppKit import NSApp, NSApplicationActivationPolicyAccessory
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    nkms_qt = NkmsQt()
    nkms_qt.initialize()

    def _shutdown(signum, frame):
        nkms_qt.stop_nkms()
        app.quit()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
