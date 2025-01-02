import os
from beartype import beartype
from fabsim.base.environment_manager import env
from fabsim.base.config_fabsim import FABSIM_CONFIG_DIR
from fabsim.base.error_handler import FabSimError
import yaml
from beartype.typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from fabsim.base.decorators import  task, old_task
from rich.console import Console
from rich.table import Table, box

class RemoteMachineManager():
    def __init__(self):
        # FabSim machines.yml file
        self.config = self._loadYamlConfigFile(env.fabsim_config_dir, "machines.yml")
        # Include private machines
        private_config = self._loadYamlConfigFile(env.fabsim_config_dir, "machines_private.yml", checkFileExists = False)
        self.config.update(private_config)

        # FabSim machines_user.yml file
        self.user_config = self._loadYamlConfigFile(env.fabsim_config_dir, "machines_user.yml")

        # Plugin machines_<plugin_name>_user.yml file
        self.plugin_config = None

        # Update the default environment variables
        env.update(self.config["default"])
        env.update(self.user_config["default"])
        # env.complete_environment()

        self._available_remote_machines()


    def _loadYamlConfigFile(self, dir : str, file_name : str, checkFileExists : bool = True) -> dict:
        """
        Load the machine specific configuration
        """
        config = {}

        file_path = os.path.join(dir, file_name)
        try:
            config = yaml.safe_load(open(file_path, encoding="utf8"))
        except FileNotFoundError as e:
            if checkFileExists == False:
                pass
            else:
                raise FabSimError.FileNotFoundError(
                    f"There is NO {file_name} under {dir} directory!!!",
                    details="Please check the directory and try again, or run config_fabsim to generate the required files"
                )
        except Exception as e:
            raise FabSimError.RuntimeError(
                f"Error loading {file_path}",
                details=f"Error: {e}"
            )

        return config

    def loadPluginMachinesConfig(self):
        """
        Load the plugin machine specific configuration
        """
        if env.plugin_dir is None:
            return
        machine_name = env.host
        self.plugin_config = self._loadYamlConfigFile(env.plugin_dir, f"machines_{env.plugin_name}_user.yml", checkFileExists = False)

        # Update the default environment variables
        env.update(self.plugin_config.get("default", {}))
        env.update(self.plugin_config.get(machine_name, {}))

        # save available user's remote machines in the environment
        machine_config_sources=[((self.plugin_config, f"machines_{env.plugin_name}_user.yml"))]
        env.avail_machines.update(self._get_avail_machines(machine_config_sources))

        # env.complete_environment()

    def loadMachine(self, machine_name : str) -> None:
        """
        Load the machine-specific configurations.
        Completes additional paths and interpolates them, via `complete_environment`.
        """

        env.machine_name = machine_name

        env.update(self.config.get(machine_name, {}))
        env.update(self.user_config.get(machine_name, {}))
        env.update(self.plugin_config.get(machine_name, {}))

        env.modules = self.config["default"]["modules"]
        env.modules.update(self.config.get(machine_name, {}).get("modules", {}))
        env.modules.update(self.user_config.get(machine_name, {}).get("modules", {}))
        env.modules.update(self.plugin_config.get(machine_name, {}).get("modules", {}))

        # TODO: check if we need these lines or not, it will be called later in complete_environment
        # module_commands = self.generate_module_commands()
        # run_prefix_commands = env.run_prefix_commands[:]
        # env.run_prefix = (
        #     " \n".join(module_commands + list(map(env.template, run_prefix_commands)))
        #     or "echo THE FIRST Running..."
        # )

        env.complete_environment()

    @beartype
    def _available_remote_machines(self) -> None:
        """
        This function will return the defined remote machine available in the
        machines.yml file
        """
        # find the available and defined remote machines names in machines.yml file
        # Note: default should be remove from the list
        avail_machines = {}
        machine_config_sources = [(self.config, "machines.yml"),
                                  (self.user_config, "machines_user.yml")]
        if self.plugin_config != None:
            machine_config_sources.append((self.plugin_config, f"machines_{env.plugin_name}_user.yml"))

        # save available remote machines in the environment
        env.avail_machines = self._get_avail_machines(machine_config_sources)


    def _get_avail_machines(self, machine_config_sources) -> dict:
        avail_machines = {}
        for machine_config, source_yaml in machine_config_sources:
            for machine_name in machine_config.keys():
                remote_address = None
                if "remote" in machine_config[machine_name]:
                    remote_address = machine_config[machine_name]["remote"]

                if machine_name not in avail_machines:
                    if remote_address is not None:
                        avail_machines.update({machine_name: { "remote_address": remote_address, "source_yaml": [source_yaml] }})
                else:
                    avail_machines[machine_name]["source_yaml"].append(source_yaml)

        return avail_machines


    def showAvailMachines(self) -> None:
        """
        Print the available remote machines for job submission
        """
        table = Table(
            title="\n\nList of available remote machines",
            show_header=True,
            box=box.ROUNDED,
            header_style="dark_cyan",
        )
        table.add_column("machine name", style="blue")
        table.add_column("machine address", style="bright_yellow")
        table.add_column("source yaml", style="white")

        for machine_name, machine_details in env.avail_machines.items():
            machine_address = machine_details["remote_address"]
            source_yaml = ", ".join(machine_details["source_yaml"])
            table.add_row(machine_name, machine_address, source_yaml)
        console = Console()
        console.print(table)

    def printMachineConfigInfo(self) -> None:
        """
        Print the `env` configuration variables for the input remote machine name

        Example Usage:
        ```sh
        fabsim -r <machine_name>
        or
        fabsim --remote <machine_name>
        ```
        """
        found = False
        console = Console()
        if self.config and env.host in self.config:
            found = True
            console.print(
                Panel(
                    yaml.dump(self.config[env.host], default_flow_style=False),
                    title="[bright_yellow]Defaults (machines.yml)[/bright_yellow]",
                    expand=False,
                    border_style="bright_yellow",
                )
            )

        if env.host in self.user_config:
            found = True
            console.print(
                Panel(
                    yaml.dump(self.user_config[env.host], default_flow_style=False),
                    title="[bright_cyan]User Configs (machines_user.yml)[/bright_cyan]",
                    expand=False,
                    border_style="bright_cyan",
                )
            )

        if self.plugin_config and env.host in self.plugin_config:
            found = True
            console.print(
                Panel(
                    yaml.dump(self.plugin_config[env.host], default_flow_style=False),
                    title=f"[orange_red1]Plugin Configs (machines_{env.plugin_name}_user.yml)[/orange_red1]",
                    expand=False,
                    border_style="orange_red1",
                )
            )

        if not found:
            raise FabSimError.RuntimeError(
                f"The machine name '{env.host}' is not found in any of the machines yaml files",
            )



remote_machine_manager = RemoteMachineManager()

