import threading
import sounddevice as sd

class AudioPlayer():
    def __init__(self, clip, fs, device_index, current_frame=0) -> None:

        self.current_frame = current_frame
        self.clip = clip
        self.fs = fs
        self.device_index = device_index

        self.stream = sd.OutputStream(
            samplerate=self.fs, 
            device=device_index, 
            channels=self.clip.shape[1],
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

        chunksize = min(len(self.clip) - self.current_frame, frames)
        outdata[:chunksize] = self.clip[
            self.current_frame:self.current_frame + chunksize]
        
        if chunksize < frames:
            outdata[chunksize:] = 0
            raise sd.CallbackStop()
        self.current_frame += chunksize