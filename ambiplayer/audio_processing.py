import threading
import numpy as np
import sounddevice as sd

import decoders

class AudioPlayer():
    def __init__(
            self, 
            clip, 
            fs, 
            device_index, 
            channels, 
            decoder, 
            current_frame=0
    ) -> None:

        self.current_frame = current_frame
        self.clip = clip
        self.fs = fs
        self.device_index = device_index
        self.decoder = decoder

        self.stream = sd.OutputStream(
            samplerate=self.fs, 
            device=device_index, 
            channels=channels,
            callback=self.update_output_buffer
        )

        self.event = threading.Event()

    def play(self): 
        self.stream.start()
    
    def pause(self): 
        self.stream.stop()

    def stop(self):
        self.stream.stop()
        self.current_frame = 0
    
    def update_output_buffer(self, outdata, frames, _, status):
        if status: print(status)

        # chunksize will equal length of frames unless nearing end of clip
        chunksize = min(len(self.clip) - self.current_frame, frames)

        this_chunk = self.clip[
            self.current_frame:self.current_frame + chunksize]
        outdata[:chunksize] = self.decoder.decode(this_chunk)
        
        if chunksize < frames:
            outdata[chunksize:] = 0
            raise sd.CallbackStop()
        self.current_frame += chunksize
