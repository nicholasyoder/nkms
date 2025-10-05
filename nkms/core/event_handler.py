from enum import IntEnum
from typing import Final

from evdev import InputEvent, UInput, ecodes
from json import dumps as json_dumps
from select import select
from threading import Lock

from nkms.core.settings import NkmsSettings
from nkms.utils.udp_socket import UdpSocket

SERVER_CLIENT_INDEX: Final = -1
CLIENT_ACTIVITY_TIMEOUT: Final = 5  # drop clients after 5 seconds with no pings.


class KeyEventType(IntEnum):
    KEY_UP = 0
    KEY_DOWN = 1
    KEY_REPEAT = 2


class EventHandler:

    def __init__(
            self,
            settings: NkmsSettings,
            device_capabilities: dict,
    ):
        self.settings = settings
        self.clients = []
        self.client_lock = Lock()
        self.data_port = self.settings.server_port + 1  # use the next higher port
        self.sock = UdpSocket(timeout=2)
        self.running = True
        self.client_index = SERVER_CLIENT_INDEX
        self.keys_activated = False
        self.key1_down = False
        self.key2_down = False
        self.prevented_key1_press = False
        self.uinput = UInput(
            events=device_capabilities,
            name='NetKMSwitch Keyboard and Mouse',
        )

    def add_client(self, client):
        """Add a client to the clients list."""
        with self.client_lock:
            if client not in self.clients:
                self.clients.append(client)

    def remove_client(self, client):
        """Remove a client from the clients list."""
        with self.client_lock:
            if client in self.clients:
                should_get_next = self.client_index == self.clients.index(client)
                self.clients.remove(client)
                if should_get_next:
                    self.get_next_client()

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
                self.key1_down and  # key1 is releasing
                (
                    self.settings.server_key2 == 0 or  # key2 is undefined or
                    (self.keys_activated and not self.key2_down)  # key2 was pressed and released
                )
            ):
                # without key2: key1 was pressed, and is now releasing
                # with key2: key1 was pressed, key2 was pressed, key2 was released, key1 is now releasing
                self.get_next_client()
                self.keys_activated = False
                got_next_client = True

            self.key1_down = not self.key1_down

        elif key_code == self.settings.server_key2:
            if self.key2_down and self.keys_activated and not self.key1_down:
                # key1 was pressed, key2 was pressed, key1 released, now key2 is releasing
                self.get_next_client()
                self.keys_activated = False
                got_next_client = True

            if self.key1_down:
                self.keys_activated = True

            self.key2_down = not self.key2_down

        return got_next_client

    def _send_event_to_client(self, event) -> None:
        """Send event to client."""
        if self.client_index == SERVER_CLIENT_INDEX:
            self.uinput.write_event(event)
            self.uinput.syn()
            return

        with self.client_lock:  # Protect clients list access
            if self.clients:
                client = self.clients[self.client_index]
                try:
                    self.sock.send_string_to(
                        string=f"{json_dumps([event.type, event.code, event.value])}\n",
                        to=(client, self.data_port),
                    )
                except OSError as e:
                    print(f'Error sending to {client}: {e!s}')
                    self.clients.remove(client)
                    self.get_next_client()

    def _make_key1_press_from_event(self, event: InputEvent) -> InputEvent:
        """Create a key1 press event to immediately precede the given event."""
        return InputEvent(
            sec=event.sec,
            usec=event.usec - 1,
            type=ecodes.EV_KEY,
            code=self.settings.server_key1,
            value=KeyEventType.KEY_DOWN,
        )

    def _process_event(self, event: InputEvent) -> bool:
        """Process a key event.
        Returns True if the event should be passed to the client, False if it should be ignored.
        """
        if (
            event.type != ecodes.EV_KEY or
            event.value not in (KeyEventType.KEY_UP, KeyEventType.KEY_DOWN)
        ):
            return True  # We only care about special processing on up/down key events.

        if event.code in (self.settings.server_key1, self.settings.server_key2):
            self.prevented_key1_press = False
            got_next_client = self._maybe_get_next_client(key_code=event.code)
            if (
                    event.value == KeyEventType.KEY_UP and
                    event.code == self.settings.server_key1 and
                    not got_next_client and
                    not self.key2_down
            ):  # key1 up without it being part of our key sequence
                # create a press event and then allow this release event to go through
                self._send_event_to_client(self._make_key1_press_from_event(event))
            elif (
                    event.code == self.settings.server_key2 and
                    not got_next_client and
                    not self.key1_down and
                    not self.keys_activated
            ):  # key2 up/down event without key2 being pressed first
                pass  # allow event
            else:  # otherwise prevent the key event from going through.
                if event.code == self.settings.server_key1 and event.value == 1:
                    self.prevented_key1_press = True

                return False
        elif self.prevented_key1_press:
            # we prevented the key1 press event, but now have an unrelated event.
            # send the key1 press that was prevented earlier, so that it can be part
            # of some other key sequence caught by another app.
            self._send_event_to_client(self._make_key1_press_from_event(event))
            self.prevented_key1_press = False

        return True

    def handle_events(self, device):
        """Start loop to listen for device's events."""
        device.grab()
        while self.running:
            read_ready, _, _ = select([device.fd], [], [], 0.1)  # 0.1 second timeout
            if not read_ready:
                continue

            for event in device.read():
                if not self.running:
                    break

                if self._process_event(event):
                    self._send_event_to_client(event)

        device.ungrab()
        device.close()
