import argparse
from fabsim.base.environment_manager import env



class CommandLineParser:
    """
    A class to parse FabSim command-line arguments using argparse.
    """

    def __init__(self):
        self.parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
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
                    "help": "list available tasks or machines (choices: 'tasks', 'machines', 'plugins')",
                    "metavar": ""
                }
            },
            {
                "name": ["-i", "--install"],
                "kwargs": {
                    "action": "store",
                    "type" : str,
                    "help": "Install a FabSim plugin",
                    "metavar": ""
                }
            },
            {
                "name": ["-r", "--remote"],
                "kwargs": {
                    "action": "store",
                    "type": str,
                    "help": "Show the configuration variables for the requested remote machine name",
                    "metavar": ""
                }
            },
            {
                "name": ["--install_packages"],
                "kwargs": {
                    "action": "store",
                    "nargs": '+',  # Accept one or more package names
                    "type": str,
                    "help": """Specify the packages to install.
- You can list multiple package names separated by spaces.
  Example:
    fabsim --install_packages p1 p2 p3 --remote <remote_machine_name>

- You can also setup virtual environment by passing the --venv flag.
  Example:
    fabsim --install_packages p1 p2 p3 --remote <remote_machine_name> --venv true
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
                    "help": "Set up virtual environment (true or false, default: false)",
                    "metavar": ""
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
        if self.args.remote and not self.args.install_packages:
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

