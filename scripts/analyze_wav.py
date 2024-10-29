from scipy.io import wavfile
import numpy as np
import matplotlib.pyplot as plt

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
# plt.plot(f[0:2000], fft_result[0:2000])
plt.savefig('fft_result.png')

# Plot the audio data
plt.figure()
plt.plot(data[:,0])
plt.xlim(0, 10000)
plt.savefig('audio_data.png')
# print(data[:,0][:500])


