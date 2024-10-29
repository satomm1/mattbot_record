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

# Do fft 
fft_result = np.fft.fft(data[:,0])
print("fft_result: ", fft_result)

# Plot the fft results showing only positive frequencies
f = np.fft.fftfreq(len(fft_result), 1/samplerate)
plt.figure()
plt.plot(f[:len(f)//2], np.abs(fft_result)[:len(f)//2])
plt.savefig('fft_result.png')

# Plot the audio data
plt.figure()
plt.plot(data[:,0])
plt.xlim(0, 10000)
plt.savefig('audio_data.png')


