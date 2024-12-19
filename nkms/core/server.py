import select
import json
import evdev
import socket
import threading
from time import sleep, time

from nkms.core.settings import NkmsSettings
from nkms.utils.notify import info_notify, warning_notify

client_lock = threading.Lock()


def get_km_devices() -> list:
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
        self.toggle_key_down = False
        self.grabbing = False
        self.grab_status = {}
        self.devices = []
        self.clients = []
        self.client_index = -1
        self.running = False
        self.threads = []
        self.activity: dict[str, float] = {}  # dict mapping clients to their last active timestamp

    def do_grabbing(self, grab_dev):
        """Grab / Ungrab device depending on value of `grabbing`.
        Also set status in `grab_status` since there's not an easy way to check a devices grab status.
        """
        if (dev_path := grab_dev.path) not in self.grab_status:
            self.grab_status[dev_path] = False

        if self.grabbing and self.grab_status[dev_path] is False:
            grab_dev.grab()
            self.grab_status[dev_path] = True
        elif not self.grabbing and self.grab_status[dev_path] is True:
            grab_dev.ungrab()
            self.grab_status[dev_path] = False

    def get_next_client(self):
        """Set socket_index to next value to cycle through outputs."""
        if self.client_index >= len(self.clients) - 1:
            self.client_index = -1
            self.grabbing = False
        else:
            self.client_index = self.client_index + 1
            self.grabbing = True

    def handle_events(self, device):
        """Start loop to listen for device's events."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_port = self.settings.server_port + 1  # just use the next higher port

        while self.running:
            read_ready, _, _ = select.select([device.fd], [], [], 0.1)  # 0.1 second timeout
            if not read_ready:
                continue

            for event in device.read():
                if not self.running:
                    break
                self.do_grabbing(device)  # TODO: can't this go in get_next_client?
                if event.code == evdev.ecodes.KEY_RIGHTCTRL:
                    if self.toggle_key_down:
                        self.get_next_client()
                    self.toggle_key_down = not self.toggle_key_down
                else:
                    data = [event.type, event.code, event.value]

                    with client_lock:  # Protect clients list access
                        if self.clients and self.client_index >= 0:
                            client = self.clients[self.client_index]
                            try:
                                sock.sendto(bytes(f"{json.dumps(data)}\n", "utf-8"), (client, data_port))
                            except OSError as e:
                                warning_notify(f'Error sending to {client}: {e!s}')
                                self.clients.remove(client)
                                self.get_next_client()

        device.close()

    def listen_for_clients(self, address, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.bind((address, port))
        print(f"Server listening for clients on port {port}")

        while True:
            # Check for inactive clients
            now = time()
            with client_lock:
                for client in self.clients:
                    if client not in self.activity:
                        print("Warning: have client with no activity timestamp!")
                        continue  # shouldn't ever happen

                    if now - self.activity[client] > 4:
                        print(f'Dropping inactive client: {client}')
                        get_next = self.client_index == self.clients.index(client)
                        self.clients.remove(client)
                        if get_next:
                            self.get_next_client()

            # Receive any pending data
            try:
                data, addr_port = sock.recvfrom(1024)
            except socket.timeout:
                continue

            addr = addr_port[0]
            if data == b'ping':  # update active timestamp for this client
                self.activity[addr] = time()
            if data == b"get devices":
                dev_caps = get_capabilities(self.devices)
                data = bytes(f"{json.dumps(dev_caps)}\n", "utf-8")
                sock.sendto(data, addr_port)
                print(f"Sent device list to: {addr}")
            elif data == b'initialized':
                with client_lock:
                    if addr not in self.clients:  # prevent duplicate entries
                        self.clients.append(addr)
                        self.activity[addr] = time()
                        print(f"Initialized new client: {addr}")

    def run(self):
        print('Starting NKMS Server ...')
        port = self.settings.server_port
        address = self.settings.server_address

        self.running = True

        print('Loading input devices ...')
        self.devices = get_km_devices()
        self.threads = []
        for device in self.devices:
            print(f'Loading input device: {device.path}')
            km_dev = evdev.InputDevice(device.path)
            thread = threading.Thread(target=self.handle_events, args=(km_dev,))
            self.threads.append(thread)

        print('Listening for client connections ...')
        tcp_thread = threading.Thread(target=self.listen_for_clients, args=(address, port,))
        self.threads.append(tcp_thread)

        for thread in self.threads:
            thread.daemon = True
            thread.start()

        info_notify('NKMS Server Started')

        while self.running:
            sleep(1)

    def stop(self):
        self.running = False
        info_notify('NKMS Server Stopped')


if __name__ == "__main__":
    nkms_server = NkmsServer()
    nkms_server.run()