import socket
import json
from evdev import UInput, ecodes

from nkms.core.settings import NkmsSettings
from nkms.utils.notify import error_notify, warning_notify, info_notify


class NkmsClient:
    def __init__(self):
        self.settings = NkmsSettings()
        self.default_capabilities = {
            ecodes.EV_KEY: [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
                31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58,
                59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87,
                88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 113, 114,
                115, 116, 117, 119, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138,
                140, 142, 150, 152, 158, 159, 161, 163, 164, 165, 166, 173, 176, 177, 178, 179, 180, 183, 184, 185, 186, 187,
                188, 189, 190, 191, 192, 193, 194, 240, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287],
            ecodes.EV_REL: [0, 1, 6, 8, 11, 12],
            ecodes.EV_MSC: [4],
            17: [0, 1, 2, 3, 4]
        }
        self.running = False
        self.ui = None
        self.server_addr_port: tuple = ()

    def init_server_connection(self) -> None:
        """Connect to the server and prepare for receiving events."""
        self.server_addr_port = (self.settings.client_server, self.settings.client_port)

        # Get device capabilities from server
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"get devices", self.server_addr_port)
        data = self.receive_data(sock=sock, buffer_size=50000)
        self.ui = UInput(
            events=self.parse_capabilities(data),
            name='NetKMSwitch Keyboard and Mouse',
        )

        # Tell the server we're ready for events
        sock.sendto(b"initialized", self.server_addr_port)
        sock.close()

    def run(self) -> None:
        info_notify('Starting NKMS client')

        # Setup socket to listen for events
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)  # self.running check interval when there are no new events
        data_port = self.settings.client_port + 1
        sock.bind(('', data_port))  # just use the next higher port
        print(f"Listening for events on port {data_port}")

        self.init_server_connection()

        self.running = True
        while self.running:
            # Send keep-alive ping
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send_sock.sendto(b'ping', self.server_addr_port)
            send_sock.close()

            # Try to receive events
            try:
                data = self.receive_data(sock=sock, buffer_size=1024)
                self.process_data(data)
            except socket.timeout:
                continue
            except Exception as e:
                error_notify("Main loop failed")
                print(e)
                self.running = False

        sock.close()
        self.cleanup()

    @staticmethod
    def receive_data(sock, buffer_size):
        return str(sock.recv(buffer_size), "utf-8").strip()

    def parse_capabilities(self, data):
        try:
            dev_caps = json.loads(data)
            return {int(k): dev_caps[k] for k in dev_caps.keys()}
        except json.decoder.JSONDecodeError:
            warning_notify('Unable to load device capabilities. Falling back to defaults.')
            return self.default_capabilities

    def process_data(self, data):
        for line in data.split("\n"):
            try:
                j_data = json.loads(line)
                self.ui.write(j_data[0], j_data[1], j_data[2])
                self.ui.syn()
            except json.decoder.JSONDecodeError:
                error_notify('JSON decode failed')
                self.running = False

    def stop(self):
        self.running = False

    def cleanup(self):
        if self.ui:
            self.ui.close()
        info_notify("NKMS client stopped")


if __name__ == '__main__':
    nkms_client = NkmsClient()
    nkms_client.run()





