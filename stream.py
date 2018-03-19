import pyaudio
import threading
import time
import os
import platform
import logging

if platform.system() == "Linux":
    import audiotools
else:
    import audiotools_stub_win as audiotools
    import wave

glPortAudio = pyaudio.PyAudio()
glPALock = threading.Lock()


class Ringbuffer:
    def __init__(self, size):
        self.size = size
        self.data = bytearray(size)
        self.pos_w = 0
        self.pos_r = 0

    def read(self):
        if not self.is_empty():
            val = self.data[self.pos_r]
            self.pos_r = (self.pos_r + 1) % self.size
            return val
        else:
            return None

    def write(self, val):
        if not self.is_full():
            self.data[self.pos_w] = val
            self.pos_w = (self.pos_w + 1) % self.size

    def _get_avail_space(self):
        if self.pos_w >= self.pos_r:
            return self.size - (self.pos_w - self.pos_r) - 1
        else:
            return self.pos_r - self.pos_w - 1

    def _get_used_space(self):
        if self.pos_w >= self.pos_r:
            return self.pos_w - self.pos_r
        else:
            return self.size - (self.pos_r - self.pos_w) - 1

    def write_chunk(self, data, chunk_size):
        free_space = self._get_avail_space()
        for i in range(0, min(chunk_size, free_space)):
            self.data[self.pos_w] = data[i]
            self.pos_w = (self.pos_w + 1) % self.size

        return min(chunk_size, free_space)

    def read_chunk(self, chunk_size):
        chunk = bytearray(chunk_size)
        n = min(self._get_used_space(), chunk_size)

        for i in range(0, n):
            chunk[i] = self.data[self.pos_r]
            self.pos_r = (self.pos_r + 1) % self.size

        return n, chunk

    def is_full(self):
        next_pos = (self.pos_w + 1) % self.size
        return next_pos == self.pos_r

    def is_empty(self):
        return self.pos_r == self.pos_w


class PCMBlob(audiotools.PCMReader):

    def __init__(self, rate, sample_width, channels, mask):
        self.rate = rate
        self.mask = mask
        self.width = sample_width
        self.data = bytearray()
        self.channels = channels

        bits = sample_width * 8
        super().__init__(sample_rate=rate, channels=channels, bits_per_sample=bits, channel_mask=mask)

    def fill(self, chunk):
        self.data.extend(chunk)

    def to_file(self, path):
        if platform.system() == "Linux":
            audiotools.FlacAudio.from_pcm(path, self)
        else:
            with wave.open(path, "wb") as w:
                w.setnchannels(self.channels)
                w.setsampwidth(self.width)
                w.setframerate(self.rate)

                w.writeframes(self.data)

    def close(self):
        pass

    def read(self, pcm_frames):
        bigEndian = False
        isSigned = True
        if len(self.data) == 0:
            return audiotools.pcm.FrameList(b"", self.channels, self.width * 8, bigEndian, isSigned)

        requested_len = pcm_frames * self.width * self.channels

        if requested_len >= len(self.data):
            frames = audiotools.pcm.FrameList(bytes(self.data),
                                              self.channels, self.width * 8, bigEndian, isSigned)
            del self.data[:]
            return frames
        else:
            frames = audiotools.pcm.FrameList(bytes(self.data[:requested_len]),
                                              self.channels, self.width * 8, bigEndian, isSigned)
            del self.data[:requested_len]
            return frames


def terminate_portaudio():
    global glPALock, glPortAudio

    with glPALock:
        glPortAudio.terminate()


class InputStream(threading.Thread):
    def __init__(self, channels, segment_duration, sampling_rate, sample_format, max_segments, prefix,
                 device_name=None):
        super().__init__()

        self.device_name = device_name
        self.channels = channels
        self.segment_duration = segment_duration
        self.sampling_rate = sampling_rate
        self.format = sample_format
        self.max_segments = max_segments
        self.prefix = prefix

        self.log = logging.getLogger(self.prefix)

        self.buffer = Ringbuffer(16 * channels * segment_duration * sampling_rate)
        self.running = False

        self.segments = []
        self.reference = None
        self.segment_lock = threading.Lock()

        self.dropped_samples = 0
        self.rec_bytes = 0

    def update_segments(self, path, duration, seg_no):

        segment = {
            'no': seg_no,
            'duration': duration,
            'url': '/' + path
        }

        with self.segment_lock:
            if len(self.segments) >= self.max_segments:

                if self.reference is not None:
                    old_segments = []
                    prev_dur = self.reference
                    for s in self.segments:
                        end_time = prev_dur + s['duration']
                        if end_time < time.time():
                            old_segments.append(s)
                            prev_dur += s['duration']
                        else:
                            break

                    for s in old_segments:
                        self.reference += s['duration']
                        self.remove_segment(s)

                else:
                    old_seg = self.segments[0]
                    self.remove_segment(old_seg)

            self.segments.append(segment)

    def remove_segment(self, s):
        self.log.debug('Removing segment %s', s['url'])

        self.segments.remove(s)
        try:
            os.remove(s['url'].lstrip('/'))
        except OSError as e:
            self.log.warning('Failed to remove segment: %s', e)

    def __callback(self, in_data,  # recorded data if input=True; else None
                   frame_count,  # number of frames
                   time_info,  # dictionary
                   status_flags):  # PaCallbackFlags

        n = self.buffer.write_chunk(in_data, len(in_data))
        self.dropped_samples += frame_count - (n / (self.channels * pyaudio.get_sample_size(self.format)))
        self.rec_bytes += n
        return None, pyaudio.paContinue

    def run(self):
        global glPALock, glPortAudio

        self.running = True

        ftype = 'flac' if platform.system() == "Linux" else 'wav'

        with glPALock:
            dev_index = None

            if self.device_name is not None or True:
                for i in range(0, glPortAudio.get_device_count()):
                    dev_info = glPortAudio.get_device_info_by_index(i)
                    if dev_info['name'] == self.device_name:
                        dev_index = i

                if dev_index is None:
                    self.log.warning("Could not find device \"%s\". Using default instead.", self.device_name)

            stream = glPortAudio.open(format=pyaudio.paInt16,
                                      channels=self.channels,
                                      input_device_index=dev_index,
                                      rate=self.sampling_rate,
                                      input=True,
                                      stream_callback=self.__callback,
                                      start=False)

        self.log.info('Start recording...')
        stream.start_stream()

        seg_no = 0
        while self.running:

            samples = 0
            blob = PCMBlob(self.sampling_rate, pyaudio.get_sample_size(self.format), self.channels, 0x1 | 0x2)

            while samples < self.sampling_rate * self.segment_duration and self.running:
                if not self.buffer.is_empty():
                    chunk_request_size = min(1024, (self.sampling_rate * self.segment_duration) - samples)
                    if chunk_request_size % (pyaudio.get_sample_size(self.format) * self.channels) != 0:
                        break
                    n, chunk = self.buffer.read_chunk(chunk_request_size)

                    # Make sure we get complete frames
                    # TODO Why does this case happen every time we switch files?
                    # TODO Probably scheduling? To account for lost time after file sysCall?
                    while n < chunk_request_size:
                        time.sleep(0.5)
                        if not self.buffer.is_empty():
                            x, extra = self.buffer.read_chunk(chunk_request_size - n)
                            chunk[n:n + x] = extra[:x]
                            n += x

                    blob.fill(chunk[:n])
                    samples += n // (self.channels * pyaudio.get_sample_size(self.format))

                else:
                    time.sleep(0.1)

            file_path = os.path.join('segments', '%s_%d.%s' % (self.prefix, seg_no, ftype))
            duration = len(blob.data) / (blob.rate * blob.width * blob.channels)

            # Write data to file. Then, update segment list.
            blob.to_file(file_path)
            self.log.debug('Written segment %d', seg_no)
            self.update_segments(file_path, duration, seg_no)

            seg_no += 1

        stream.stop_stream()
        stream.close()
        self.log.info('Stopped recording. Written %d segments.', seg_no)
        self.log.info('Cleaning up segments')

        for i in range(0, len(self.segments)):
            self.remove_segment(self.segments[0])
