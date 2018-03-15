import threading
import pyaudio
import signal
import platform
import sys
import os
import time

import stream
from flask_app import run_flask, shutdown_app, audio_streams


if platform.system() == "Linux":
    import pulsectl


FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 4
MAX_SEGMENTS = 3
PORT = 5000
NO_STREAMS = 2

flask_thread = threading.Thread(target=run_flask)
loaded_pulse_modules = []


def sighandler(signum, frame):
    print("SIGINT received!")
    shutdown()
    sys.exit(1)


def pulse_setup_sinks():
    modules = []
    if platform.system() == "Linux":
        with pulsectl.Pulse('PocketDisco') as pulse:
            for i in range(0, NO_STREAMS):
                index = pulse.module_load("module-null-sink",
                                          "sink_name=PD_Stream%d \
                                           sink_properties=device.description=PocketDisco_Stream%d" % (i, i))
                modules.append(index)
    return modules


def pulse_remove_sinks(modules):
    if platform.system() == "Linux":
        with pulsectl.Pulse('PocketDisco') as pulse:
            for index in modules:
                pulse.module_unload(index)


def shutdown():
    global loaded_pulse_modules
    print('Stopping Web Server')
    shutdown_app()
    flask_thread.join()

    print("Stopping Audio Streams")
    for s in audio_streams:
        s.running = False
        s.join()
    stream.terminate_portaudio()
    print('Stopped.')

    pulse_remove_sinks(loaded_pulse_modules)


def main():
    global loaded_pulse_modules
    signal.signal(signal.SIGINT, sighandler)

    if not os.path.isdir('segments'):
        try:
            os.makedirs('segments')
        except OSError as e:
            print(e)

    loaded_pulse_modules = pulse_setup_sinks()
    if platform.system() == "Linux":
        device_name = "pulse"
    else:
        device_name = None

    for i in range(0, NO_STREAMS):
        s = stream.InputStream(CHANNELS,
                               SEGMENT_DURATION,
                               RATE, FORMAT,
                               MAX_SEGMENTS,
                               "stream%d" % i,
                               device_name=device_name)
        audio_streams.append(s)
        s.start()

    # TODO Find Workaround
    #time.sleep(2)
    # Find our streams and attach them to the sinks
    #if os.name == "posix":
    #    with pulsectl.Pulse('PocketDisco') as pulse:
    #        for c in pulse.client_list():
    #            print(pulse.client_info(c.index))

    flask_thread.start()

    input("Press any key to stop.")
    shutdown()




if __name__ == '__main__':
    main()
