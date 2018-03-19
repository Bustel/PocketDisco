import threading
import pyaudio
import signal
import platform
import sys
import os
import time
import subprocess
import logging

import stream
from flask_app import run_flask, shutdown_app, audio_streams

if platform.system() == "Linux":
    import pulsectl

FORMAT = pyaudio.paInt16
RATE = 44100
CHANNELS = 2
SEGMENT_DURATION = 5
MAX_SEGMENTS = 5
PORT = 5000
NO_STREAMS = 1

flask_thread = threading.Thread(target=run_flask)
loaded_pulse_modules = []


def sighandler(signum, frame):
    log = logging.getLogger(__name__)
    log.info("SIGINT received! Shutting down.")
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
    log = logging.getLogger(__name__)
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
                log.warning('Sources and sinks do not match. Check for zombie modules')
                return

            for cmd_out, source in zip(output_lst, our_sources):
                try:
                    pulse.source_output_move(cmd_out, source.index)
                except pulsectl.PulseOperationFailed:
                    log.warning('Failed to move output %d to source %d' % (cmd_out, source.name))


def pulse_remove_sinks(modules):
    if platform.system() == "Linux":
        log = logging.getLogger(__name__)
        with pulsectl.Pulse('PocketDisco') as pulse:
            for index in modules:
                try:
                    pulse.module_unload(index)
                except pulsectl.PulseOperationFailed:
                    log.error('Failed to unload pulse modules')


def shutdown():
    global loaded_pulse_modules
    log = logging.getLogger(__name__)
    if flask_thread.is_alive():
        log.info('Stopping Web Server')
        shutdown_app()
        flask_thread.join()
    else:
        log.info('Web Server already down.')

    log.info("Stopping Audio Streams")
    for s in audio_streams:
        if s.is_alive():
            s.running = False
            s.join()
    stream.terminate_portaudio()
    log.info('Stopped.')

    pulse_remove_sinks(loaded_pulse_modules)


def main():
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)

    global loaded_pulse_modules
    signal.signal(signal.SIGINT, sighandler)

    if platform.system() == 'Windows':
        os.chdir(os.path.dirname(sys.argv[0]))

    if not os.path.isdir('segments'):
        try:
            log.error('segments folder not found (CWD: %s)', os.getcwd())
            os.makedirs('segments')
        except OSError as e:
            log.error(e)

    loaded_pulse_modules = pulse_setup_sinks()
    if platform.system() == "Linux":
        device_name = "pulse"
    else:
        device_name = "Stereomix (Realtek High Definit"

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

    input("Press any key to stop.\n")
    shutdown()


if __name__ == '__main__':
    main()
