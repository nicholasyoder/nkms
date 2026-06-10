from evdev import UInput


class LinuxVirtualInput:
    def __init__(self, capabilities: dict):
        self._ui = UInput(events=capabilities, name='NetKMSwitch Keyboard and Mouse')

    def write(self, type: int, code: int, value: int) -> None:
        self._ui.write(type, code, value)

    def syn(self) -> None:
        self._ui.syn()

    def close(self) -> None:
        self._ui.close()
