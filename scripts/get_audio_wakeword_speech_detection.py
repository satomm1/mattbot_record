import rospy
from std_msgs.msg import UInt8, String, Bool
from geometry_msgs.msg import Pose2D, Twist
import tf

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
import re
import subprocess
import os

import requests

from capture_utils import write_wav_session

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


def _robot_id_from_env():
    raw = os.environ.get("ROBOT_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _get_admaif_mux_source(admaif, card='APE'):
    result = subprocess.run(
        ['amixer', '-c', card, 'get', f'ADMAIF{admaif} Mux'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    match = re.search(r"Item0: '([^']+)'", result.stdout)
    return match.group(1) if match else None


def find_ape_capture_device(i2s_port='I2S2', card='APE', max_admaif=20):
    for admaif in range(1, max_admaif + 1):
        if _get_admaif_mux_source(admaif, card=card) == i2s_port:
            return f'hw:{card},{admaif - 1}'
    return None


def configure_admaif_mux(admaif, i2s_port='I2S2', card='APE'):
    subprocess.run(
        ['amixer', '-c', card, 'cset', f'name=ADMAIF{admaif} Mux', i2s_port],
        check=True,
    )


def resolve_capture_device(device=None, i2s_port='I2S2', card='APE', admaif_fallback=2):
    if device and device != 'auto':
        return device

    detected = find_ape_capture_device(i2s_port=i2s_port, card=card)
    if detected:
        print(f"Auto-detected ALSA device {detected} (ADMAIF mux -> {i2s_port})")
        return detected

    configure_admaif_mux(admaif_fallback, i2s_port=i2s_port, card=card)
    device = f'hw:{card},{admaif_fallback - 1}'
    print(f"Configured ADMAIF{admaif_fallback} -> {i2s_port}; using ALSA device {device}")
    return device


class MicAudio:

    def __init__(self, sample_rate=32000, channels=2, data_format=alsaaudio.PCM_FORMAT_S32_LE, period_size=1024, device='auto'):

        self.period_size = period_size
        self.channels = channels
        self.sample_rate = sample_rate

        self.url='http://127.0.0.1:5000/gemini'

        i2s_port = rospy.get_param('~i2s_port', 'I2S2')
        alsa_device = rospy.get_param('~alsa_device', device)
        device = resolve_capture_device(device=alsa_device, i2s_port=i2s_port)
        print(f"Opening ALSA capture device: {device}")

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

        self.rendezvous_pub = rospy.Publisher('/rendezvous', Bool, queue_size=10)

        # Persist utterances to capture spool for upload (same layout as image sessions).
        self.save_wakeword_audio = bool(rospy.get_param("~save_wakeword_audio", False))
        self.spool_dir = rospy.get_param("~spool_dir", "/workspace/catkin_ws/data/capture_spool")
        self.robot_id = _robot_id_from_env()
        if self.save_wakeword_audio and self.robot_id is None:
            rospy.logwarn("save_wakeword_audio enabled but ROBOT_ID unset; spool writes disabled")
            self.save_wakeword_audio = False

        if self.save_wakeword_audio:
            self._tf_listener = tf.TransformListener()

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

    def _lookup_pose(self):
        try:
            translation, rotation = self._tf_listener.lookupTransform(
                "map", "base_footprint", rospy.Time(0)
            )
            _roll, _pitch, theta = tf.transformations.euler_from_quaternion(rotation)
            return {
                "x": translation[0],
                "y": translation[1],
                "theta": theta,
                "frame": "map",
            }
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            return None

    def record_audio(self):
        print("Recording...")
        self.frames = []
        self.is_recording = True
        self.record_start_time = time.time()
        self.triggered = False
        self.ring_buffer.clear()

    def _handle_gemini_navigation(self, gemini_payload):
        """Parse Gemini JSON and publish voice_goal or rendezvous if present."""
        try:
            response = gemini_payload.get("response")
            if isinstance(response, list):
                print("Response: " + response[0])
                return
            if isinstance(response, str):
                parsed = json.loads(response)
            else:
                return
            if isinstance(parsed, list):
                parsed = parsed[0]
            if not isinstance(parsed, dict):
                return
            if parsed.get("success"):
                goal_msg = Pose2D()
                goal_msg.x = parsed["x"]
                goal_msg.y = parsed["y"]
                goal_msg.theta = parsed.get("theta", 0)
                print(f"New Goal: x={goal_msg.x}, y={goal_msg.y}, theta={goal_msg.theta}")
                self.goal_pub.publish(goal_msg)
            elif parsed.get("goal") and parsed["goal"] != "None":
                if parsed["goal"] in LANDMARKS:
                    goal_msg = Pose2D()
                    goal_msg.x = LANDMARKS[parsed["goal"]][0]
                    goal_msg.y = LANDMARKS[parsed["goal"]][1]
                    goal_msg.theta = LANDMARKS[parsed["goal"]][2]
                    print(
                        f"New Goal: {parsed['goal']} (x={goal_msg.x}, y={goal_msg.y}, theta={goal_msg.theta})"
                    )
                    self.goal_pub.publish(goal_msg)
                elif parsed["goal"] == "rendezvous":
                    print("Rendezvous command received.")
                    self.rendezvous_pub.publish(True)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"Error parsing Gemini navigation response: {exc}")

    def _save_utterance_to_spool(self, transcript: str):
        if not self.save_wakeword_audio:
            return
        try:
            with open("output.wav", "rb") as handle:
                wav_bytes = handle.read()
            pose = self._lookup_pose()
            session_id = write_wav_session(
                self.spool_dir,
                self.robot_id,
                "wakeword",
                wav_bytes,
                transcript=transcript,
                sample_rate=self.sample_rate,
                channels=self.channels,
                pose=pose,
            )
            print(f"Saved wakeword audio session={session_id}")
        except OSError as exc:
            print(f"Failed to save wakeword audio: {exc}")

    def _finalize_utterance(self, audio_data):
        """Write WAV, transcribe, optionally spool, POST transcript to Gemini."""
        write("output.wav", self.sample_rate, audio_data)
        self.frames = []

        data = {"query": "processing", "query_type": "message_to_user"}
        try:
            response = requests.post(self.url, json=data)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            pass

        print("Transcribing...")
        self.is_transcribing = True
        segments, _info = self.model.transcribe("output.wav")
        self.is_transcribing = False
        transcript = ""
        for segment in segments:
            transcript += segment.text
        print(transcript)
        self.audio_input_publisher.publish(transcript)

        self._save_utterance_to_spool(transcript)

        data = {"query": transcript, "query_type": "conversation"}
        try:
            response = requests.post(self.url, json=data)
            response.raise_for_status()
            self._handle_gemini_navigation(response.json())
        except requests.exceptions.RequestException:
            print("Gemini Server not running.")
        except json.JSONDecodeError:
            print("Error decoding JSON response from Gemini Server.")

        self.first_wakeword_after_recording = True
        self.triggered = False
        self.voice_processing_publisher.publish(False)

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
                            self.recording_start_time = time.time()

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
                    time_since_recording = time.time() - self.recording_start_time
                    if (not self.triggered) and time_since_recording > 2.5 and not self.is_speech:  # No speech 
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
                        self._finalize_utterance(audio_data)
                    elif total_time >= 10:
                        self.idle = True
                        total_time = 0
                        audio_data = np.concatenate(self.frames)
                        self._finalize_utterance(audio_data)
                        
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