import argparse
from fabsim.base.environment_manager import env


def colorize(text, color):
    colors = {
        "cyan": "\033[96m",
        "yellow": "\033[93m",
        "green": "\033[92m",
        "red": "\033[91m",
        "end": "\033[0m",
    }
    return f"{colors[color]}{text}{colors['end']}"

class CommandLineParser:
    """
    A class to parse FabSim command-line arguments using argparse.
    """

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            usage=colorize("""
    fabsim3 [-h] [-l] [-i] [-r] [--install_packages  [...]] [--venv]
""", "cyan"),
            formatter_class=argparse.RawTextHelpFormatter
        )
        self._setup_arguments()
        self.args = None

    def _setup_arguments(self):
        """
        Define the input arguments to be handled by the parser.
        """

        arguments = [
            {
                "name": ["-l", "--list"],
                "kwargs": {
                    "choices": ["tasks", "machines", "plugins"],
                    "help": """list available tasks,machines, or plugins (choices: 'tasks', 'machines', 'plugins')
  Example:
        > fabsim --list tasks
        > fabsim --list machines
        > fabsim --list plugins

""",
                    "metavar": ""
                }
            },
            {
                "name": ["-i", "--install"],
                "kwargs": {
                    "action": "store",
                    "type" : str,
                    "help": """Install a FabSim plugin
  Example:
        > fabsim --install <plugin_name>

""",
                    "metavar": ""
                }
            },
            {
                "name": ["-r", "--remote"],
                "kwargs": {
                    "action": "store",
                    "type": str,
                    "help": """Show the configuration variables for the requested remote machine name
  Example:
        > fabsim --install <remote_machine_name>

""",
                    "metavar": ""
                }
            },
            {
                "name": ["--install_packages"],
                "kwargs": {
                    "action": "store",
                    "nargs": '+',  # Accept one or more package names
                    "type": str,
                    "help": """Install python packages to be installed in the target remote machine.
You can list multiple package names separated by spaces.
  Example:
        > fabsim --install_packages p1 p2 p3 --remote <remote_machine_name>
You can also setup virtual environment by passing the --venv flag.
  Example:
        > fabsim --install_packages p1 p2 p3 --remote <remote_machine_name> --venv true

""",
                    "metavar": ""
                }
            },
            {
                "name": ["--venv"],
                "kwargs": {
                    "action": "store",
                    "choices": ["true", "false"],
                    "type" : str,
                    "default": 'false',
                    "help": argparse.SUPPRESS, # hide --venv flag from help
                    "metavar": ""
                }
            },
            {
                "name": ["--setup_ssh_keys"],
                "kwargs": {
                    "action": "store_true",
                    "help": """Configure passwordless SSH access to the remote machine.
  Example:
        > fabsim --setup_ssh_keys --remote <remote_machine_name>

""",
                }
            },
            {
                "name": ["--show_config"],
                "kwargs": {
                    "action": "store_true",
                    "help": """Check if any configuration is available for FabSim.
  Example:
        > fabsim --show_config

""",
                }
            },

        ]

        # Iterate over the arguments and add them to the parser
        for arg in arguments:
            self.parser.add_argument(*arg["name"], **arg["kwargs"])

        # Add positional argument to capture any additional input args
        self.parser.add_argument("cmd", nargs="*", help=argparse.SUPPRESS)

    def parse_arguments(self):
        """
        Parse the command-line arguments.
        """
        self.args = self.parser.parse_args()

    def requestShowAvailableTasks(self) -> bool:
        """
        check if the user requested to show the available tasks
        """
        if self.args.list and self.args.list == "tasks":
            return True
        return False

    def requestShowAvailableMachines(self) -> bool:
        """
        check if the user requested to show the available machines
        """
        if self.args.list and self.args.list == "machines":
            return True
        return False

    def requestShowAvailablePlugins(self) -> bool:
        """
        check if the user requested to show the available plugins
        """
        if self.args.list and self.args.list == "plugins":
            return True
        return False

    def requestShowRemoteMachineConfig(self) -> bool:
        """
        check if the user requested to show the remote machine configuration
        """
        if self.args.remote and not self.args.install_packages and not self.args.setup_ssh_keys:
            return True
        return False

    def requestInstallPlugin(self) -> bool:
        """
        check if the user requested to install a plugin
        """
        if self.args.install:
            return True
        return False

    def getRequestRemoteMachineName(self) -> bool:
        """
        check if the user requested to show the remote machine configuration
        """
        return self.args.remote

    def getRequestedPluingName(self) -> str:
        """
        Get the requested plugin name to be Installed
        """
        return self.args.install

    def requestInstallPackages(self) -> bool:
        """
        check if the user requested to install packages on remote machine
        """
        if self.args.install_packages and self.args.remote:
            return True
        return False

    def requestShowConfig(self) -> bool:
        """
        check if the user requested to show the FabSim configuration
        """
        return self.args.show_config

    def requestSetupSshKey(self) -> bool:
        """
        check if the user requested to setup passwordless SSH access to the remote machine
        """
        if self.args.setup_ssh_keys and self.args.remote:
            return True
        return False

    def getRequestedInstallPackages(self) -> list:
        """
        check if the user requested to install packages on remote machine
        """
        # return self.args.install_packages
        return list(map(str, self.args.install_packages))

    def requestUseVenv(self) -> bool:
        """
        check if the user requested to install packages on remote machine
        """
        return self.args.venv.lower() == "true"

    def getSubCommands(self) -> list:
        """
        Get the command-line input arguments
        """
        return self.args.cmd

