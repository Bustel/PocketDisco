import ruamel.yaml
import logging
import platform

yaml = ruamel.yaml.YAML(typ='rt')

DEFAULTS_GENERAL = {
    'port': 5000,
    'log_level': logging.INFO,
    'use_pulseaudio': True if platform.system() == 'linux' else False
}

DEFAULTS_STREAM = {
    'device': 'pulse' if platform.system() == 'linux' else None,
    'rate': 44100,
    'channels': 2,
    'max_segments': 5,
    'name': None,
    'segment_duration': 5,
    'format': 'paInt16'
}


class PDConfig:
    yaml_tag = 'PocketDiscoConfiguration'

    def __init__(self):
        for k in DEFAULTS_GENERAL.keys():
            self.__dict__[k] = DEFAULTS_GENERAL[k]
            self.streams = [PDStreamConfig()]

    @classmethod
    def from_file(cls, path):
        with open(path, 'r') as f:
            cfg = yaml.load(f)
            if type(cfg) != PDConfig:
                raise ValueError('Invalid Configuration!')

            for k in DEFAULTS_GENERAL.keys():
                if not hasattr(cfg, k):
                    cfg.__dict__[k] = DEFAULTS_GENERAL[k]

            if not hasattr(cfg, 'streams'):
                raise ValueError('Invalid Configuration!')

            if len(cfg.streams) == 0:
                raise ValueError('No streams were configured!')

            for s in cfg.streams:
                for k in DEFAULTS_STREAM.keys():
                    if not hasattr(s, k):
                        s.__dict__[k] = DEFAULTS_STREAM[k]

            return cfg


class PDStreamConfig:
    yaml_tag = 'stream'

    def __init__(self):
        for k in DEFAULTS_STREAM.keys():
            self.__dict__[k] = DEFAULTS_STREAM[k]


yaml.register_class(PDConfig)
yaml.register_class(PDStreamConfig)
