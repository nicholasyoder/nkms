import sys
import os
import configparser
from typing import Any

if sys.platform == 'darwin':
    _CONFIG_PATH = os.path.expanduser('~/.config/nkms/nkms.conf')
    _USE_QT = False
else:
    _CONFIG_PATH = '/etc/nkms/nkms.conf'
    _USE_QT = True


class _ConfigParserAdapter:
    """QSettings-compatible adapter backed by configparser (macOS only).

    sync() reads from disk when clean, writes to disk when dirty — matching
    the QSettings call pattern used by NkmsSettings.load() and .save().
    Top-level keys (no '/') live in [General] to match QSettings INI format.
    """

    def __init__(self, path: str):
        self._path = path
        self._cp = configparser.ConfigParser()
        self._dirty = False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._cp.read(path)

    def value(self, key: str, default=None):
        section, option = self._split_key(key)
        try:
            return self._cp.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def setValue(self, key: str, value) -> None:
        section, option = self._split_key(key)
        if not self._cp.has_section(section):
            self._cp.add_section(section)
        self._cp.set(section, option, str(value))
        self._dirty = True

    def sync(self) -> None:
        if self._dirty:
            with open(self._path, 'w') as f:
                self._cp.write(f)
            self._dirty = False
        else:
            self._cp.clear()
            self._cp.read(self._path)

    @staticmethod
    def _split_key(key: str) -> tuple[str, str]:
        if '/' in key:
            section, option = key.split('/', 1)
            return section, option
        return 'General', key


class NkmsSettings:
    def __init__(self):
        if _USE_QT:
            from PyQt6.QtCore import QSettings
            self.settings = QSettings(_CONFIG_PATH, QSettings.Format.IniFormat)
        else:
            self.settings = _ConfigParserAdapter(_CONFIG_PATH)
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
        for key, value in self.get_settings_dict().items():
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
