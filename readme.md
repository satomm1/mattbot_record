# Streaming Stereo Audio from I2S PCM Microphones to Nvidia Jetson Orin Nano

This repo contains code for streaming stereo audio from I2S PCM microphones to a Nvidia Jetson Orin Nano developer kit. In my case, I use a InvenSense ICS-43434 MEMS microphone. To convert the 24 bit PCM data output from the microphone to a form readable by the Jetson audio drivers, I use a PIC32MK0128MCA048T-I/Y8X microcontroller to convert the data to 32 bit and the correct endianness. 

Custom PCBs were designed to facilitate the MEMS microphones, PIC32, and connection to the Jetson. These PCBs were designed with KICAD and the designs (and KICAD files) are located in the `./pcb` directory. To order your own PCBs, the necessary gerber files are located in a `./pcb/*/gerber` directory. A BOM for each of the pcbs is also located in the directory (with part numbers for ordering from DigiKey).

The firmware for the PIC32 is located in the `./firmware` directory. This code should be loaded onto the PIC32 and supports sampling rates up to 44,100 Hz.

To enable the I2S on the Jetson, enable the I2S functionality via:
```
sudo python3 /opt/nvidia/jetson-io/jetson-io.py
```
As a simple test to see if the audio is working, you can use these commands to save a recording to `output.wav`:
```
amixer -c APE cset name="ADMAIF2 Mux" I2S2
arecord -D hw:APE,1 -r 16000 -c 2 -f S32_LE output.wav
```
It may be necessary to run `python3 ./scripts/channels.py` to determine which audio device to use for the above example. If you find you need to change from `hw:APE,1` to something else, you will need to modify the other python files as well.

To use the I2S on the Nvidia Jetson with Python, you need to make sure you have installed the following packages:
```
pip install pyalsaaudio
sudo apt-get install libasound2-dev
sudo apt-get install alsa-utils
```
To test the python audio, run:
```
python3 ./scripts/record.py
```
which will save a short 5 second recording to `./scripts/output.wav`. To see the sound in frequency domain, you can run `./scripts/analyze_wav.py`.

We use a wakeword to determine when to start listening. The opensource [openWakeWord](https://github.com/dscripka/openWakeWord) is used to identify "Hey Robot," but the openWakeWord repo describes how to easily create your own wakeword. We also use the opensource [Silero voice activity detector](https://github.com/snakers4/silero-vad) to identify when speech has ended. Speech which is recorded is transcribed using [Whisper](https://github.com/openai/whisper). These features require the installation of additional dependencies:
```
pip install openwakeword
pip install silero-vad
pip install -U openai-whisper
```
Putting all this together, we create a function which:
1) Initializes the I2S interface on the Jetson.
2) Records audio using the I2S interface.
3) Detects the wakeword using openWakeWord.
4) Records speech until silence is detected using Silero VAD.
5) Saves the recorded audio to a file.
6) Transcribes the audio.
7) (optional) Sends the transcription to an LLM for a response.
Try it out using:
```
python3 ./scripts/get_audio_wakeword_speech_detection.py
```
This repo is set up as a ROS package compatible with ROS Noetic.

License: MIT