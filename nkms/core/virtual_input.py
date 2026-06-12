import sys

if sys.platform == 'darwin':
    from nkms.core.virtual_input_macos import MacOSVirtualInput as VirtualInput
else:
    from nkms.core.virtual_input_linux import LinuxVirtualInput as VirtualInput

__all__ = ['VirtualInput']
