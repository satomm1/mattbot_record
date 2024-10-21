#!/usr/bin/env python3
# -*- mode: python; indent-tabs-mode: t; c-basic-offset: 4; tab-width: 4 -*-

## recordtest.py
##
## This is an example of a simple sound capture script.
##
## The script opens an ALSA pcm device for sound capture, sets
## various attributes of the capture, and reads in a loop,
## writing the data to standard out.
##
## To test it out do the following:
## python recordtest.py out.raw # talk to the microphone
## aplay -r 8000 -f S16_LE -c 1 out.raw

#!/usr/bin/env python

from __future__ import print_function

import sys
import time
import getopt
import alsaaudio
import wave
import numpy as np
from scipy.io import wavfile

def usage():
	print('usage: recordtest.py [-d <device>] <file>', file=sys.stderr)
	sys.exit(2)

if __name__ == '__main__':

	device = 'hw:APE,1'

	opts, args = getopt.getopt(sys.argv[1:], 'd:')
	for o, a in opts:
		if o == '-d':
			device = a

	if not args:
		usage()

	# f = open(args[0], 'wb')

	# Open the device in nonblocking capture mode in mono, with a sampling rate of 44100 Hz
	# and 16 bit little endian samples
	# The period size controls the internal number of frames per period.
	# The significance of this parameter is documented in the ALSA api.
	# For our purposes, it is suficcient to know that reads from the device
	# will return this many frames. Each frame being 2 bytes long.
	# This means that the reads below will return either 320 bytes of data
	# or 0 bytes of data. The latter is possible because we are in nonblocking
	# mode.
	inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK,
		channels=2, rate=48000, format=alsaaudio.PCM_FORMAT_S32_BE,
		periodsize=256, device=device)

	# with wave.open("sound1.wav", "w") as f:
	# 	f.setnchannels(2)
	# 	f.setsampwidth(3)
	# 	f.setframerate(44800)
	# 	f.setnframes(0)

	

	all_data = []
	loops = 10000

	print("Recording...")
	while loops > 0:
		loops -= 1
		# Read data from device
		l, data = inp.read()

		if l < 0:
			print("Capture buffer overrun! Continuing nonetheless ...")
		elif l:
			# Convert data to numpy and little endian
			data = np.frombuffer(data, dtype=np.int32)
			all_data.append(data)

			# f.writeframes(data)

			# f.write(data)

			time.sleep(.001)

	print("Done recording.")

	data = np.concatenate(all_data)
	print("Data shape: ", data.shape)

	# Save the data to a .wav file
	wavfile.write("sound1.wav", 44100, data)