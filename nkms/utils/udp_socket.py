import socket

class UdpSocket(socket.socket):
    """Wrapper on socket.socket for easily sending/receiving utf-8 encoded strings via udp."""

    def __init__(self, timeout: int | None = None):
        super().__init__(socket.AF_INET, socket.SOCK_DGRAM)
        if timeout is not None:
            self.settimeout(timeout)

    def send_string_to(self, string: str, to: tuple) -> None:
        self.sendto(bytes(string, 'utf-8'), to)

    def receive_string(self, buffer_size: int = 1024) -> str:
        return str(self.recv(buffer_size), "utf-8").strip()
