import argparse
from fabsim.base.environment_manager import env



class CommandLineParser:
    """
    A class to parse FabSim command-line arguments using argparse.
    """

    def __init__(self):
        self.parser = argparse.ArgumentParser()
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
        if self.args.remote:
            # Set the remote machine name in the environment to be used by the remote machine manager to show the configuration
            env.host = self.args.remote
            return True
        return False

    def requestInstallPlugin(self) -> bool:
        """
        check if the user requested to install a plugin
        """
        if self.args.install:
            return True
        return False

    def getRequestedPluingName(self) -> str:
        """
        Get the requested plugin name to be Installed
        """
        return self.args.install

    def getSubCommands(self) -> list:
        """
        Get the command-line input arguments
        """
        return self.args.cmd

