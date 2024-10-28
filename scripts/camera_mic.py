import pyaudio
import wave
import whisper
import sounddevice as sd
import numpy as np
import sys
import scipy.signal as signal
import matplotlib.pyplot as plt

def design_fir_filter(sample_rate, numtaps=101, cutoff=np.array([500,5000])):
    # Design a low-pass FIR filter
    nyquist_rate = sample_rate / 2.0
    cutoff_freq = cutoff / nyquist_rate
    
    # Use the window method to design the filter
    fir_coeff = signal.firwin(numtaps, cutoff=cutoff_freq, pass_zero="bandpass")
    return fir_coeff

def apply_fir_filter(data, fir_coeff):
    # Apply the FIR filter to the data
    filtered_data = signal.lfilter(fir_coeff, 1.0, data)
    return filtered_data

def plot_frequency_spectrum(audio_data, sample_rate):
    # Calculate the FFT
    N = len(audio_data)
    yf = np.fft.fft(audio_data)
    xf = np.fft.fftfreq(N, 1.0 / sample_rate)
    
    # Only take the positive half of the spectrum
    xf = xf[:N // 2]
    yf = yf[:N // 2]

    # Convert magnitude to dB scale
    magnitude = 20 * np.log10(np.abs(yf))
    
    # Plot the spectrum
    plt.figure(figsize=(10, 6))
    plt.plot(xf, magnitude)
    plt.title("Frequency Domain Spectrum")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude (dB)")
    plt.grid()
    plt.savefig('frequency_spectrum.png')

def record_audio(output_filename, device_index, record_seconds=5, sample_rate=16000, channels=2, fir_coeff=None):
    p = pyaudio.PyAudio()
    
    stream = p.open(format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=1024)
    
    frames = []

    plotted = False
    
    print("Recording...")
    for _ in range(0, int(sample_rate / 1024 * record_seconds)):
        data = stream.read(1024)

        if fir_coeff is not None:
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_data = apply_fir_filter(audio_data, fir_coeff)
            data = audio_data.astype(np.int16).tobytes()

        # if not plotted:
        #     audio_data = np.frombuffer(data, dtype=np.int16)
        #     plot_frequency_spectrum(audio_data, sample_rate=sample_rate)
        #     plotted = True

        frames.append(data)
    
    print("Recording finished.")
    
    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save the recorded data as a WAV file
    with wave.open(output_filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))

def list_audio_devices():
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"Device {i}: {info['name']} (input channels: {info['maxInputChannels']})")
    p.terminate()

def transcribe_audio_in_real_time(model, duration=5, sample_rate=16000):
    
    def callback(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        # Flatten the audio data and convert it to the format expected by Whisper
        audio_data = indata.flatten()
        audio_data = audio_data.astype(np.int16)
        audio_data = (audio_data / 32767.0).astype(np.float32)  # Normalize
        
        # Perform the transcription
        result = model.transcribe(audio_data, word_timestamps=True)
        print("Transcription:", result['text'])

    print(f"Recording and transcribing for {duration} seconds...")
    
    # Record audio in real-time and call the callback function
    with sd.InputStream(samplerate=sample_rate, channels=2, callback=callback, dtype='int16'):
        sd.sleep(duration * 1000)
    
    print("Recording and transcription complete.")

# list_audio_devices()

model = whisper.load_model("base.en")
# fir_coeff = design_fir_filter(16000, numtaps=101)

record_audio("output.wav", device_index=0, record_seconds=5)
result = model.transcribe("output.wav")
print(result["text"])

# model = whisper.load_model("base.en")
# transcribe_audio_in_real_time(model, duration=5, sample_rate=16000)

