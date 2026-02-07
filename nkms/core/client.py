import socket
import json
import threading
import time

from evdev import UInput

from nkms.core.constants import FALLBACK_DEVICE_CAPABILITIES
from nkms.core.settings import NkmsSettings
from nkms.utils.udp_socket import UdpSocket


class NkmsClient:
    def __init__(self):
        self.settings = NkmsSettings()
        self.running = False
        self.ui: UInput | None = None
        self.server_addr_port: tuple = ()
        self.active = False
        self.event_thread: threading.Thread | None = None

    def listen_for_events(self):
        """Receive and process events from the server."""
        sock = UdpSocket(timeout=1)
        data_port = self.settings.client_port + 1
        sock.bind(('', data_port))  # just use the next higher port
        print(f"Listening for events on port {data_port}")

        while self.active:
            try:
                self.process_data(sock.receive_string())
            except socket.timeout:
                continue

        sock.close()

    def run(self) -> None:
        print('Starting NKMS client')
        self.server_addr_port = (self.settings.client_server, self.settings.client_port)
        sock = UdpSocket(timeout=4)
        self.running = True
        while self.running:
            if self.active:  # do keep-alive pings
                try:
                    sock.send_string_to(string='ping', to=self.server_addr_port)
                    if (data := sock.receive_string()) == 'pong':
                        time.sleep(1)  # server is alive, wait and ping again
                    else:
                        print(f'Unexpected reply from server ping: {data}')
                        self.stop_events_listener()
                except socket.timeout:
                    print('Keep-alive ping timed out.')
                    self.stop_events_listener()
                except OSError as e:
                    print(f'Connection error during keep-alive: {e}')
                    self.stop_events_listener()

            else: # do pings to check if server is online
                try:
                    sock.send_string_to(string='ping', to=self.server_addr_port)
                    if (data := sock.receive_string()) != 'pong':
                        print(f'Unexpected reply from server ping: {data}')
                        time.sleep(2)
                        continue
                except socket.timeout:
                    continue
                except OSError as e:
                    print(f'Connection error: {e}')
                    time.sleep(2)
                    continue

                # Got a response from server ping. start listening for events
                self.start_events_listener()


    def start_events_listener(self):
        """Start listen for events thread."""
        print("Starting events thread...")
        sock = UdpSocket(timeout=4)
        # Get device capabilities from server
        try:
            sock.send_string_to(string='get devices', to=self.server_addr_port)
            data = sock.receive_string(buffer_size=50000)
        except OSError as e:
            print(f'Failed to get capabilities from server: {e}')
            return

        # Setup UInput device with capabilities from server
        self.ui = UInput(
            events=self.parse_capabilities(data),
            name='NetKMSwitch Keyboard and Mouse',
        )
        # Start events thread
        self.active = True
        self.event_thread = threading.Thread(target=self.listen_for_events)
        self.event_thread.daemon = True
        self.event_thread.start()
        # Tell the server we're ready for events
        sock.send_string_to(string='initialized', to=self.server_addr_port)
        sock.close()
        print(f'Successfully connected to {self.server_addr_port}')

    def stop_events_listener(self):
        """Stop listen for events thread."""
        print("Stopping events thread...")
        self.active = False
        if self.event_thread is not None:
            self.event_thread.join() # wait for thread to check self.active and shutdown
        if self.ui:
            self.ui.close()
        print("Stopped events thread.")

    @staticmethod
    def parse_capabilities(data):
        try:
            dev_caps = json.loads(data)
            return {int(k): dev_caps[k] for k in dev_caps.keys()}
        except json.decoder.JSONDecodeError:
            print('Unable to load device capabilities. Falling back to defaults.')
            return FALLBACK_DEVICE_CAPABILITIES

    def process_data(self, data):
        for line in data.split("\n"):
            if not (stripped_line := line.strip()):  # Skip empty lines
                continue

            try:
                j_data = json.loads(stripped_line)
                self.ui.write(j_data[0], j_data[1], j_data[2])
                self.ui.syn()
            except (json.decoder.JSONDecodeError, IndexError) as e:
                print(f'Decode failed for data {stripped_line} due to: {e!s}')
                continue

    def stop(self):
        self.running = False
        self.stop_events_listener()


if __name__ == '__main__':
    nkms_client = NkmsClient()
    nkms_client.run()
