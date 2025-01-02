import importlib
import os
import glob
import sys
from fabsim.base.environment_manager import env
from fabsim.base.error_handler import FabSimError
import yaml
import inspect
from fabsim.base.logger import add_print_prefix
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich import print as rich_print
from fabsim.base.command_runner import cmd_runner

class PluginManager():
    def __init__(self, *args, **kwargs):
        # Initialize the plugin manager with provided arguments
        plugins_yaml_file = os.path.join(env.fabsim_root, "deploy", "plugins.yml")

        with open(plugins_yaml_file, encoding="utf-8") as file:
            self.fabsim_plugins = yaml.load(file, Loader=yaml.SafeLoader)

    def _setPluginRootDir(self, path : str):
        """check if the fabsim is called from a valid plugin directory, then set the plugin directory and name in the environment

        Args:
            path (str): the path of the directory from which the script is called
        """
        # set the plugin directory and name in the environment
        env.plugin_dir = None
        env.plugin_name = None
        # FabSim plugins should follow the naming convention Fab*.py
        pluginFilePattern = "Fab*.py"
        # Stop before falling off root of filesystem (should be platform agnostic)
        while os.path.split(os.path.abspath(path))[1]:
            # look for a py file named started with fab_ in the directory
            if glob.glob(os.path.join(path, pluginFilePattern)):
                fab_files = [os.path.basename(f) for f in glob.glob(os.path.join(path, pluginFilePattern))]
                if len(fab_files) > 1:
                    raise FabSimError.ValueError(
                        f"Multiple Fab* files {fab_files} found in the plugin directory.",
                        details="Please make sure there is only one Fab* file in the plugin directory."
                    )
                env.plugin_dir = path
                env.plugin_name = os.path.splitext(fab_files[0])[0]
                break
            path = os.path.split(path)[0]

    def _loadPluginMachinesConfig(self):
        """
        Load the plugin machine specific configuration
        """
        machine_config_file_plugin = os.path.join(
            env.plugin_dir, f"machines_{env.plugin_name}_user.yml")

        if os.path.isfile(machine_config_file_plugin):
            self.plugin_config = yaml.safe_load(open(machine_config_file_plugin, encoding="utf8"))
            # Update the default environment variables
            env.update(self.plugin_config.get("default", {}))


    def _importPluginModules(self, caller_globals : dict):
        """
        Dynamically imports plugin modules and updates the caller's global namespace with the plugin's attributes. This method modifies the global namespace of the caller to include the attributes of the specified plugin module.
        It first inserts the plugin directory into the system path, then imports the plugin module using its name.
        Raises:
            FabSimError.ImportError: If an ImportError occurs during the import process.
            FabSimError.RuntimeError: If any other exception occurs during the import process.
        """


        try:
            with add_print_prefix(prefix="loading plugin", color=28):
                print("{} ...".format(env.plugin_name))

            plugin = importlib.import_module("{}".format(env.plugin_name))
            plugin_dict = plugin.__dict__

            try:
                to_import = plugin.__all__
            except AttributeError:
                to_import = [
                    name for name in plugin_dict if not name.startswith("_")
                ]

            caller_globals.update(
                {name: plugin_dict[name] for name in to_import}
            )
            # env.localplugins.update({env.plugin_name: env.plugin_dir})

        except ImportError as e:
            print(e)
            raise FabSimError.ImportError(e.message if hasattr(e, "message") else e)
        except Exception as e:
            print(e)
            raise FabSimError.RuntimeError(e.message if hasattr(e, "message") else e)

    def loadPlugin(self, path: str):
        """
        Load the current plugin which fabsim command is called from
        """
        self._setPluginRootDir(path)
        # self._loadPluginMachinesConfig()

        # if plugin directory is set, then import the plugin modules
        if env.plugin_dir:
            # here, if we use the globals(), new changes will no be permanent for other files, so, we need to write them into global namespace seen by this frame
            sys.path.insert(0, env.plugin_dir)
            caller_globals = inspect.stack()[1][0].f_globals
            self._importPluginModules(caller_globals)

            # add plugin directory to the local templates and config files paths
            # 1. local_templates_path : encodes the default location for templates.
            env.local_templates_path.insert(
                0, os.path.join(env.plugin_dir, "templates")
            )
            # 2. local_config_file_path : encodes the default location for config files.
            env.local_config_file_path.insert(
                0, os.path.join(env.plugin_dir, "config_files")
            )

    def showAvailPlugins(self):
        """
        print list of available plugins.
        """
        table = Table(
            title="List of available plugins",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("plugin name")
        table.add_column("repository")
        for plugin_name, repo in self.fabsim_plugins.items():
            table.add_row(
                f"[blue]{plugin_name}[/blue]",
                f"{repo['repository']}"
            )
        console = Console()
        console.print(table,new_line_start=True)


    def _warn_duplicate_plugin(self, plugin_dir, plugin_name, random_string_length=5):
        """Warn user about the duplicate plugin directory."""
        console = Console()
        console.print(
            Panel(
                f"[orange_red1]The {plugin_name} "
                f"plugin directory already exists in the current directory {plugin_dir}. ",
                title="[red1]Error[/red1]",
                expand=False,
            ),
            new_line_start=True,
        )

    def installPlugin(self, plugin_name: str, curr_dir: str):
        """
        Install a FabSim3 plugin.

        Args:
            plugin_name (str): plugin name
            branch (str, optional): branch name

        """
        if env.plugin_name != None:
            raise FabSimError.RuntimeError(
                "Install plugin command is not allowed to run from a plugin directory.",
                details=f"Install plugin command called inside {env.plugin_name} plugin directory."
            )

        if plugin_name not in self.fabsim_plugins:
            raise FabSimError.RuntimeError(
                f"'{plugin_name}' plugin not found in the available plugins.",
                details="To see the list of available plugins, run 'fabsim -l plugins'",
            )

        # check if the requested pluging is already installed or not
        plugin_dir = curr_dir
        if os.path.exists(f"{plugin_name}"):
            self._warn_duplicate_plugin(plugin_dir, plugin_name)
            return

        rich_print(
            Panel.fit(
                f"Installing [orange_red1]{plugin_name}[/orange_red1] plugin...",
                border_style="orange_red1",
            )
        )

        info = self.fabsim_plugins[plugin_name]
        cmd_runner.local(f"git clone {info['repository']} \"{os.path.join(plugin_dir,plugin_name)}\"")

        rich_print(
            Panel.fit(
                f"Plugin [green]{plugin_name}[/green] installed successfully.",
                border_style="green",
            )
        )

plugin_manager = PluginManager()