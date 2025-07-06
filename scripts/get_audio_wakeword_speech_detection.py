import rospy
from std_msgs.msg import UInt8, String, Bool
from geometry_msgs.msg import Pose2D, Twist

import openwakeword
from openwakeword.model import Model

import alsaaudio
from scipy.io.wavfile import write
import wave

from faster_whisper import WhisperModel

import numpy as np
import sys
import time
import json

import requests

import torch
torch.set_num_threads(1)
import collections

from silero_vad import (load_silero_vad,
                          read_audio,
                          get_speech_timestamps,
                          save_audio,
                          VADIterator,
                          collect_chunks)

WAKEWORD_TIME = 0.32
# WAKEWORD_MODEL = "alexa_v0.1.tflite"
# WAKEWORD_KEY = "alexa_v0.1.tflite"
# WAKEWORD_MODEL = "./hey_row_bot.tflite"
# WAKEWORD_KEY = "hey_row_bot"

EXTRA_GAIN = 2**6

LANDMARKS = {"kitchen": [50.7, 20.7, 3.15],
             "bathroom": [27.8, 30.7, 3.15],
             "office": [10.6, 3.9, 1.57]}

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

        self.wakeword_weights = rospy.get_param('~weights_file',  "./hey_row_bot.tflite")
        self.wakeword_key = rospy.get_param('~key_name', "hey_row_bot")

        # Download the mel spectrogram model if it doesn't exist
        openwakeword.utils.download_models(model_names=[])

        self.wakeword_model = Model(wakeword_models=[self.wakeword_weights], inference_framework="tflite")

        self.model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        self.audio_input_publisher = rospy.Publisher('/audio_input', String, queue_size=10)

        self.vad_model = load_silero_vad(onnx=True)

        self.vad_iterator = VADIterator(self.vad_model, sampling_rate=16000)
        self.triggered = False

        self.ring_buffer = collections.deque(maxlen=30)
        self.is_speech = False

        self.button_status = 0
        self.button_subscriber = rospy.Subscriber('/button_status', UInt8, self.button_callback, queue_size=1)

        # Subscribe to Robot Velocity Commands
        self.is_moving = False
        self.cmd_vel_subscriber = rospy.Subscriber('/cmd_vel', Twist, self.cmd_vel_callback, queue_size=1)

        self.goal_pub = rospy.Publisher('/voice_goal', Pose2D, queue_size=10)
        self.voice_processing_publisher = rospy.Publisher('/voice_processing', Bool, queue_size=10)  # Publisher to indicate voice processing state

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

    def cmd_vel_callback(self, msg):
        if msg.linear.x != 0 or msg.angular.z != 0:
            self.is_moving = True  
        else:
            self.is_moving = False      

    def record_audio(self):
        print("Recording...")
        self.frames = []
        self.is_recording = True
        self.record_start_time = time.time()
        self.triggered = False
        self.ring_buffer.clear()

    def run(self):

        total_time = 0
        time_per_period = self.period_size / self.sample_rate
        wakeword_frames = []
        speech_end_time = time.time()
        self.counts = 0
        while not rospy.is_shutdown():
            length, data = self.pcm.read()

            if self.is_moving:
                rospy.sleep(1)
                continue  # Skip processing if the robot is moving

            if length:  
                reshaped_data = np.frombuffer(data, dtype='<i4').reshape(-1, self.channels, order='C')

                speech_data = np.mean(reshaped_data * 2**8 * EXTRA_GAIN , axis=1).astype(np.int32)
                speech_data = speech_data[::2] / (2**31)  # Downsample to 16000 Hz and rescale to -1 to 1

                if len(speech_data) == 512:
                    speech_dict = self.vad_iterator(speech_data, 16000)
                    if speech_dict and 'start' in speech_dict:
                        # print("Speech detected")
                        self.is_speech = True
                    elif speech_dict and 'end' in speech_dict:
                        # print("Speech ended")
                        self.is_speech = False
                        speech_end_time = time.time()
                        self.vad_iterator.reset_states()

                if self.idle:  # Detecting wakeword
                    # Data is really 24 bit scaled, so rescale to be 16 bit
                    reshaped_data = reshaped_data // 2**8 * EXTRA_GAIN 

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

                        elif (prediction[self.wakeword_key] > 0.5):
                            print("Wakeword detected!")
                            data = {'query': "wakeword", 'query_type': 'message_to_user'}
                            try:
                                response = requests.post(self.url, json=data)
                                response.raise_for_status()
                            except requests.exceptions.RequestException as e:
                                # print(f"Failed to send wakeword notification: {e}")
                                pass

                            self.idle = False
                            self.counts = 0

                            self.voice_processing_publisher.publish(True)  # Indicate that voice processing is happening
                        total_time = 0
                        wakeword_frames = []
                    
                else:  # Recording audio
                    # data is really scaled to be 24 bit, rescale to be 32 bit
                    reshaped_data = reshaped_data * 2**8 * EXTRA_GAIN
                    self.frames.append(reshaped_data)
                    total_time += time_per_period

                    self.counts += 1

                    time_since_speech = time.time() - speech_end_time
                    if (not self.triggered) and time_since_speech > 2.5 and not self.is_speech:  # No speech 
                        self.idle = True
                        total_time = 0
                        self.frames = []
                        print("No speech detected.")
                        data = {'query': "no_speech", 'query_type': 'message_to_user'}

                        try: 
                            response = requests.post(self.url, json=data)
                            response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            pass

                        self.triggered = False
                        self.first_wakeword_after_recording = True
                        self.ring_buffer.clear()

                        self.voice_processing_publisher.publish(False)  # Indicate that voice processing is not happening
                    elif not self.triggered and self.counts > 5 and self.is_speech:
                        self.triggered = True
                        self.counts = 0
                    elif self.triggered and not self.is_speech and time_since_speech > 1:
                        self.idle = True
                        total_time = 0
                        audio_data = np.concatenate(self.frames)
                        write("output.wav", self.sample_rate, audio_data)
                        self.frames = []

                        data = {'query': "processing", 'query_type': 'message_to_user'}
                        try:
                            response = requests.post(self.url, json=data)
                            response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            pass

                        print("Transcribing...")
                        self.is_transcribing = True
                        segments, info = self.model.transcribe("output.wav")
                        self.is_transcribing = False
                        result = ""
                        for segment in segments:
                            result += segment.text
                        # print(result["text"])
                        print(result)
                        # self.audio_input_publisher.publish(result["text"])
                        self.audio_input_publisher.publish(result)

                        data = {'query': result, 'query_type': 'conversation'}

                        try:
                            response = requests.post(self.url, json=data)
                            response.raise_for_status()
                            result = response.json()

                            response = result['response']
                            if isinstance(response, list):
                                print("Response: " + response[0])
                            elif isinstance(response, str):
                                result = json.loads(response)
                                if isinstance(result, list):
                                    result = result[0]
                                    if isinstance(result, dict):
                                        if 'success' in result and result['success']:
                                            x = result['x']
                                            y = result['y']
                                            if 'theta' in result:
                                                theta = result['theta']
                                            else:
                                                theta = 0
                                            print(f"New Goal: x={x}, y={y}, theta={theta}")

                                            goal_msg = Pose2D()
                                            goal_msg.x = x
                                            goal_msg.y = y
                                            goal_msg.theta = theta
                                            self.goal_pub.publish(goal_msg)
                                        elif 'goal' in result and result['goal'] != "None":
                                            if result['goal'] in LANDMARKS:
                                                goal_msg = Pose2D()
                                                goal_msg.x = LANDMARKS[result['goal']][0]
                                                goal_msg.y = LANDMARKS[result['goal']][1]
                                                goal_msg.theta = LANDMARKS[result['goal']][2]
                                                print(f"New Goal: {result['goal']} (x={goal_msg.x}, y={goal_msg.y}, theta={goal_msg.theta})")
                                                self.goal_pub.publish(goal_msg)

                        except requests.exceptions.RequestException as e:
                            print("Gemini Server not running.")
                        except json.JSONDecodeError as e:
                            print("Error decoding JSON response from Gemini Server.")

                        self.first_wakeword_after_recording = True
                        self.triggered = False

                        self.voice_processing_publisher.publish(False)  # Indicate that voice processing is not happening
                    elif total_time >= 10:
                        self.idle = True
                        total_time = 0
                        audio_data = np.concatenate(self.frames)
                        write("output.wav", self.sample_rate, audio_data)
                        self.frames = []

                        data = {'query': "processing", 'query_type': 'message_to_user'}
                        try:
                            response = requests.post(self.url, json=data)
                            response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            pass

                        print("Transcribing...")
                        self.is_transcribing = True
                        segments, info = self.model.transcribe("output.wav")
                        self.is_transcribing = False
                        result = ""
                        for segment in segments:
                            result += segment["text"]
                        # print(result["text"])
                        print(result)
                        # self.audio_input_publisher.publish(result["text"])
                        self.audio_input_publisher.publish(result)

                        data = {'query': result["text"], 'query_type': 'conversation'}
                        
                        try:
                            response = requests.post(self.url, json=data)
                            response.raise_for_status()
                            result = response.json()
                            print("Response: " + result['response']['response'])

                            result = json.loads(result['response'])
                            if isinstance(result, list):
                                result = result[0]
                                if isinstance(result, dict):
                                    if 'success' in result and result['success']:
                                        x = result['x']
                                        y = result['y']
                                        if 'theta' in result:
                                            theta = result['theta']
                                        else:
                                            theta = 0
                                        print(f"New Goal: x={x}, y={y}, theta={theta}")

                                        goal_msg = Pose2D()
                                        goal_msg.x = x
                                        goal_msg.y = y
                                        goal_msg.theta = theta
                                        self.goal_pub.publish(goal_msg)
                                    elif 'goal' in result and result['goal'] != "None":
                                            if result['goal'] in LANDMARKS:
                                                goal_msg = Pose2D()
                                                goal_msg.x = LANDMARKS[result['goal']][0]
                                                goal_msg.y = LANDMARKS[result['goal']][1]
                                                goal_msg.theta = LANDMARKS[result['goal']][2]
                                                print(f"New Goal: {result['goal']} (x={goal_msg.x}, y={goal_msg.y}, theta={goal_msg.theta})")
                                                self.goal_pub.publish(goal_msg)

                        except requests.exceptions.RequestException as e:
                            print("Gemini Server not running.")

                        self.first_wakeword_after_recording = True
                        self.triggered = False

                        self.voice_processing_publisher.publish(False)  # Indicate that voice processing is not happening
                        
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