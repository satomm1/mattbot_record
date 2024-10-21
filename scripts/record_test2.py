import alsaaudio
import numpy as np
from scipy.io.wavfile import write
import time

# Function to record audio using ALSA
def record_audio(duration=5, sample_rate=44100, channels=1, data_format=alsaaudio.PCM_FORMAT_S32_LE, period_size=1024, device='default'):
    # Set up the ALSA PCM object for capturing audio
    # pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, rate=sample_rate, format=data_format, channels=channels, periodsize=256)
    pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, channels=channels, rate=sample_rate, format=data_format, periodsize=period_size, device=device)
    
    # Create an empty list to store the recorded data
    audio_data = []
    
    # Calculate the number of loops needed to record for the desired duration
    num_loops = int(duration * sample_rate / period_size)
    
    print("Recording...")
    
    time_array = []
    for _ in range(num_loops):
        # Read data from the PCM input buffer
        t1 = time.time()
        length, data = pcm.read()
        if length:
            # Convert the byte data to a NumPy array of int16 values
            audio_data.append(np.frombuffer(data, dtype=np.int32).reshape(-1, channels))
            # print(audio_data[-1].shape)
            
        t2 = time.time()

        time_array.append(t2-t1)
    
    print("Average time per loop: ", np.mean(time_array))
    print("Recording complete.")
    
    # Concatenate all the recorded chunks into a single NumPy array
    audio_samples = np.concatenate(audio_data)
    print("Audio samples shape: ", audio_samples.shape)
    
    return audio_samples

# Record 5 seconds of audio
duration = 5  # seconds
sample_rate = 44100  # Sample rate (CD quality)
channels = 2  # Stereo

audio_samples = record_audio(duration, sample_rate, channels)

# Save the audio to a WAV file
output_filename = 'recorded_audio.wav'

# Use scipy to write the .wav file
write(output_filename, sample_rate, audio_samples)

print(f"WAV file saved as '{output_filename}'")
