from typing import Optional

from evdev.ecodes import ecodes

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QStackedLayout,
    QComboBox,
    QLabel,
    QGroupBox,
    QGridLayout,
    QLineEdit,
    QSpinBox,
)

from nkms.core.settings import NkmsSettings


def get_key_from_value(d, val):
    keys = [k for k, v in d.items() if v == val]
    return keys[0] if keys else None


class SettingsWindow(QWidget):

    settings_saved = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()
        self.keys = ''
        self.waiting_for_keys = False

        self.setWindowTitle("NKMS Settings")
        base_layout = QVBoxLayout()
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_layout.addWidget(mode_label)
        self.mode_select = QComboBox()
        self.mode_select.addItem("Client")
        self.mode_select.addItem("Server")
        mode_layout.addWidget(self.mode_select)
        mode_layout.addStretch(1)
        base_layout.addLayout(mode_layout)
        base_layout.addSpacing(5)
        self.stacked_layout = QStackedLayout()
        client_gbox = QGroupBox("Client Settings")
        client_base_layout = QGridLayout()
        client_base_layout.addWidget(QLabel("Server:"), 0, 0)
        self.client_server_input = QLineEdit()
        client_base_layout.addWidget(self.client_server_input, 0, 1)
        client_base_layout.addWidget(QLabel("Port:"), 1, 0)
        self.client_port_input = QSpinBox()
        self.client_port_input.setRange(0, 65535)
        client_base_layout.addWidget(self.client_port_input, 1, 1)
        client_gbox.setLayout(client_base_layout)
        client_base_layout.addWidget(QLabel("Note: Next higher port will also be used."), 2, 0, 2, 2)
        self.stacked_layout.addWidget(client_gbox)
        server_gbox = QGroupBox("Server Settings")
        server_base_layout = QGridLayout()
        server_base_layout.addWidget(QLabel("Input Switch Keys:"), 0, 0, 2, 1)
        self.key_select_1 = QComboBox()
        server_base_layout.addWidget(self.key_select_1, 0, 1)
        self.key_select_2 = QComboBox()
        server_base_layout.addWidget(self.key_select_2, 1, 1)
        server_base_layout.addWidget(QLabel("Bind Address:"), 2, 0)
        self.server_address_input = QLineEdit()
        server_base_layout.addWidget(self.server_address_input, 2, 1)
        server_base_layout.addWidget(QLabel("Port:"), 3, 0)
        self.server_port_input = QSpinBox()
        self.server_port_input.setRange(0, 65535)
        server_base_layout.addWidget(self.server_port_input, 3, 1)
        server_gbox.setLayout(server_base_layout)
        server_base_layout.addWidget(QLabel("Note: Next higher port will also be used."), 4, 0, 1, 2)
        self.stacked_layout.addWidget(server_gbox)
        base_layout.addLayout(self.stacked_layout)
        base_layout.addSpacing(5)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        close_bt = QPushButton("Close")
        buttons_layout.addWidget(close_bt)
        apply_bt = QPushButton("Save")
        buttons_layout.addWidget(apply_bt)
        buttons_layout.addStretch(1)
        base_layout.addLayout(buttons_layout)
        self.setLayout(base_layout)

        self.mode_select.activated.connect(self.stacked_layout.setCurrentIndex)
        close_bt.clicked.connect(self.close)
        apply_bt.clicked.connect(self.apply_settings)

        self.keys = {'None': 0}
        self.key_select_2.addItem('None', 0)  # second key may be undefined
        for name, value in ecodes.items():
            if name.startswith('KEY_'):
                name = name.removeprefix('KEY_')
                self.keys[name] = value
                self.key_select_1.addItem(name, value)
                self.key_select_2.addItem(name, value)

        self.load_settings()


    def load_settings(self):
        self.mode_select.setCurrentText(self.settings.mode)
        self.client_server_input.setText(self.settings.client_server)
        self.client_port_input.setValue(self.settings.client_port)
        self.server_address_input.setText(self.settings.server_address)
        self.server_port_input.setValue(self.settings.server_port)
        self.stacked_layout.setCurrentIndex(self.mode_select.currentIndex())
        self.key_select_1.setCurrentText(get_key_from_value(self.keys, self.settings.server_key1))
        self.key_select_2.setCurrentText(get_key_from_value(self.keys, self.settings.server_key2))

    def apply_settings(self):
        self.settings.mode = self.mode_select.currentText()
        self.settings.client_server = self.client_server_input.text()
        self.settings.client_port = self.client_port_input.text()
        self.settings.server_address = self.server_address_input.text()
        self.settings.server_port = self.server_port_input.text()
        self.settings.server_key1 = self.keys[self.key_select_1.currentText()]
        self.settings.server_key2 = self.keys[self.key_select_2.currentText()]
        self.settings_saved.emit(self.settings.get_settings_dict())
