import pyaudio
import audiotools
import signal
import time
import threading
import requests
import os

from flask import Flask, jsonify, request, abort, send_file, render_template

FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 5
MAX_SEGMENTS = 3
PORT = 5000

glRunning = False
glReference = None
glSegments = []
glSegmentLock = threading.Lock()

app = Flask(__name__)


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

        bits = sample_width*8
        super().__init__(sample_rate=rate, channels=channels, bits_per_sample=bits, channel_mask=mask)

    def fill(self, chunk):
        self.data.extend(chunk)

    def to_file(self, path):
        audiotools.WaveAudio.from_pcm(path, self)

    def close(self):
        pass

    def read(self, pcm_frames):
        bigEndian = False
        isSigned = True
        if len(self.data) == 0:
            return audiotools.pcm.FrameList(b"", self.channels, self.width*8, bigEndian, isSigned)

        requested_len = pcm_frames * self.width * self.channels

        if requested_len >= len(self.data):
            frames = audiotools.pcm.FrameList(bytes(self.data),
                                              self.channels, self.width*8, bigEndian, isSigned)
            del self.data[:]
            return frames
        else:
            frames = audiotools.pcm.FrameList(bytes(self.data[:requested_len]),
                                              self.channels, self.width*8, bigEndian, isSigned)
            del self.data[:requested_len]
            return frames


dropped_samples = 0
rec_bytes = 0
shared_buffer = Ringbuffer(16 * CHANNELS * SEGMENT_DURATION * RATE)


def sigint_handler(signal, frame):
    global glRunning
    glRunning = False


def callback(in_data,  # recorded data if input=True; else None
             frame_count,  # number of frames
             time_info,  # dictionary
             status_flags):  # PaCallbackFlags

    global dropped_samples, rec_bytes

    n = shared_buffer.write_chunk(in_data, len(in_data))
    dropped_samples += frame_count - (n / (CHANNELS * pyaudio.get_sample_size(FORMAT)))
    rec_bytes += n
    return None, pyaudio.paContinue


def update_segments(fname, duration, no):
    global glSegments, glSegmentLock, glReference

    segment = {
        'no': no,
        'duration': duration,
        'url': '/' + fname
    }

    with glSegmentLock:
        if len(glSegments) >= MAX_SEGMENTS:
            glSegments.pop(0)

        glSegments.append(segment)

        if glReference is None:
            glReference = time.time()
        else:
            dur = 0
            for seg in glSegments:
                dur += seg['duration']
            glReference = time.time() - dur + segment['duration']

    dur = 0
    for seg in glSegments:
        dur += seg['duration']

    start_time = glReference + dur - segment['duration']
    print('Start time: %f' % start_time)
    end_time = start_time + segment['duration']
    print('End time: %f' % end_time)


def run_flask():
    app.run('0.0.0.0', PORT, use_reloader=False)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/get_tracks')
def api_endpoint():
    with glSegmentLock:
        tracklist = {
            'reference': glReference,
            'segments': glSegments
        }
        return jsonify(tracklist)


@app.route('/segments/<path:segment>')
def serve_segments(segment):
    return send_file(os.path.join('segments', segment), cache_timeout=SEGMENT_DURATION)


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    if not glRunning:
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return 'Server shutting down...'
    else:
        abort(404)


# No cacheing at all for API endpoints.
@app.after_request
def add_header(response):
    # response.cache_control.no_store = True
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response


def main():
    global glRunning
    t = threading.Thread(target=run_flask)
    signal.signal(signal.SIGINT, sigint_handler)
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    stream_callback=callback,
                    start=False)

    print('Start recording...')

    glRunning = True
    stream.start_stream()
    seg_no = 0

    while glRunning:
        samples = 0
        blob = PCMBlob(RATE, pyaudio.get_sample_size(FORMAT), CHANNELS, 0x1 | 0x2)

        while samples < RATE * SEGMENT_DURATION and glRunning:
            if not shared_buffer.is_empty():
                chunk_request_size = min(1024, (RATE * SEGMENT_DURATION) - samples)
                if chunk_request_size % (pyaudio.get_sample_size(FORMAT) * CHANNELS) != 0:
                    break
                n, chunk = shared_buffer.read_chunk(chunk_request_size)

                # Make sure we get complete frames
                # TODO Why does this case happen every time we switch files?
                # TODO Probably scheduling? To account for lost time after file sysCall?
                while n < chunk_request_size:
                    time.sleep(0.5)
                    if not shared_buffer.is_empty():
                        x, extra = shared_buffer.read_chunk(chunk_request_size - n)
                        chunk[n:n+x] = extra[:x]
                        n += x

                blob.fill(chunk[:n])
                samples += n // (CHANNELS * pyaudio.get_sample_size(FORMAT))

            else:
                time.sleep(0.1)

        file_path = os.path.join('segments', 'segment_%d.wav' % (seg_no % MAX_SEGMENTS))
        duration = len(blob.data) / (blob.rate * blob.width * blob.channels)
        update_segments(file_path, duration, seg_no)
        blob.to_file(file_path)
        print('Written segment %d' % seg_no)

        if seg_no == MAX_SEGMENTS:
            t.start()

        seg_no += 1

    requests.post('http://localhost:%d/api/shutdown' % PORT)
    stream.stop_stream()
    stream.close()
    p.terminate()

    print('Stopped recording. Written %d segments.' % seg_no)

    print('Stopping Web Server')
    t.join()
    print('Stopped.')


if __name__ == '__main__':
    main()
