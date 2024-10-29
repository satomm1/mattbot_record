import pyaudio
"""
This script lists all available audio devices and their supported channels using the PyAudio library.

The script performs the following steps:
1. Initializes the PyAudio instance.
2. Iterates through all available audio devices.
3. Prints the name, maximum input channels, and maximum output channels for each device.
4. Terminates the PyAudio instance.

Dependencies:
- pyaudio: This library is required to interact with audio devices.

Usage:
Run this script to get a list of all audio devices and their channel capabilities.

Example:
    $ python channels.py

Output:
    Device 0: Device Name
      Max input channels: X
      Max output channels: Y
    Device 1: Device Name
      Max input channels: X
      Max output channels: Y
    ...
"""

# Initialize PyAudio
p = pyaudio.PyAudio()

# List all available devices and their supported channels
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"Device {i}: {info['name']}")
    print(f"  Max input channels: {info['maxInputChannels']}")
    print(f"  Max output channels: {info['maxOutputChannels']}")

# Terminate PyAudio
p.terminate()