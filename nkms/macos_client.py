import signal
import sys


def _check_accessibility():
    from ApplicationServices import AXIsProcessTrusted
    if not AXIsProcessTrusted():
        print(
            "ERROR: Accessibility permission not granted.\n"
            "Open System Settings → Privacy & Security → Accessibility\n"
            "and add the Python interpreter running this script:\n"
            f"  {sys.executable}"
        )
        sys.exit(1)


def main():
    _check_accessibility()

    from nkms.core.client import NkmsClient
    client = NkmsClient()

    def _shutdown(signum, frame):
        print("\nShutting down...")
        client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    client.run()


if __name__ == '__main__':
    main()
