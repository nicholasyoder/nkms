from evdev import UInput

from nkms.core.constants import NKMS_UINPUT_NAME


class LinuxVirtualInput:
    def __init__(self, capabilities: dict):
        self._ui = UInput(events=capabilities, name=NKMS_UINPUT_NAME)

    def write(self, type: int, code: int, value: int) -> None:
        self._ui.write(type, code, value)

    def syn(self) -> None:
        self._ui.syn()

    def close(self) -> None:
        self._ui.close()
