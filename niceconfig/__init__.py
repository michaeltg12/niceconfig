import yaml

from .config import Config, ConfigDict

yaml.representer.SafeRepresenter.add_representer(
    ConfigDict,
    yaml.representer.SafeRepresenter.represent_dict
)
