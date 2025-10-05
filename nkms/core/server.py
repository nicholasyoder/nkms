import select
import json
from enum import IntEnum
from typing import Final

import evdev
import socket
import threading
from time import time

from nkms.core.settings import NkmsSettings
from nkms.utils.udp_socket import UdpSocket

client_lock = threading.Lock()
SERVER_CLIENT_INDEX: Final = -1
CLIENT_ACTIVITY_TIMEOUT: Final = 5  # drop clients after 5 seconds with no pings.

class KeyEventType(IntEnum):
    KEY_UP = 0
    KEY_DOWN = 1
    KEY_REPEAT = 2


def get_km_devices() -> list[evdev.InputDevice]:
    """Get devices that have capabilities that look like a keyboard or mouse."""
    devs = []
    all_devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for dev in all_devices:
        cap = dev.capabilities()
        ec = evdev.ecodes
        if ec.EV_KEY in cap:
            keys = cap[ec.EV_KEY]
            if ec.BTN_LEFT in keys or (ec.KEY_A in keys and ec.KEY_Z in keys):
                devs.append(dev)
    return devs


def get_capabilities(devices: list) -> dict:
    """Get capabilities dict for the provided devices."""
    new_caps = {}
    for dev in devices:
        dev_caps = dev.capabilities()
        for k in dev_caps.keys():
            if k not in new_caps.keys():
                new_caps[k] = []

            if k == 0:
                continue

            a = dev_caps[k]
            for v in a:
                if v not in new_caps[k]:
                    new_caps[k].append(v)

    return new_caps


class NkmsServer:

    def __init__(self):
        self.settings = NkmsSettings()
        self.keys_activated = False
        self.key1_down = False
        self.key2_down = False
        #self.grab_status = defaultdict(lambda : False)
        self.devices = []
        self.clients = []
        self.client_index = SERVER_CLIENT_INDEX
        self.running = False
        self.threads = []
        self.activity: dict[str, float] = {}  # dict mapping clients to their last active timestamp
        self.stop_event = threading.Event()
        self.uinput = None
        self.capabilities = {}

    def get_next_client(self):
        """Set socket_index to next value to cycle through outputs."""
        if self.client_index >= len(self.clients) - 1:
            self.client_index = SERVER_CLIENT_INDEX
        else:
            self.client_index = self.client_index + 1

    def _maybe_get_next_client(self, key_code: int) -> bool:
        """Go to next client if switch key sequence has been pressed."""
        got_next_client = False
        if key_code == self.settings.server_key1:
            if (
                self.key1_down is True and  # key1 is releasing
                (
                    self.settings.server_key2 == 0 or  # key2 is undefined or
                    (self.keys_activated is True and self.key2_down is False)  # key2 was pressed and released
                )
            ):
                # without key2: key1 was pressed, and is now releasing
                # with key2: key1 was pressed, key2 was pressed, key2 was released, key1 is now releasing
                self.get_next_client()
                self.keys_activated = False
                got_next_client = True

            self.key1_down = not self.key1_down

        elif key_code == self.settings.server_key2:
            if self.key2_down is True and self.keys_activated is True and self.key1_down is False:
                # key1 was pressed, key2 was pressed, key1 released, now key2 is releasing
                self.get_next_client()
                self.keys_activated = False
                got_next_client = True

            if self.key1_down is True:
                self.keys_activated = True

            self.key2_down = not self.key2_down

        return got_next_client

    def send_event_to_client(self, event, sock, data_port) -> None:
        """Send event to client."""
        if self.client_index == SERVER_CLIENT_INDEX:
            self.uinput.write_event(event)
            self.uinput.syn()
            return

        with client_lock:  # Protect clients list access
            if self.clients:
                client = self.clients[self.client_index]
                try:
                    sock.send_string_to(
                        string=f"{json.dumps([event.type, event.code, event.value])}\n",
                        to=(client, data_port),
                    )
                except OSError as e:
                    print(f'Error sending to {client}: {e!s}')
                    self.clients.remove(client)
                    self.get_next_client()

    def _make_key1_press_from_event(self, event: evdev.InputEvent) -> evdev.InputEvent:
        """Create a key1 press event to immediately precede the given event."""
        return evdev.InputEvent(
            sec=event.sec,
            usec=event.usec - 1,
            type=evdev.ecodes.EV_KEY,
            code=self.settings.server_key1,
            value=KeyEventType.KEY_DOWN,
        )

    def handle_events(self, device):
        """Start loop to listen for device's events."""
        sock = UdpSocket()
        data_port = self.settings.server_port + 1  # just use the next higher port
        device.grab()
        prevented_key1_press = False

        while self.running:
            read_ready, _, _ = select.select([device.fd], [], [], 0.1)  # 0.1 second timeout
            if not read_ready:
                continue

            for event in device.read():
                if not self.running:
                    break

                if (
                    event.type == evdev.ecodes.EV_KEY and
                    event.value in (KeyEventType.KEY_UP, KeyEventType.KEY_DOWN)
                ):
                    if event.code in (self.settings.server_key1, self.settings.server_key2):
                        prevented_key1_press = False
                        got_next_client = self._maybe_get_next_client(key_code=event.code)
                        if (
                            event.value == KeyEventType.KEY_UP and
                            event.code == self.settings.server_key1 and
                            not got_next_client and
                            not self.key2_down
                        ):  # key1 up without it being part of our key sequence
                            # create a press event and then allow this release event to go through
                            self.send_event_to_client(self._make_key1_press_from_event(event), sock, data_port)
                        elif (
                            event.code == self.settings.server_key2 and
                            not got_next_client and
                            not self.key1_down and
                            not self.keys_activated
                        ):  # key2 up/down event without key2 being pressed first
                            pass  # allow event
                        else:  # otherwise prevent the key event from going through.
                            if event.code == self.settings.server_key1 and event.value == 1:
                                prevented_key1_press = True

                            continue
                    elif prevented_key1_press:
                        # we prevented the key1 press event, but now have an unrelated event.
                        # send the key1 press that was prevented earlier, so that it can be part
                        # of some other key sequence caught by another app.
                        self.send_event_to_client(self._make_key1_press_from_event(event), sock, data_port)
                        prevented_key1_press = False

                self.send_event_to_client(event, sock, data_port)

        device.close()

    def maybe_drop_inactive_clients(self):
        now = time()
        with client_lock:
            for client in self.clients:
                if client not in self.activity:
                    print("Warning: have client with no activity timestamp!")
                    continue  # shouldn't ever happen

                if now - self.activity[client] >= CLIENT_ACTIVITY_TIMEOUT:
                    print(f'Dropping inactive client: {client}')
                    should_get_next = self.client_index == self.clients.index(client)
                    self.clients.remove(client)
                    if should_get_next:
                        self.get_next_client()

    def maybe_process_client_data(self, sock: UdpSocket) -> None:
        try:
            data, (address, port) = sock.recvfrom(1024)
        except socket.timeout:
            return

        if data == b'ping':  # update active timestamp for this client
            sock.send_string_to(string='pong', to=(address, port))
            self.activity[address] = time()
        elif data == b'get devices':
            sock.send_string_to(
                string=f"{json.dumps(self.capabilities)}\n",
                to=(address, port),
            )
            print(f"Sent device list to: {address}")
        elif data == b'initialized':
            with client_lock:
                if address not in self.clients:  # prevent duplicate entries
                    self.clients.append(address)
                    self.activity[address] = time()
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
        self.uinput = evdev.UInput(self.capabilities, name='NetKMSwitch Keyboard and Mouse')
        self.threads = []
        for device in self.devices:
            print(f'Loading input device: {device.path}')
            self.threads.append(threading.Thread(
                target=self.handle_events,
                args=(evdev.InputDevice(device.path),),
            ))

        self.threads.append(threading.Thread(
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
        self.stop_event.set()
        for thread in self.threads:
            thread.join()

        print('NKMS Server Stopped')


if __name__ == "__main__":
    nkms_server = NkmsServer()
    nkms_server.run()