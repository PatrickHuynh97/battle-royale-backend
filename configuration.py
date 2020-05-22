import collections
import json
import os


class Configuration(object):
    __instance = None
    values = None

    # Singleton
    def __new__(cls):
        # If not initiated, the following is done
        if Configuration.__instance is None:
            Configuration.__instance = object.__new__(cls)

            default_config_file = "config.json"

            script_dir = os.path.dirname(__file__)

            default_config_path = os.path.join(script_dir, default_config_file)

            # Load default config for circle settings
            with open(default_config_path, "r") as f:
                config = json.load(f)

            Configuration.__instance.values = config

        return Configuration.__instance

    def get_configuration(self):
        return self.__instance.values


def deep_update_dict(original, new):
    for key, value in new.items():
        if isinstance(value, collections.Mapping):
            if key not in original:
                original[key] = {}
            deep_update_dict(original.get(key, {}), value)
        else:
            original[key] = value