import threading
import pyaudio
import signal
import platform
import sys
import os
import time
import subprocess

import stream
from flask_app import run_flask, shutdown_app, audio_streams

if platform.system() == "Linux":
    import pulsectl

FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 4
MAX_SEGMENTS = 6
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


def pulse_attach_streams():
    # This is a workaround for the lack of all bindings in source_output_list()
    if platform.system() == "Linux":
        cmd_out = subprocess.getoutput('pacmd list-source-outputs')
        index = -1
        output_lst = []
        pid = os.getpid()

        for line in cmd_out.split('\n'):
            line = line.strip()
            if line.startswith('index: '):
                index = int(line.split('index: ')[1])
            elif line.startswith('application.process.id = "') and index != -1:
                client_pid = int(line.split('application.process.id = "')[1].strip('"'))
                if client_pid == pid:
                    output_lst.append(index)  #

        # Make source outputs more distinguishable for the user
        for i, output in enumerate(output_lst):
            media_name = 'PocketDiscoCaptureStream%d' % i
            cmd = 'pacmd update-source-output-proplist %d media.name="%s"' % (output, media_name)
            subprocess.getstatusoutput(cmd)

        with pulsectl.Pulse('PocketDisco') as pulse:
            our_sources = list(filter(lambda x: x.name.startswith('PD_Stream'),
                                      sorted(pulse.source_list(), key=lambda x: x.index)))

            if len(our_sources) != len(output_lst):
                print('Sources and sinks do not match. Check for zombie modules')
                return

            for cmd_out, source in zip(output_lst, our_sources):
                try:
                    pulse.source_output_move(cmd_out, source.index)
                except pulsectl.PulseOperationFailed:
                    print('Failed to move output %d to source %d' % (cmd_out, source.name))


def pulse_remove_sinks(modules):
    if platform.system() == "Linux":
        with pulsectl.Pulse('PocketDisco') as pulse:
            for index in modules:
                pulse.module_unload(index)


def shutdown():
    global loaded_pulse_modules

    if flask_thread.is_alive():
        print('Stopping Web Server')
        shutdown_app()
        flask_thread.join()
    else:
        print('Web Server already down.')

    print("Stopping Audio Streams")
    for s in audio_streams:
        if s.is_alive():
            s.running = False
            s.join()
    stream.terminate_portaudio()
    print('Stopped.')

    pulse_remove_sinks(loaded_pulse_modules)


def main():
    global loaded_pulse_modules
    signal.signal(signal.SIGINT, sighandler)

    if platform.system() == 'Windows':
        os.chdir(os.path.dirname(sys.argv[0]))

    if not os.path.isdir('segments'):
        try:
            print(os.getcwd())
            print('segments folder not found')
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

    # Sleep is necessary for streams to appear as clients.
    time.sleep(2)
    pulse_attach_streams()

    flask_thread.start()

    input("Press any key to stop.")
    shutdown()


if __name__ == '__main__':
    main()
