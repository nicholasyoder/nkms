from PyQt6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QStackedLayout, \
    QComboBox, QLabel, QGroupBox, QGridLayout, QLineEdit

from PyQt6.QtCore import QSettings


class NkmsSettings:
    def __init__(self):
        self.settings = QSettings("nkms")
        # Defaults
        self.mode = "Client"
        self.client_server = ""
        self.client_port = "4777"
        self.server_address = "0.0.0.0"
        self.server_port = "4777"
        # Load saved values
        self.load()

    def load(self):
        self.mode = self.settings.value("mode", self.mode)
        self.client_server = self.settings.value("client/server", self.client_server)
        self.client_port = self.settings.value("client/port", self.client_port)
        self.server_address = self.settings.value("server/bind_address", self.server_address)
        self.server_port = self.settings.value("server/port", self.server_port)

    def save(self):
        self.settings.setValue("mode", self.mode)
        self.settings.setValue("client/server", self.client_server)
        self.settings.setValue("client/port", self.client_port)
        self.settings.setValue("server/bind_address", self.server_address)
        self.settings.setValue("server/port", self.server_port)
        self.settings.sync()


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = NkmsSettings()

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
        self.client_port_input = QLineEdit()
        client_base_layout.addWidget(self.client_port_input, 1, 1)
        client_gbox.setLayout(client_base_layout)
        self.stacked_layout.addWidget(client_gbox)

        server_gbox = QGroupBox("Server Settings")
        server_base_layout = QGridLayout()
        server_base_layout.addWidget(QLabel("Bind Address:"), 0, 0)
        self.server_address_input = QLineEdit()
        server_base_layout.addWidget(self.server_address_input, 0, 1)
        server_base_layout.addWidget(QLabel("Port:"), 1, 0)
        self.server_port_input = QLineEdit()
        server_base_layout.addWidget(self.server_port_input, 1, 1)
        server_gbox.setLayout(server_base_layout)
        self.stacked_layout.addWidget(server_gbox)

        base_layout.addLayout(self.stacked_layout)

        base_layout.addSpacing(5)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        close_bt = QPushButton("Close")
        buttons_layout.addWidget(close_bt)
        apply_bt = QPushButton("Apply")
        buttons_layout.addWidget(apply_bt)
        buttons_layout.addStretch(1)
        base_layout.addLayout(buttons_layout)

        self.setLayout(base_layout)

        self.mode_select.activated.connect(self.stacked_layout.setCurrentIndex)
        close_bt.clicked.connect(self.close)
        apply_bt.clicked.connect(self.apply_settings)

        self.load_settings()

    def load_settings(self):
        self.mode_select.setCurrentText(self.settings.mode)
        self.client_server_input.setText(self.settings.client_server)
        self.client_port_input.setText(self.settings.client_port)
        self.server_address_input.setText(self.settings.server_address)
        self.server_port_input.setText(self.settings.server_port)
        self.stacked_layout.setCurrentIndex(self.mode_select.currentIndex())

    def apply_settings(self):
        self.settings.mode = self.mode_select.currentText()
        self.settings.client_server = self.client_server_input.text()
        self.settings.client_port = self.client_port_input.text()
        self.settings.server_address = self.server_address_input.text()
        self.settings.server_port = self.server_port_input.text()
        self.settings.save()
