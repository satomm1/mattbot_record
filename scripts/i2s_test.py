# this code is a minimal code base for capturing audio data from the I2S interface
# on the Nvidia Jetson Orin Nano using the I2S2 interface. 
#
# It may be necessary to call this command prior to running: 
# amixer -c APE cset name="ADMAIF2 Mux" I2S2
#
# To test, you can call this from the command line:
# arecord -D hw:APE,1 -r 16000 -c 2 -f S32_LE output.wav
#
# Other dependencies: pip install pyalsaaudio
#                     sudo apt-get install libasound2-dev
#                     sudo apt-get install alsa-utils


import alsaaudio
import numpy as np

# Select the device to use (replace 'hw:1,0' if another card/device is correct)
device = 'hw:2,0'  # Card 1, Device 0 (ADMAIF1 for I2S input)

# Configure audio capture parameters
channels = 2  # Stereo capture
sample_rate = 44100  # Sample rate (44.1 kHz)
format = alsaaudio.PCM_FORMAT_S32_LE  # 24-bit format for I2S data
period_size = 1024  # Number of frames to capture per period

# Open the I2S PCM device for capture
capture = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK,
		channels=channels, rate=sample_rate, format=format,
		periodsize=period_size, device=device)

print("Capturing audio data...")

# Infinite loop to read data continuously
num_times = 0
while True:
    # Read data from the I2S interface
    length, data = capture.read()
    
    if length > 0:
        # Convert the byte data into a numpy array for processing
        audio_data = np.frombuffer(data, dtype=np.int32)

        print(length)

        # print(audio_data)
        num_times +=1
        if num_times % 1000 == 0:
            
        
            # Example: print mean amplitude of the captured data
            print(f"Mean Amplitude: {np.mean(np.abs(audio_data))}")
