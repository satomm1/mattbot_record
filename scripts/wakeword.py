import openwakeword
from openwakeword.model import Model

import alsaaudio
import numpy as np
import sys
import time

# # One-time download of all pre-trained models (or only select models)
openwakeword.utils.download_models()

# Instantiate the model(s)
model = Model(
    wakeword_models=["alexa_v0.1.tflite"],  # can also leave this argument empty to load all of the included pre-trained models
)

# Function to record audio using ALSA and feed it into the wakeword model
def record_and_detect_wakeword(sample_rate=16000, channels=2, data_format=alsaaudio.PCM_FORMAT_S32_LE, period_size=1024, device='hw:APE,1', frame_duration=0.08):
    # Set up the ALSA PCM object for capturing audio
    pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, channels=channels, rate=sample_rate, format=data_format, periodsize=period_size, device=device)
    
    print("Listening for wakeword...")

    total_time = 0
    time_per_period = period_size / sample_rate
    frames = []
    while True:
        # Read data from the PCM input buffer
        length, data = pcm.read()

        if length:
            reshaped_data = np.frombuffer(data, dtype='<i4').reshape(-1, channels, order='C')

            # data is really 24 bit, rescale to be 32 bit
            reshaped_data = reshaped_data * 2**12

            # Rescale data to be 16 bit
            reshaped_data = reshaped_data // 2**16

            # Convert to mono by averaging the channels
            mono_data = np.mean(reshaped_data, axis=1).astype(np.int16)

            frames.append(mono_data)
            total_time += time_per_period
        
            if total_time >= frame_duration:
                # Feed the frame into the wakeword model
                prediction = model.predict(np.concatenate(frames))
                # print(prediction['alexa_v0.1.tflite'])
                if (prediction['alexa_v0.1.tflite'] > 0.05):
                    print("Wakeword detected!")

                total_time = 0
                frames = []

        time.sleep(0.01)

# Start listening for the wakeword
record_and_detect_wakeword(sample_rate=16000, channels=2)
