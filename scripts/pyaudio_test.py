import pyaudio
import numpy as np
import time,wave,datetime,os,csv


def pyserial_start():
    audio = pyaudio.PyAudio() # create pyaudio instantiation
    ##############################
    ### create pyaudio stream  ###
    # -- streaming can be broken down as follows:
    # -- -- format             = bit depth of audio recording (16-bit is standard)
    # -- -- rate               = Sample Rate (44.1kHz, 48kHz, 96kHz)
    # -- -- channels           = channels to read (1-2, typically)
    # -- -- input_device_index = index of sound device
    # -- -- input              = True (let pyaudio know you want input)
    # -- -- frmaes_per_buffer  = chunk to grab and keep in buffer before reading
    ##############################
    stream = audio.open(format = pyaudio_format,rate = 48000,channels = chans, \
                        input_device_index = dev_index,input = True, \
                        frames_per_buffer=CHUNK)
    stream.stop_stream() # stop stream to prevent overload
    return stream,audio

def pyserial_end():
    stream.close() # close the stream
    audio.terminate() # close the pyaudio connection
#
##############################################
# function for grabbing data from buffer
##############################################
#
def data_grabber(rec_len):
    stream.start_stream() # start data stream
    stream.read(CHUNK,exception_on_overflow=False) # flush port first 
    t_0 = datetime.datetime.now() # get datetime of recording start
    print('Recording Started.')
    data,data_frames = [],[] # variables
    for frame in range(0,int((samp_rate*rec_len)/CHUNK)):
        # grab data frames from buffer
        stream_data = stream.read(CHUNK,exception_on_overflow=False)
        data_frames.append(stream_data) # append data
        data.append(np.frombuffer(stream_data,dtype=buffer_format))
    stream.stop_stream() # stop data stream
    print('Recording Stopped.')
    return data,data_frames,t_0
#

def data_saver(t_0):
    data_folder = './data/' # folder where data will be saved locally
    if os.path.isdir(data_folder)==False:
        os.mkdir(data_folder) # create folder if it doesn't exist
    filename = datetime.datetime.strftime(t_0,
                                          '%Y_%m_%d_%H_%M_%S_pyaudio') # filename based on recording time
    wf = wave.open(data_folder+filename+'.wav','wb') # open .wav file for saving
    wf.setnchannels(chans) # set channels in .wav file 
    wf.setsampwidth(audio.get_sample_size(pyaudio_format)) # set bit depth in .wav file
    wf.setframerate(samp_rate) # set sample rate in .wav file
    wf.writeframes(b''.join(data_frames)) # write frames in .wav file
    wf.close() # close .wav file
    return filename

##############################################
# Main Data Acquisition Procedure
##############################################
#   
if __name__=="__main__":
    #
    ###########################
    # acquisition parameters
    ###########################
    #
    CHUNK          = 48000  # frames to keep in buffer between reads
    samp_rate      = 48000 # sample rate [Hz]
    pyaudio_format = pyaudio.paInt32 # 24-bit device
    buffer_format  = np.int32 # 16-bit for buffer
    chans          = 2 # only read 1 channel
    dev_index      = 0 # index of sound device    
    #
    #############################
    # stream info and data saver
    #############################
    #
    stream,audio = pyserial_start() # start the pyaudio stream   
    record_length =  5 # seconds to record
    input('Press Enter to Record Noise (Keep Quiet!)')
    noise_chunks_all,_,_ = data_grabber(CHUNK/samp_rate) # grab the data
    input('Press Enter to Record Data (Turn Freq. Generator On)')
    data_chunks_all,data_frames,t_0 = data_grabber(record_length) # grab the data
    data_saver(t_0) # save the data as a .wav file
    pyserial_end() # close the stream/pyaudio connection
    #