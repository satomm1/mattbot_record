import rospy
from std_msgs.msg import UInt8, String

import openwakeword
from openwakeword.model import Model

import alsaaudio
from scipy.io.wavfile import write
import wave
import whisper
import numpy as np
import sys
import time

import requests

WAKEWORD_TIME = 0.32
# WAKEWORD_MODEL = "alexa_v0.1.tflite"
# WAKEWORD_KEY = "alexa_v0.1.tflite"
WAKEWORD_MODEL = "./hey_row_bot.tflite"
WAKEWORD_KEY = "hey_row_bot"

class MicAudio:

    def __init__(self, sample_rate=32000, channels=2, data_format=alsaaudio.PCM_FORMAT_S32_LE, period_size=1024, device='hw:APE,1'):

        self.period_size = period_size
        self.channels = channels
        self.sample_rate = sample_rate

        self.url='http://127.0.0.1:5000/gemini'

        self.pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, channels=channels, rate=sample_rate, format=data_format, periodsize=period_size, device=device)
        
        # Create an empty list to store the recorded data
        self.frames = []

        self.idle = True
        self.is_recording = False
        self.is_transcribing = False
        self.first_wakeword_after_recording = False

        self.wakeword_model = Model(wakeword_models=[WAKEWORD_MODEL])

        self.model = whisper.load_model("base.en")
        self.audio_input_publisher = rospy.Publisher('/audio_input', String, queue_size=10)

        self.button_status = 0
        self.button_subscriber = rospy.Subscriber('/button_status', UInt8, self.button_callback, queue_size=1)

        print("Ready to record audio...")

    def button_callback(self, msg):
        # See if the LSB is 1 or 0
        new_button_status = msg.data & 0b00000001

        if new_button_status != self.button_status:
            self.button_status = new_button_status
            if new_button_status == 1 and not self.is_transcribing:
                self.record_audio()
            else:
                self.is_recording = False          

    def record_audio(self):
        print("Recording...")
        self.frames = []
        self.is_recording = True
        self.record_start_time = time.time()

    def run(self):

        total_time = 0
        time_per_period = self.period_size / self.sample_rate
        wakeword_frames = []
        while not rospy.is_shutdown():
            length, data = self.pcm.read()

            if length:  
                reshaped_data = np.frombuffer(data, dtype='<i4').reshape(-1, self.channels, order='C')

                
                if self.idle:  # Detecting wakeword
                    reshaped_data = reshaped_data // 2**4  # Rescale data to be 16 bit

                    # Convert to mono by averaging the channels
                    mono_data = np.mean(reshaped_data, axis=1).astype(np.int16)

                    # Downsample to 16000 Hz
                    mono_data = mono_data[::2]

                    wakeword_frames.append(mono_data)
                    total_time += time_per_period

                    if total_time >= WAKEWORD_TIME:
                        # Feed the frame into the wakeword model
                        prediction = self.wakeword_model.predict(np.concatenate(wakeword_frames))
                        if self.first_wakeword_after_recording:
                            # Ignore the first wakeword after recording (it's usually a false positive)
                            self.first_wakeword_after_recording = False

                        elif (prediction[WAKEWORD_KEY] > 0.5):
                            print("Wakeword detected!")
                            self.idle = False
                        total_time = 0
                        wakeword_frames = []
                    
                else:  # Recording audio
                    # data is really 24 bit, rescale to be 32 bit
                    reshaped_data = reshaped_data * 2**12

                    self.frames.append(reshaped_data)

                    total_time += time_per_period

                    if total_time >= 8:
                        self.idle = True
                        total_time = 0
                        audio_data = np.concatenate(self.frames)
                        write("output.wav", self.sample_rate, audio_data)
                        self.frames = []

                        print("Transcribing...")
                        self.is_transcribing = True
                        result = self.model.transcribe("output.wav")
                        self.is_transcribing = False
                        print(result["text"])
                        self.audio_input_publisher.publish(result["text"])

                        data = {'query': result["text"], 'query_type': 'conversation'}
                        response = requests.post(self.url, json=data)
                        result = response.json()
                        print("Response: " + result['response'])

                        self.first_wakeword_after_recording = True
                        
            rospy.sleep(1/(self.sample_rate+1000))


    def shutdown(self):
        self.p.terminate()
        print("Shutting down mic_audio_node...")

if __name__ == '__main__':
    rospy.init_node('mic_audio_node')
    mic_audio = MicAudio()
    try:
        mic_audio.run()
    except rospy.ROSInterruptException:
        mic_audio.shutdown()