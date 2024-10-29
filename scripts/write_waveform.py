from scipy.io.wavfile import write
import numpy as np

"""
This script generates a sine waveform and writes it to a WAV file.

Modules:
    scipy.io.wavfile.write: Function to write a numpy array as a WAV file.
    numpy: Library for numerical operations.

Constants:
    samplerate (int): The sample rate of the waveform in Hz.
    fs (int): The frequency of the sine wave in Hz.
    amplitude (int): The maximum amplitude of the sine wave, set to the maximum value of a 32-bit integer.

Variables:
    t (numpy.ndarray): Array of time values from 0 to 2 seconds.
    data (numpy.ndarray): Array of amplitude values for the sine wave.

Functions:
    write: Writes the generated sine wave data to a file named "example.wav".

Execution:
    The script prints one cycle of the sine wave to the terminal and the number of samples in one cycle.
"""
samplerate = 16000; fs = 400
t = np.linspace(0., 2., samplerate*2)
amplitude = np.iinfo(np.int32).max
data = amplitude * np.sin(2. * np.pi * fs * t)
write("example.wav", samplerate, data.astype(np.int32))

# print one cycle of the wave to the terminal
one_cycle_counts = samplerate//fs
for i in range(one_cycle_counts):
    print(f"{data[i].astype(np.int32)},")

print("Number of samples in one cycle: ", one_cycle_counts)