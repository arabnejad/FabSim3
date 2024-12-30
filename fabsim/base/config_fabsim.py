import os
import sys
import platform
import getpass
from rich.console import Console
import ruamel.yaml
from pprint import pprint
import shutil
from fabsim.base.environment_manager import FABSIM_CONFIG_DIR

def get_platform():
    #TODO: move this to utils.py
    platforms = {
        "linux": "Linux",
        "linux1": "Linux",
        "linux2": "Linux",
        "linux3": "Linux",
        "darwin": "OSX",
        "win32": "Windows",
    }
    try:
        return platforms[sys.platform]
    except Exception:
        print("[{}] Unidentified system !!!".format(sys.platform))
        exit()


class AttributeDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            # to conform with __getattr__ spec
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]


class ConfigFabSim:
    def __init__(self):
        self.config_env = AttributeDict(
            {
                "OS_system": get_platform(),
                "OS_release": platform.release(),
                "fabsim_root": os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                "user_name": getpass.getuser(),
                "config_dir": FABSIM_CONFIG_DIR
            }
        )
        self.console = Console()

        self.yaml = ruamel.yaml.YAML()
        self.yaml.allow_duplicate_keys = None
        self.yaml.preserve_quotes = True  # to Prevent long lines getting wrapped in ruamel.yaml
        self.yaml.width = 4096  # or some other big enough value to prevent line-wrap


    def copy_templates_files(self):
        # copy the templates files
        templates_dir = os.path.join(self.config_env.config_dir, "templates")
        if not os.path.exists(templates_dir):
            shutil.copytree(
                os.path.join(self.config_env.fabsim_root, "deploy", "templates"),
                templates_dir
            )
        else:
            print(f"Templates directory already exists at: {templates_dir}")


    def copy_machines_yaml_file(self):
        machines_yaml_file = os.path.join(self.config_env.config_dir, "machines.yml")

        # check the machines.yml if it exits
        if os.path.isfile(machines_yaml_file):
            print(f"machines.yml file is already exists in {self.config_env.config_dir}")
            return

        shutil.copy(
            os.path.join(self.config_env.fabsim_root,"deploy","machines.yml"),
            machines_yaml_file
        )


    def generate_machines_user_yaml_file(self):
        machines_user_yaml_file = os.path.join(self.config_env.config_dir, "machines_user.yml")

        # check the machines_user.yml if it exits
        if os.path.isfile(machines_user_yaml_file):
            print(f"machines_user.yml file is already exists in {self.config_env.config_dir}")
            return

        # Load and invoke the default non-machine specific config JSON
        # dictionaries.
        machines_user_example_yaml = self.yaml.load(
            open(
                os.path.join(
                    self.config_env.fabsim_root,
                    "deploy",
                    "machines_user_example.yml",
                )
            )
        )
        # setup machines_user.yml
        S = ruamel.yaml.scalarstring.DoubleQuotedScalarString
        machines_user_example_yaml["default"]["username"] = self.config_env.user_name
        machines_user_example_yaml["localhost"]["username"] = self.config_env.user_name

        # save machines_user.yml
        with open(machines_user_yaml_file, "w") as output_yaml_file:
            self.yaml.dump(machines_user_example_yaml, output_yaml_file)

    def config_dir_exists(self):
        print(f"Checking if configuration directory exists at: {self.config_env.config_dir}")
        print(f"results = {self.config_env.config_dir.exists()}")
        return self.config_env.config_dir.exists()

    def create_config_dir(self):
        # Create the config directory if it doesn't exist
        if self.config_dir_exists() == False:
            print(f"Creating configuration directory at: {self.config_env.config_dir}")
            self.config_env.config_dir.mkdir(parents=True, exist_ok=True)
        else:
            print(f"Configuration directory already exists at: {self.config_env.config_dir}")

def main():
    config = ConfigFabSim()
    config.create_config_dir()
    config.generate_machines_user_yaml_file()
    config.copy_machines_yaml_file()
    config.copy_templates_files()


if __name__ == "__main__":
    main()
