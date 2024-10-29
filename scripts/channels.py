import pyaudio

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