import sys
import threading
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import QObject
from settings import SettingsWindow, NkmsSettings
from notify import error_notify


class NkmsQt(QObject):
    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()
        self.nkms_thread = None
        self.nkms_daemon = None
        self.settings_window = None
        self.tray_icon = None
        self.start_action = None
        self.stop_action = None
        self.tray_menu = None

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
        self.stop_action.setDisabled(True)
        quit_action = self.tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            if self.nkms_daemon and self.nkms_daemon.running:
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
        if self.settings.mode == "Client":
            from client import NkmsClient
            self.nkms_daemon = NkmsClient()
            self.nkms_thread = threading.Thread(target=self.nkms_daemon.run)
            self.nkms_thread.daemon = True
            self.nkms_thread.start()
        else:
            pass

    def stop_nkms(self):
        if not (self.nkms_daemon or self.nkms_thread):
            error_notify('Unable to stop daemon')
            return

        self.nkms_daemon.stop()
        self.nkms_thread.join(timeout=5)
        if self.nkms_thread.is_alive():
            error_notify('Daemon did not stop')
            return


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    nkms_qt = NkmsQt()
    nkms_qt.initialize()
    nkms_qt.start_nkms()
    sys.exit(app.exec())
