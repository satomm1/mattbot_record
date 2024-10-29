import alsaaudio
import numpy as np
from scipy.io.wavfile import write
import time
import matplotlib.pyplot as plt

# Function to record audio using ALSA
def record_audio(duration=5, sample_rate=44100, channels=2, data_format=alsaaudio.PCM_FORMAT_S32_LE, period_size=1024, device='hw:APE,1'):
    # Set up the ALSA PCM object for capturing audio
    pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, channels=channels, rate=sample_rate, format=data_format, periodsize=period_size, device=device)
    
    # Create an empty list to store the recorded data
    audio_data = []
    
    # Calculate the number of loops needed to record for the desired duration
    num_loops = int(duration * sample_rate / period_size)
    
    print("Recording...")
    
    total_data = 0
    time_array = []
    for _ in range(num_loops):
        # Read data from the PCM input buffer
        t1 = time.time()
        length, data = pcm.read()

        # print(data)

        if length:
            total_data += length

            reshaped_data = np.frombuffer(data, dtype='<i4').reshape(-1, channels, order='C')

            # data is really 24 bit, rescale to be 32 bit
            reshaped_data = reshaped_data * 2**8

            print(reshaped_data[0])

            # reshaped_data = np.frombuffer(data, dtype='>i4').reshape(-1, channels, order='C')
            # print(reshaped_data[0])

            print("Max Amplitude: ", np.max(np.abs(reshaped_data)))
            audio_data.append(reshaped_data)

        time.sleep(0.01)
            
        t2 = time.time()

        time_array.append(t2-t1)
    
    print("Average time per loop: ", np.mean(time_array))
    print("Recording complete.")
    print("Total data: ", total_data)

    # Concatenate all the recorded chunks into a single NumPy array
    audio_samples = np.concatenate(audio_data)
    print("Audio samples shape: ", audio_samples.shape)
    
    return audio_samples

# Record 5 seconds of audio
duration = 5  # seconds
sample_rate = 16000  # Sample rate (CD quality)
channels = 2  # Stereo

audio_samples = record_audio(duration, sample_rate, channels)

plt.plot(audio_samples[:,0][0:500])
plt.savefig('audio_data.png')

# Save the audio to a WAV file
output_filename = 'output.wav'

# Use scipy to write the .wav file
write(output_filename, sample_rate, audio_samples)

print(f"WAV file saved as '{output_filename}'")

