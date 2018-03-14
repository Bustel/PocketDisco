import pyaudio
import threading
import stream

from flask_app import run_flask, shutdown_app, audio_streams

FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 4
MAX_SEGMENTS = 3
PORT = 5000


def main():
    stream1 = stream.InputStream(CHANNELS, SEGMENT_DURATION, RATE, FORMAT, MAX_SEGMENTS, "stream1")
    stream1.start()
    audio_streams.append(stream1)

    t = threading.Thread(target=run_flask)
    t.start()

    input("Press any key to stop.")


    print('Stopping Web Server')
    shutdown_app()

    print("Stopping Audio Streams")
    stream1.running = False

    t.join()
    stream1.join()
    print('Stopped.')


if __name__ == '__main__':
    main()
