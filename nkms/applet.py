import sys
from typing import Any
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject
from PyQt6.QtDBus import QDBusConnection, QDBusMessage

from nkms.core.settings import NkmsSettings
from nkms.core.settings_window import SettingsWindow


class NkmsQt(QObject):
    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()
        self.settings_window = None
        self.tray_icon = None
        self.start_action = None
        self.stop_action = None
        self.tray_menu = None

        # Connect to the session bus
        self.bus = QDBusConnection.systemBus()
        if not self.bus.isConnected():
            print("Cannot connect to the D-Bus session bus")
            sys.exit(1)

    def initialize(self):
        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("nkms"), self)

        self.tray_menu = QMenu()
        show_action = self.tray_menu.addAction("Settings")
        show_action.triggered.connect(self.show_settings)
        self.start_action = self.tray_menu.addAction("Start")
        self.start_action.triggered.connect(self.start_nkms)
        self.stop_action = self.tray_menu.addAction("Stop")
        self.stop_action.triggered.connect(self.stop_nkms)
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_menu.aboutToShow.connect(self._update_menu_state)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def call_daemon(self, method: str, args: list[Any] | None = None) -> Any:
        """Call daemon method via dbus"""
        message = QDBusMessage.createMethodCall(
            'org.nkms',
            '/org/nkms',
            'org.nkms',
            method,
        )
        if args:
            message.setArguments(args)

        reply = self.bus.call(message)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            print("Error:", reply.errorMessage())
            return None

        return reply.arguments()[0] if len(reply.arguments()) == 1 else reply.arguments()

    def _update_menu_state(self):
        running = self.call_daemon('is_running') is True
        self.stop_action.setDisabled(not running)
        self.start_action.setDisabled(running)

    def show_settings(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow()
            self.settings_window.settings_saved.connect(self.save_settings)
        self.settings_window.show()

    def save_settings(self, settings_dict: dict[str, Any]) -> None:
        self.call_daemon(method='save_settings', args=[settings_dict])

    def start_nkms(self):
        self.call_daemon('start')

    def stop_nkms(self):
        self.call_daemon('stop')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    nkms_qt = NkmsQt()
    nkms_qt.initialize()
    sys.exit(app.exec())
