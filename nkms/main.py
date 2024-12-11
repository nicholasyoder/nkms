import sys
from typing import Any
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import QObject
from PyQt6.QtDBus import QDBusConnection, QDBusMessage

from nkms.core.settings import SettingsWindow, NkmsSettings


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
        # TODO: load icon theme from qt5ctl settings file
        QIcon.setThemeName('Papirus')
        icon = QIcon.fromTheme("application-x-executable")
        self.tray_icon = QSystemTrayIcon(icon, self)

        self.tray_menu = QMenu()
        show_action = self.tray_menu.addAction("Settings")
        show_action.triggered.connect(self.show_settings)
        self.start_action = self.tray_menu.addAction("Start")
        self.start_action.triggered.connect(self.start_nkms)
        self.stop_action = self.tray_menu.addAction("Stop")
        self.stop_action.triggered.connect(self.stop_nkms)
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.activated.connect(self.tray_icon_activated)
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

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            if self.call_daemon('is_running') is True:
                self.stop_action.setDisabled(False)
                self.start_action.setDisabled(True)
            else:
                self.stop_action.setDisabled(True)
                self.start_action.setDisabled(False)
            self.tray_menu.exec(QCursor.pos())

    def show_settings(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow()
        self.settings_window.show()

    def start_nkms(self):
        self.call_daemon('start')

    def stop_nkms(self):
        self.call_daemon('stop')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    nkms_qt = NkmsQt()
    nkms_qt.initialize()
    nkms_qt.start_nkms()
    sys.exit(app.exec())
