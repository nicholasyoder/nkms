from typing import Final

from evdev import InputDevice, list_devices, ecodes
from json import dumps as json_dumps
from time import time
from threading import Event, Lock, Thread

from nkms.core.event_handler import EventHandler
from nkms.core.settings import NkmsSettings
from nkms.utils.udp_socket import UdpSocket

client_lock = Lock()
SERVER_CLIENT_INDEX: Final = -1
CLIENT_ACTIVITY_TIMEOUT: Final = 5  # drop clients after 5 seconds with no pings.


def get_km_devices() -> list[InputDevice]:
    """Get devices that have capabilities that look like a keyboard or mouse."""
    devs = []
    for dev in [InputDevice(path) for path in list_devices()]:
        cap = dev.capabilities()
        if ecodes.EV_KEY in cap:
            keys = cap[ecodes.EV_KEY]
            if ecodes.BTN_LEFT in keys or (ecodes.KEY_A in keys and ecodes.KEY_Z in keys):
                devs.append(dev)
    return devs


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

    def listen_for_client_data(self, address, port):
        sock = UdpSocket(timeout=2)
        sock.bind((address, port))
        print(f"Listening for clients on port {port}")
        while self.running:
            self.maybe_drop_inactive_clients()
            self.maybe_process_client_data(sock)

    def run(self):
        print('Starting NKMS Server ...')
        self.running = True
        self.devices = get_km_devices()
        self.capabilities = get_capabilities(self.devices)
        self.event_handler = EventHandler(
            settings=self.settings,
            device_capabilities=self.capabilities,
        )
        self.threads = []
        for device in self.devices:
            print(f'Loading input device: {device.path}')
            self.threads.append(Thread(
                target=self.event_handler.handle_events,
                args=(device,),
            ))

        self.threads.append(Thread(
            target=self.listen_for_client_data,
            args=(
                self.settings.server_address,
                self.settings.server_port,
            ),
        ))

        for thread in self.threads:
            thread.daemon = True
            thread.start()

        print('NKMS Server Started')
        self.stop_event.wait()

    def stop(self):
        self.running = False
        if self.event_handler:
            self.event_handler.running = False
        self.stop_event.set()
        for thread in self.threads:
            thread.join()

        print('NKMS Server Stopped')


if __name__ == "__main__":
    nkms_server = NkmsServer()
    nkms_server.run()