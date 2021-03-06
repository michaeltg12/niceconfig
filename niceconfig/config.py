import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml


def rsetattr(base, path, value):
    '''Given a list of path nodes, recursively find and set the target attribute or key.'''
    path, *child_paths = path

    if child_paths:
        new_base = getattr(base, path, None) or base[path]
        return rsetattr(new_base, child_paths, value)

    if hasattr(base, path):
        return setattr(base, path, value)

    if path in base:
        base[path] = value


class ConfigDict(dict, yaml.YAMLObject):
    '''Dict that can take a list as a key, recurse down its nested structure to get/set the value.'''

    def __getitem__(self, keys):

        if isinstance(keys, Sequence) and not isinstance(keys, str):
            key, *child_keys = keys
            if child_keys:
                return self[child_keys]

        return super().__getitem__(keys)

    def __setitem__(self, keys, value):

        if isinstance(keys, str) or not isinstance(keys, Sequence):
            return super().__setitem__(keys, value)

        return rsetattr(self, keys, value)


class Config(object):
    def __init__(self, files, defaults, schema=None, env_prefix=''):
        # setting self.store this way is necessary to avoid triggering this
        # class' overridden __setattr__ which uses self.store causing infinite recursion
        self.__dict__['store'] = ConfigDict()
        self.__dict__['env_prefix'] = env_prefix
        self.store.update(defaults)

        if isinstance(files, (str, Path)):
            files = [files, ]

        # Go through the list backward so the first file listed will take
        # precedence, falling back to the second, third, fourth, etc.
        for config_file in reversed(files):
            source_path = Path(config_file)
            if source_path.is_file():
                logging.debug(f'Overriding with config from {config_file}')
                content = source_path.read_text()
                self.store.update(yaml.safe_load(content))

        for config, value in self.flatten(defaults):
            env_var = self.get_env_var_name(config)
            if env_var in os.environ:
                logging.debug(f'Overriding {config} from {env_var}')
                self.store[config] = os.environ[env_var]

    def flatten(self, mapping):
        '''Flatten a mapping to a list of ((parent1..parentN), value).'''
        for key, value in mapping.items():
            if isinstance(value, Mapping):
                for subkey, subvalue in self.flatten(value):
                    yield [key] + subkey, subvalue
            else:
                yield [key], value

    def get_env_var_name(self, path):
        '''Given a list, return a valid environment variable name.'''
        return f'{self.env_prefix.upper()}_' + '_'.join(part.upper() for part in path)

    def as_env_file(self):
        '''Write the current config to a sourcable bash script.'''
        script = ''
        for config, value in self.flatten(self.store):
            if isinstance(value, str):  # only strings can be set with env vars
                env_var = self.get_env_var_name(config)
                script += f'export {env_var}={value}\n'
        return script

    def as_yaml(self):
        return yaml.dump(self.store, canonical=True, default_flow_style=False)

    def __getattr__(self, attr):
        return self.store[attr]

    def __setattr__(self, key, value):
        self.store[key] = value

    def __str__(self):
        return f'{self.store}'
