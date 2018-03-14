import threading
import pyaudio
import os
import pulsectl
import time

import stream
from flask_app import run_flask, shutdown_app, audio_streams


FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 4
MAX_SEGMENTS = 3
PORT = 5000
NO_STREAMS = 2


def main():

    loaded_pulse_modules = []
    if os.name == "posix":
        device_name = "pulse"

        # Set up a sink for every stream
        with pulsectl.Pulse('PocketDisco') as pulse:
            for i in range(0, NO_STREAMS):
                index = pulse.module_load("module-null-sink",
                                          "sink_name=PD_Stream%d \
                                           sink_properties=device.description=PocketDisco_Stream%d" % (i, i))
                loaded_pulse_modules.append(index)
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



    t = threading.Thread(target=run_flask)
    t.start()

    input("Press any key to stop.")

    print('Stopping Web Server')
    shutdown_app()
    t.join()

    print("Stopping Audio Streams")
    for s in audio_streams:
        s.running = False
        s.join()
    stream.terminate_portaudio()
    print('Stopped.')

    if os.name == "posix":
        print("Removing audio sinks...")
        with pulsectl.Pulse('PocketDisco') as pulse:
            for index in loaded_pulse_modules:
                pulse.module_unload(index)


if __name__ == '__main__':
    main()
