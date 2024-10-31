import rospy
from std_msgs.msg import UInt8, String

import pyaudio
import wave
import whisper
import numpy as np
import sys
import time

class MicAudio:

    def __init__(self, sample_rate=16000, channels=2, device_index=None):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.frames = []

        self.is_recording = False
        self.is_transcribing = False

        self.model = whisper.load_model("base.en")
        self.audio_input_publisher = rospy.Publisher('/audio_input', String, queue_size=10)

        self.button_status = 0
        self.button_subscriber = rospy.Subscriber('/button_status', UInt8, self.button_callback, queue_size=1)

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
        
        self.stream = self.p.open(format=pyaudio.paInt16,
                        channels=self.channels,
                        rate=self.sample_rate,
                        input=True,
                        input_device_index=self.device_index,
                        frames_per_buffer=1024)
        
        print("Recording...")
        self.frames = []
        self.is_recording = True
        self.record_start_time = time.time()

    def run(self):
        while not rospy.is_shutdown():
            if self.is_recording and time.time() - self.record_start_time < 10:
                data = self.stream.read(1024)
                self.frames.append(data)
            else:
                self.is_recording = False     
                if self.frames:
                    print("Recording finished.")
                    
                    # Stop and close the stream
                    self.stream.stop_stream()
                    self.stream.close()

                    # Save the recorded data as a WAV file
                    with wave.open('output.wav', 'wb') as wf:
                        wf.setnchannels(self.channels)
                        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
                        wf.setframerate(self.sample_rate)
                        wf.writeframes(b''.join(self.frames))
                    
                    self.frames = None

                    print("Transcribing...")
                    self.is_transcribing = True
                    result = self.model.transcribe("output.wav")
                    self.is_transcribing = False
                    print(result["text"])
                    self.audio_input_publisher.publish(result["text"])

            rospy.sleep(1/17000)


    def shutdown(self):
        self.p.terminate()
        print("Shutting down mic_audio_node...")

if __name__ == '__main__':
    rospy.init_node('mic_audio_node')
    mic_audio = MicAudio(device_index=0)
    try:
        mic_audio.run()
    except rospy.ROSInterruptException:
        mic_audio.shutdown()