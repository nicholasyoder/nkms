from typing import Any

from PyQt6.QtCore import QSettings


class NkmsSettings:
    def __init__(self):
        self.settings = QSettings("/etc/nkms/nkms.conf", QSettings.Format.IniFormat)
        # Defaults
        self.mode = "Client"
        self.client_server = ""
        self.client_port = 4777
        self.server_address = "0.0.0.0"
        self.server_port = 4777
        self.server_key1 = 125
        self.server_key2 = 41
        # Load saved values
        self.load()

    def load(self):
        self.settings.sync()
        self.mode = self.settings.value("mode", self.mode)
        self.client_server = self.settings.value("client/server", self.client_server)
        self.client_port = int(self.settings.value("client/port", self.client_port))
        self.server_address = self.settings.value("server/bind_address", self.server_address)
        self.server_port = int(self.settings.value("server/port", self.server_port))
        self.server_key1 = int(self.settings.value("server/key1", self.server_key1))
        self.server_key2 = int(self.settings.value("server/key2", self.server_key2))

    def save(self):
        for key, value in self.get_settings_dict():
            self.settings.setValue(key, value)
        self.settings.sync()

    def get_settings_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "client/server": self.client_server,
            "client/port": self.client_port,
            "server/bind_address": self.server_address,
            "server/port": self.server_port,
            "server/key1": self.server_key1,
            "server/key2": self.server_key2,
        }

    def save_settings_dict(self, settings_dict: dict[str, Any]) -> None:
        for key, value in settings_dict.items():
            self.settings.setValue(key, value)
