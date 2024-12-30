import importlib
import inspect
import os
import sys
import time
from pprint import pformat, pprint

import yaml
from beartype import beartype
from beartype.typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel

from fabsim.base.decorators import task
from fabsim.base.environment_manager import env
from fabsim.base.utils import add_print_prefix
from fabsim.deploy.templates import template
from fabsim.base.config_fabsim import FABSIM_CONFIG_DIR
from fabsim.base.error_handler import FabSimError
from fabsim.base.config_fabsim import get_platform
class RemoteMachines:
    def __init__(self):
        self.config = None
        # Load default machines
        machine_config_file = os.path.join(FABSIM_CONFIG_DIR, "machines.yml")
        if os.path.isfile(machine_config_file):
            self.config = yaml.safe_load(open(machine_config_file, encoding="utf8"))
        else:
            raise FabSimError.FileNotFoundError(
                f"There is NO machines.yml under {FABSIM_CONFIG_DIR} directory!!!",
                details="Please check the directory and try again, or run config_fabsim to generate the required files"
            )
        # Include private machines
        config_file_private = os.path.join(FABSIM_CONFIG_DIR, "machines_private.yml")
        if os.path.isfile(config_file_private):
            self.config.update(yaml.safe_load(open(config_file_private, encoding="utf8")))


        # Load user machines
        self.user_config = None
        machine_config_file_users = os.path.join(FABSIM_CONFIG_DIR, "machines_user.yml")
        if os.path.isfile(machine_config_file_users):
            self.user_config = yaml.safe_load(open(machine_config_file_users, encoding="utf8"))
        else:
            raise FabSimError.FileNotFoundError(
                f"There is NO machines_user.yml under {FABSIM_CONFIG_DIR} directory!!!",
                details="Please check the directory and try again, or run config_fabsim to generate the required files"
            )

        # set plugin machines
        self.plugin_config = None

        # Update the default environment variables
        env.update(self.config["default"])
        env.update(self.user_config["default"])

    '''
    def load_plugin_machines_config(self, plugin_name: str):
        """
        Load the plugin machine specific configuration
        """

        if env.plugin_dir == None:
            #TODO: maybe we need to raise an error here?
            return


        machine_config_file_plugin = os.path.join(
            env.plugin_dir, f"machines_{env.plugin_name}_user.yml")

        if os.path.isfile(machine_config_file_plugin):
            self.plugin_config = yaml.safe_load(open(machine_config_file_plugin, encoding="utf8"))
            # Update the default environment variables
            env.update(self.plugin_config.get("default", {}))
    '''


    @beartype
    def add_plugin_environment_variable(self, plugin_name: str) -> None:
        """
        read the plugin machine specific configuration for the input plugin name.

        !!! info
            the plugin machine specific config file should follow the following
            name structure:
            ```sh
            machines_<plugin_name>_user.yml
            ```

        Args:
            plugin_name (str): the name of pluing

        """

        # TODO: this function should be removed

        # machines_<plugin>.yml
        # machines_<plugin>_user.yml
        plugin_path = os.path.join(env.localroot, "plugins", plugin_name)
        machine_name = env.host
        plugin_machines_user = os.path.join(
            plugin_path, "machines_{}_user.yml".format(plugin_name)
        )

        if not os.path.isfile(plugin_machines_user):
            print("\nNO machines_{}_user.yml FOUND\n".format(plugin_name))
            return

        plugin_config = yaml.load(
            open(plugin_machines_user), Loader=yaml.SafeLoader
        )

        if plugin_config is None:
            print("\nmachines_{}_user.yml is empty\n".format(plugin_name))
            return

        self.user_config.update(plugin_config)
        # only update environment variable based on plugin_machines_user yaml file
        old_env = my_deepcopy(env)

        if "default" in plugin_config and plugin_config["default"] is not None:
            env.update(plugin_config["default"])

        if (
            machine_name in plugin_config
            and plugin_config[machine_name] is not None
        ):
            env.update(plugin_config[machine_name])

        console = Console()

        env.modules = config["default"]["modules"]
        if "import" in config[machine_name]:
            if config[machine_name]["import"] in plugin_config:
                env.modules.update(
                    plugin_config[config[machine_name]["import"]].modules
                )

        if (
            machine_name in plugin_config
            and plugin_config[machine_name] is not None
        ):
            env.modules.update(plugin_config[machine_name].get("modules", {}))
        else:
            error_msg = "{} is not available in {}".format(
                machine_name, plugin_machines_user
            )
            error_msg += "\nor there is no item for that machine name"

            console.print(
                Panel(
                    "[red1]{}[/red1]".format(error_msg),
                    title="[yellow1]Error[/yellow1]",
                    expand=False,
                )
            )

        # TODO: do we need calling complete_environment() here at all ???
        env.complete_environment()
        msg = "\n".join(findDiff(env, old_env, path="env"))
        title = "New/Updated environment variables from {} plugin".format(
            plugin_name
        )
        console.print(
            Panel(
                "{}".format(msg),
                title="[yellow1]{}[/yellow1]".format(title),
                expand=False,
            )
        )


    def generate_module_commands(self, script=None):
        """
        Generates the required module commands for the remote machine scripts.
        It reads the `modules` env variables defined in machine yaml files.
        Example input entry:
        ```yaml
        modules:
            # list of modules to be loaded on remote machine
            loaded: ["python/3.7.3", "openmpi/4.0.0_gcc620"]
            # list of modules to be unloaded on remote machine
            unloaded: ["python"]

        ```
        and generates these lines in the job script
        ```sh
        # unload modules
        module unload python
        # load required modules
        module load python python/3.7.3 openmpi/4.0.0_gcc620
        ```
        """
        module_commands = [
            "module {}".format(module) for module in env.modules["all"]
        ]

        module_commands += [
            "module {}".format(module)
            for module in env.modules.get("nonexistent", "")
        ]

        module_commands += [
            "module unload {}".format(module)
            for module in env.modules.get("unloaded", "")
        ]
        module_commands += [
            "module load {}".format(module)
            for module in env.modules.get("loaded", "")
        ]
        if script is not None:
            module_commands += [
                "module {}".format(module)
                for module in env.modules.get(script, "")
            ]
        return module_commands


    @beartype
    def load_machine(self, machine_name: str) -> None:
        """
        Load the machine-specific configurations.
        Completes additional paths and interpolates them, via
        `complete_environment`.
        """
        env.machine_name = machine_name

        # env.update(self.config[machine_name])
        env.update(self.config.get(machine_name, {}))
        env.update(self.user_config.get(machine_name, {}))
        if self.plugin_config != None:
            env.update(self.plugin_config.get(machine_name, {}))
        # if machine_name in self.user_config:
        #     env.update(self.user_config[machine_name])


        # Construct modules environment: update, not replace when overrides are done.


        env.modules = self.config["default"]["modules"]
        env.modules.update(self.config.get(machine_name, {}).get("modules", {}))
        env.modules.update(self.user_config.get(machine_name, {}).get("modules", {}))
        if self.plugin_config != None:
            env.modules.update(self.plugin_config.get(machine_name, {}).get("modules", {}))


        # TODO: check if we need these lines or not, it will be called later in complete_environment
        module_commands = self.generate_module_commands()
        run_prefix_commands = env.run_prefix_commands[:]
        env.run_prefix = (
            " \n".join(module_commands + list(map(template, run_prefix_commands)))
            or "echo THE FIRST Running..."
        )

        env.complete_environment()

    '''
    def complete_environment(self) -> None:
        """
        Add paths to the environment based on information in the yaml configs
        files.

        Environment vars created can be used in job-script templates:

        - `results_path`: Path to store results
        - `remote_path` : Root of area for checkout and build on remote
        - `config_path` : Path to store config files
        - `scripts_path` : Path where job-queue-submission scripts generated by
            Fabric are sent.
        - `run_prefix` : Command string to invoke before any job is run.
        """
        env.host_string = "{}@{}".format(env.username, env.remote)
        env.home_path = template(env.home_path_template)
        env.runtime_path = template(env.runtime_path_template)
        env.work_path = template(env.work_path_template)
        env.remote_path = template(env.remote_path_template)
        env.stat = template(env.stat)
        env.results_path = os.path.join(env.work_path, "results")
        env.config_path = os.path.join(env.work_path, "config_files")
        env.scripts_path = os.path.join(env.work_path, "scripts")
        env.local_results = os.path.join(os.path.expanduser(
            template(env.plugin_dir)), "results")
        env.local_system_time = int(time.time())

        if hasattr(env, "flee_location"):
            env.flee_location = template(env.flee_location)

        for i in range(0, len(env.local_templates_path)):
            env.local_templates_path[i] = os.path.expanduser(
                template(env.local_templates_path[i])
            )

        for i in range(0, len(env.local_config_file_path)):
            env.local_config_file_path[i] = os.path.expanduser(
                template(env.local_config_file_path[i])
            )

        module_commands = self.generate_module_commands(script=env.get("script", None))
        run_prefix_commands = env.run_prefix_commands[:]
        env.run_prefix = (
            " \n".join(
                module_commands
                + list(map(template, map(template, run_prefix_commands)))
            )
            or "/bin/true || true"
        )


        if env.temp_path_template:
            env.temp_path = template(env.temp_path_template)

        if hasattr(env, "virtual_env_path") and env.virtual_env_path:
            env.virtual_env_path = template(env.virtual_env_path)

        if hasattr(env, "app_repository") and env.app_repository:
            env.app_repository = template(env.app_repository)

        if (
            # not any(
            #     "install_app" in str or "install_packages" in str
            #     for str in env.tasks
            # )
            env.task in ["install_app", "install_packages"]
            and hasattr(env, "venv")
            and str(env.venv).lower() == "true"
        ):
            # since we are going to load python VirtualEnv, so, it would be better
            # to unload any current loaded python modules, in order to avoid
            # conflicts during the execution of python program
            env.run_prefix += (
                "\n# load python from VirtualEnv"
                "\nmodule unload python\n"
                "source {}/bin/activate".format(env.virtual_env_path)
            )
    '''


    @beartype
    def available_remote_machines(self) -> Dict:
        """
        This function will return the defined remote machine available in the
        machines.yml file
        """
        # find the available and defined remote machines names in machines.yml file
        # Note: default should be remove from the list
        avail_hosts = {}
        machine_config_sources = [(self.config, "machines.yml"),
                                  (self.user_config, "machines_user.yml")]
        if self.plugin_config != None:
            machine_config_sources.append((self.plugin_config, f"machines_{env.plugin_name}_user.yml"))

        for machine_config, source_yaml in machine_config_sources:
            for machine_name in machine_config.keys():
                remote_address = None
                if "remote" in machine_config[machine_name]:
                    remote_address = machine_config[machine_name]["remote"]

                if machine_name not in avail_hosts:
                    if remote_address is not None:
                        avail_hosts.update({machine_name: { "remote_address": remote_address, "source_yaml": [source_yaml] }})
                else:
                    avail_hosts[machine_name]["source_yaml"].append(source_yaml)

        return avail_hosts




# remote_machines = RemoteMachines()

'''
def machine_config_info() -> None:
    """
    Print the `env` configuration variables for the input remote machine name

    Example Usage:
    ```sh
    fabsim <machine_name> print_machine_config_info
    ```
    """
    found = False
    console = Console()
    if remote_machines.config and env.host in remote_machines.config:
        found = True
        console.print(
            Panel(
                yaml.dump(remote_machines.config[env.host], default_flow_style=False),
                title="[bright_yellow]Defaults (machines.yml)[/bright_yellow]",
                expand=False,
                border_style="bright_yellow",
            )
        )

    if env.host in remote_machines.user_config:
        found = True
        console.print(
            Panel(
                yaml.dump(remote_machines.user_config[env.host], default_flow_style=False),
                title="[bright_cyan]User Configs (machines_user.yml)[/bright_cyan]",
                expand=False,
                border_style="bright_cyan",
            )
        )

    if remote_machines.plugin_config and env.host in remote_machines.plugin_config:
        found = True
        console.print(
            Panel(
                yaml.dump(remote_machines.plugin_config[env.host], default_flow_style=False),
                title=f"[orange_red1]Plugin Configs (machines_{env.plugin_name}_user.yml)[/orange_red1]",
                expand=False,
                border_style="orange_red1",
            )
        )

    if not found:
        raise FabSimError.RuntimeError(
            f"The machine name '{env.host}' is not found in any of the machines yaml files",
        )
'''


def my_deepcopy(obj):
    new_obj = {}
    for key in obj:
        if type(obj[key]) in [dict]:
            new_obj[key] = my_deepcopy(obj[key])
        elif isinstance(obj[key], (list)):
            new_obj[key] = obj[key][:]
        else:
            new_obj[key] = obj[key]
    return new_obj


@beartype
def findDiff(d1: Dict, d2: Dict, path: Optional[str] = "") -> List[str]:
    ret_str = []
    for key in d1:
        if key not in d2:
            ret_str.append("{} :".format(path))
            ret_str.append("  +++ {} is a new added key".format(key))
        else:
            if type(d1[key]) in [dict]:
                if path == "":
                    nested_path = key
                else:
                    nested_path = path + "->" + key
                ret_str += findDiff(d1[key], d2[key], nested_path)
            elif isinstance(d1[key], (bool, str, int)):
                if d1[key] != d2[key]:
                    ret_str.append("{} :".format(path))
                    ret_str.append("  --- {} : {}".format(key, str(d2[key])))
                    ret_str.append("  +++ {} : {}".format(key, str(d1[key])))
                else:
                    pass
            elif isinstance(d1[key], (list)):
                if set(d1[key]) != set(d2[key]):
                    ret_str.append("{} :".format(path))
                    ret_str.append("  --- {} : {}".format(key, str(d2[key])))
                    ret_str.append("  +++ {} : {}".format(key, str(d1[key])))

    return ret_str
