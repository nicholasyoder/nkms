#!/usr/bin/python3

import select
import socketserver
import json
import evdev
import evdev.ecodes as e
import threading
from time import sleep
from settings import NkmsSettings
from notify import info_notify, warning_notify, error_notify


SOCKETS = []
KM_DEVS = []


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global SOCKETS, KM_DEVS
        while True:
            if self.request not in SOCKETS:
                SOCKETS.append(self.request)
                info_notify(f'New connection from {self.request}')
                sleep(0.1)  # small delay to allow client to initialize

            new_caps = {}
            for dev in KM_DEVS:
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

            data = bytes(f"{json.dumps(new_caps)}\n", "utf-8")
            self.request.send(data)

            data = self.request.recv(1024)
            if not data:
                break


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def server_bind(self):
        self.allow_reuse_address = True
        super(ThreadedTCPServer, self).server_bind()


class NkmsServer:
    def __init__(self):
        self.settings = NkmsSettings()
        self.toggle_key_down = False
        self.grabbing = False
        self.grab_status = {}
        self.socket_index = -1
        self.running = False
        self.tcp_server = None
        self.threads = []

    def start_tcp_server(self, address, port):
        self.tcp_server = ThreadedTCPServer((address, port), ThreadedTCPRequestHandler)
        self.tcp_server.allow_reuse_address = True
        self.tcp_server.serve_forever()

    def get_km_devices(self):
        """
        Get devices that have capabilities that look like a keyboard or mouse
        """
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

    def do_grabbing(self, grab_dev):
        """
        Grab / Ungrab device depending on value of `grabbing`
        Also set status in `grab_status` since there's not an easy way
        to check a devices grab status
        """
        if self.grabbing and self.grab_status[grab_dev.path] is False:
            grab_dev.grab()
            self.grab_status[grab_dev.path] = True
        elif not self.grabbing and self.grab_status[grab_dev.path] is True:
            grab_dev.ungrab()
            self.grab_status[grab_dev.path] = False

    def get_next_socket(self):
        """
        Set socket_index to next value to cycle through outputs
        """
        global SOCKETS

        if self.socket_index == len(SOCKETS) - 1:
            self.socket_index = -1
            self.grabbing = False
        else:
            self.socket_index = self.socket_index + 1
            self.grabbing = True

    def handle_events(self, device):
        """
        Start loop to listen for device's events
        """
        global SOCKETS
        while self.running:
            r, w, x = select.select([device.fd], [], [], 0.1)  # 0.1 second timeout
            if r:
                for event in device.read():
                    if not self.running:
                        break
                    self.do_grabbing(device)
                    if event.code == e.KEY_RIGHTCTRL:
                        # Context menu key
                        if self.toggle_key_down:
                            self.get_next_socket()
                        self.toggle_key_down = not self.toggle_key_down
                    else:
                        data = [event.type, event.code, event.value]
                        if SOCKETS and self.socket_index >= 0:
                            sock = SOCKETS[self.socket_index]
                            try:
                                sock.send(bytes(f"{json.dumps(data)}\n", "utf-8"))
                            except (OSError, BrokenPipeError):
                                warning_notify(f'Dropped connection: {sock}')
                                SOCKETS.remove(sock)
                                self.socket_index = -1
                                self.grabbing = False
        device.close()

    def run(self):
        global KM_DEVS
        print('Starting NKMS Server ...')
        port = int(self.settings.server_port)
        address = self.settings.server_address

        self.running = True

        print('Loading input devices ...')
        KM_DEVS = self.get_km_devices()
        self.threads = []
        for device in KM_DEVS:
            km_dev = evdev.InputDevice(device.path)
            print(device.path)
            self.grab_status[device.path] = False
            thread = threading.Thread(target=self.handle_events, args=(km_dev,))
            thread.start()
            self.threads.append(thread)

        print('Starting TCP server ...')
        tcp_thread = threading.Thread(target=self.start_tcp_server, args=(address, port,))
        tcp_thread.start()
        self.threads.append(tcp_thread)

        info_notify('NKMS Server Started')

        while self.running:
            sleep(1)

    def stop(self):
        self.running = False
        self.tcp_server.shutdown()
        self.tcp_server.server_close()

        for thread in self.threads:
            thread.join()

        info_notify('NKMS Server Stopped')


if __name__ == "__main__":
    nkms_server = NkmsServer()
    nkms_server.run()