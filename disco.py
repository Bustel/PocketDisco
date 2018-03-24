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
import config
from flask_app import run_flask, shutdown_app, audio_streams

if platform.system() == "Linux":  # TODO Make this configuration specific.
    import pulsectl

CONFIG = config.PDConfig()
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
            for i in range(0, len(CONFIG.streams)):
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

    if CONFIG.use_pulseaudio:
        pulse_remove_sinks(loaded_pulse_modules)


def load_configuration():
    global CONFIG
    if os.path.isfile('config.yaml'):
        try:
            CONFIG = config.PDConfig.from_file('config.yaml')
        except ValueError as e:
            pass


def setup_logging():
    logging.basicConfig(level=CONFIG.log_level)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)


def main():
    global CONFIG
    global loaded_pulse_modules

    if platform.system() == 'Windows':
        os.chdir(os.path.dirname(sys.argv[0]))

    load_configuration()
    setup_logging()

    log = logging.getLogger(__name__)

    signal.signal(signal.SIGINT, sighandler)

    if not os.path.isdir('segments'):
        try:
            log.error('segments folder not found (CWD: %s)', os.getcwd())
            os.makedirs('segments')
        except OSError as e:
            log.error(e)

    if CONFIG.use_pulseaudio:
        loaded_pulse_modules = pulse_setup_sinks()

    for i in range(0, len(CONFIG.streams)):
        s_cfg = CONFIG.streams[i]

        if s_cfg.format == 'paInt16':
            pa_format = pyaudio.paInt16
        elif s_cfg.format == 'paInt24':
            pa_format = pyaudio.paInt24
        elif s_cfg.format == 'paInt32':
            pa_format = pyaudio.paInt32
        elif s_cfg.format == 'paFloat32':
            pa_format = pyaudio.paFloat32
        else:
            log.warning('Configuration file contains unknown format for stream. Using paInt16 instead.')
            pa_format = pyaudio.paInt16

        s = stream.InputStream(s_cfg.channels,
                               s_cfg.segment_duration,
                               s_cfg.rate, pa_format,
                               s_cfg.max_segments,
                               "stream%d" % i,
                               device_name=s_cfg.device,
                               name=s_cfg.name)
        audio_streams.append(s)
        s.start()

    # Sleep is necessary for streams to appear as clients.
    if CONFIG.use_pulseaudio:
        time.sleep(2)
        pulse_attach_streams()

    flask_thread.start()

    input("Press any key to stop.\n")
    shutdown()


if __name__ == '__main__':
    main()
