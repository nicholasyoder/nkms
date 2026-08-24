from typing import Final

import pyudev
from evdev import InputDevice, list_devices, ecodes
from json import dumps as json_dumps
from time import sleep, time
from threading import Event, Lock, Thread

from nkms.core.constants import NKMS_UINPUT_NAME
from nkms.core.event_handler import EventHandler
from nkms.core.settings import NkmsSettings
from nkms.utils.udp_socket import UdpSocket

client_lock = Lock()
SERVER_CLIENT_INDEX: Final = -1
CLIENT_ACTIVITY_TIMEOUT: Final = 5  # drop clients after 5 seconds with no pings.
DEVICE_OPEN_RETRIES: Final = 5
DEVICE_OPEN_RETRY_DELAY: Final = 0.2  # seconds


def _is_km_device(dev: InputDevice) -> bool:
    """Check whether a device has capabilities that look like a keyboard or mouse."""
    if dev.name == NKMS_UINPUT_NAME:
        return False  # don't grab our own local passthrough device.
    cap = dev.capabilities()
    if ecodes.EV_KEY not in cap:
        return False
    keys = cap[ecodes.EV_KEY]
    return ecodes.BTN_LEFT in keys or (ecodes.KEY_A in keys and ecodes.KEY_Z in keys)


def get_km_devices() -> list[InputDevice]:
    """Get devices that have capabilities that look like a keyboard or mouse."""
    return [dev for dev in (InputDevice(path) for path in list_devices()) if _is_km_device(dev)]


def get_capabilities(devices: list) -> dict:
    """Get capabilities dict for the provided devices."""
    new_caps = {}
    for dev in devices:
        dev_caps = dev.capabilities()
        for k, values in dev_caps.items():
            if k == 0:
                continue

            if k not in new_caps:
                new_caps[k] = []

            for v in values:
                if v not in new_caps[k]:
                    new_caps[k].append(v)

    return new_caps


class NkmsServer:

    def __init__(self):
        self.settings = NkmsSettings()
        self.event_handler = None
        self.devices = []
        self.running = False
        self.threads = []
        self.activity: dict[str, float] = {}  # dict mapping clients to their last active timestamp
        self.stop_event = Event()
        self.capabilities = {}
        self.devices_lock = Lock()
        self._device_threads: dict[str, Thread] = {}

    def maybe_drop_inactive_clients(self):
        now = time()
        inactive_clients = []
        for client in self.activity:
            if now - self.activity[client] >= CLIENT_ACTIVITY_TIMEOUT:
                inactive_clients.append(client)

        for client in inactive_clients:
            print(f'Dropping inactive client: {client}')
            self.activity.pop(client, None)
            self.event_handler.remove_client(client)

    def maybe_process_client_data(self, sock: UdpSocket) -> None:
        try:
            data, (address, port) = sock.recvfrom(1024)
        except TimeoutError:
            return

        if data == b'ping':
            sock.send_string_to(string='pong', to=(address, port))
            if address in self.activity:  # update activity if the device has been initialized.
                self.activity[address] = time()
        elif data == b'get devices':
            sock.send_string_to(
                string=f"{json_dumps(self.capabilities)}\n",
                to=(address, port),
            )
            print(f"Sent device list to: {address}")
        elif data == b'initialized':
            self.activity[address] = time()  # add device address to the activity dict
            self.event_handler.add_client(address)
            print(f"Initialized new client: {address}")

    def _add_device(self, device: InputDevice) -> None:
        """Start a reader thread for a device. Caller holds devices_lock."""
        print(f'Loading input device: {device.path}')
        thread = Thread(target=self.event_handler.handle_events, args=(device,), daemon=True)
        self.devices.append(device)
        self.threads.append(thread)
        self._device_threads[device.path] = thread
        thread.start()

    def _handle_device_added(self, path: str) -> None:
        """Open a newly-plugged-in device node and, if it looks like a keyboard/mouse, start reading it."""
        device = None
        for _ in range(DEVICE_OPEN_RETRIES):
            try:
                device = InputDevice(path)
                break
            except OSError:
                sleep(DEVICE_OPEN_RETRY_DELAY)  # udev may not have finished applying node permissions yet.

        if device is None:
            print(f'Failed to open new input device: {path}')
            return

        with self.devices_lock:
            if path in self._device_threads:
                return  # already tracked (e.g. from the initial scan).
            if not _is_km_device(device):
                return
            self._add_device(device)
            self.capabilities = get_capabilities(self.devices)
            self.event_handler.update_capabilities(self.capabilities)

    def _handle_device_removed(self, path: str) -> None:
        """Drop bookkeeping for a device that has disappeared. Its reader thread exits on its own."""
        with self.devices_lock:
            thread = self._device_threads.pop(path, None)
            if thread is None:
                return
            self.devices = [dev for dev in self.devices if dev.path != path]
            thread.join(timeout=2)
            if thread in self.threads:
                self.threads.remove(thread)
            print(f'Input device removed: {path}')

    def monitor_devices(self) -> None:
        """Watch udev for input devices being plugged in or unplugged."""
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='input')
        monitor.start()

        while self.running:
            device = monitor.poll(timeout=1)
            if device is None:
                continue

            node = device.device_node
            if not node or not node.startswith('/dev/input/event'):
                continue

            if device.action == 'add':
                self._handle_device_added(node)
            elif device.action == 'remove':
                self._handle_device_removed(node)

    def listen_for_client_data(self, address, port):
        sock = UdpSocket(timeout=2)
        while self.running:
            try:
                sock.bind((address, port))
                break
            except OSError as e:
                print(f'Failed to bind to {address}:{port}: {e}. Retrying in 2 seconds...')
                sleep(2)
        print(f"Listening for clients on port {port}")
        while self.running:
            self.maybe_drop_inactive_clients()
            self.maybe_process_client_data(sock)

    def run(self):
        print('Starting NKMS Server ...')
        self.running = True
        self.devices = []
        self.threads = []
        self._device_threads = {}

        initial_devices = get_km_devices()
        self.capabilities = get_capabilities(initial_devices)
        self.event_handler = EventHandler(
            settings=self.settings,
            device_capabilities=self.capabilities,
        )
        with self.devices_lock:
            for device in initial_devices:
                self._add_device(device)

        client_data_thread = Thread(
            target=self.listen_for_client_data,
            args=(
                self.settings.server_address,
                self.settings.server_port,
            ),
            daemon=True,
        )
        monitor_thread = Thread(target=self.monitor_devices, daemon=True)
        self.threads.append(client_data_thread)
        self.threads.append(monitor_thread)
        client_data_thread.start()
        monitor_thread.start()

        print('NKMS Server Started')
        self.stop_event.wait()

    def stop(self):
        self.running = False
        if self.event_handler:
            self.event_handler.running = False
        self.stop_event.set()
        with self.devices_lock:
            threads = list(self.threads)
        for thread in threads:
            thread.join()

        print('NKMS Server Stopped')


if __name__ == "__main__":
    nkms_server = NkmsServer()
    nkms_server.run()