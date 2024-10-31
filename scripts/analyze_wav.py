from scipy.io import wavfile
import numpy as np
import matplotlib.pyplot as plt

"""
This script analyzes a WAV file by performing a Fast Fourier Transform (FFT) and plotting the results.

Functions:
    None

Usage:
    Run the script to read a WAV file, perform FFT on the audio data, and save the plots of the FFT results and the audio data.

Dependencies:
    - scipy.io.wavfile
    - numpy
    - matplotlib.pyplot

Variables:
    samplerate (int): The sample rate of the audio file in Hz.
    data (numpy.ndarray): The audio data read from the WAV file.
    fft_result (numpy.ndarray): The result of the FFT performed on the audio data.
    f (numpy.ndarray): The frequency bins corresponding to the FFT result.

Outputs:
    - Prints the sample rate, data shape, and data type of the audio file.
    - Saves 'fft_result.png' containing the plot of the FFT results showing only positive frequencies.
    - Saves 'audio_data.png' containing the plot of the audio data.
"""

samplerate, data = wavfile.read('./output.wav')

print(f"Sample rate: {samplerate} Hz")
print("Data shape: ", data.shape)
print("Data type: ", data.dtype)
# print("data: ", data)

# Do fft for left channel
fft_result_left = np.fft.fft(data[:,0])

# Do fft for right channel
fft_result_right = np.fft.fft(data[:,1])

max_amplitude = np.max(np.abs(data))
print("max_amplitude: ", max_amplitude)

# Plot the fft results for both channels showing only positive frequencies in subplots
f = np.fft.fftfreq(len(fft_result_left), 1/samplerate)

plt.figure()

# Subplot for left channel
plt.subplot(2, 1, 1)
plt.title('FFT Results - Left Channel')
plt.plot(f[:len(f)//2], np.abs(fft_result_left)[:len(f)//2])
plt.xlabel('Frequency (Hz)')
plt.ylabel('Amplitude')
plt.grid()

# Subplot for right channel
plt.subplot(2, 1, 2)
plt.title('FFT Results - Right Channel')
plt.plot(f[:len(f)//2], np.abs(fft_result_right)[:len(f)//2])
plt.xlabel('Frequency (Hz)')
plt.ylabel('Amplitude')
plt.grid()

plt.tight_layout()
plt.savefig('fft_result.png')

# Plot the audio data for the left and right channels
plt.figure()

# Subplot for left channel
plt.subplot(2, 1, 1)
plt.title('Audio Data - Left Channel')
plt.plot(data[:,0][0:1000])
plt.xlabel('Sample')
plt.ylabel('Amplitude')
plt.grid()

# Subplot for right channel
plt.subplot(2, 1, 2)
plt.title('Audio Data - Right Channel')
plt.plot(data[:,1][0:1000])
plt.xlabel('Sample')
plt.ylabel('Amplitude')
plt.grid()

plt.tight_layout()
plt.savefig('audio_data.png')

