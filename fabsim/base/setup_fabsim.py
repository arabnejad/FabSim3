"""Module to install, update, and remove FabSim3 plugins."""

import random
import string
from os import path, rename, getcwd

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rich_print
from fabsim.base.decorators import task
from fabsim.base.environment_manager import env
from fabsim.base.command_runner import cmd_runner
from fabsim.deploy.templates import template
from fabsim.base.error_handler import FabSimError

'''
def warn_duplicate_plugin(plugin_dir, plugin_name, random_string_length=5):
    """Warn user about the duplicate plugin directory."""

    res = "".join(
        random.choices(
            string.ascii_uppercase + string.digits, k=random_string_length
        )
    )
    console = Console()
    console.print(
        Panel(
            f"[orange_red1]The {plugin_name} "
            "plugin directory already exists in the current directory. ",
            title="[red1]Error[/red1]",
            expand=False,
        ),
        new_line_start=True,
    )




def install_plugin(plugin_name):
    """
    Install a specific FabSim3 plugin.

    Args:
        plugin_name (str): plugin name
        branch (str, optional): branch name
    """

    plugins_yaml_file = path.join(env.fabsim_root, "deploy", "plugins.yml")
    with open(plugins_yaml_file, encoding="utf-8") as file:
        plugins = yaml.load(file, Loader=yaml.SafeLoader)

    if plugin_name not in plugins:
        raise FabSimError.RuntimeError(
            f"'{plugin_name}' plugin not found in the available plugins.",
            details="To see the list of available plugins, run 'fabsim -l plugins'",
        )
        return


    # check if the requested pluging is already installed or not
    plugin_dir = getcwd()
    if path.exists(f"{plugin_name}"):
        warn_duplicate_plugin(plugin_dir, plugin_name)
        return

    rich_print(
        Panel.fit(
            f"Installing [orange_red1]{plugin_name}[/orange_red1] plugin...",
            border_style="orange_red1",
        )
    )

    info = plugins[plugin_name]
    local(f"git clone {info['repository']} \"{path.join(plugin_dir,plugin_name)}\"")

    rich_print(
        Panel.fit(
            f"Plugin [green]{plugin_name}[/green] installed successfully.",
            border_style="green",
        )
    )
'''
'''
def avail_plugin():
    """
    print list of available plugins.
    """
    plugins_yaml_file = path.join(env.fabsim_root, "deploy", "plugins.yml")
    with open(plugins_yaml_file, encoding="utf-8") as file:
        plugins = yaml.load(file, Loader=yaml.SafeLoader)

    table = Table(
        title="List of available plugins",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("plugin name")
    table.add_column("repository")
    for plugin_name, repo in plugins.items():
        table.add_row(
            f"[blue]{plugin_name}[/blue]",
            f"{repo['repository']}"
        )
    console = Console()
    console.print(table,new_line_start=True)
'''




def get_clean_fabsim_dirs_string(prefix):
    """
    Returns the commands required to clean the fabric directories. This
    is not in the env, because modifying this is likely to break FabSim
    in most cases. This is stored in an individual function, so that the
    string can be appended in existing commands, reducing the
    performance overhead.
    """
    return (
        f"rm -rf $config_path/{prefix}*; "
        f"rm -rf $results_path/{prefix}*; "
        f"rm -rf $scripts_path/{prefix}*"
    )


@task
def clean_fabsim_dirs(prefix=""):
    """
    Cleans up directories used by FabSim.
    """
    cmd_runner.run(template(get_clean_fabsim_dirs_string(prefix)))


@task
def setup_ssh_keys(password=""):
    """
    Sets up SSH key pairs for FabSim access.
    """
    console = Console()
    console.print(
        Panel(
            "[magenta]To set up your SSH keys, you will be logged in to your\n"
            "local machine once using SSH. You may be asked to provide\n"
            "your password once to facilitate this login.[/magenta]",
            title="[dark_cyan]Setup SSH keys[/dark_cyan]",
            expand=False,
        )
    )

    home = path.expanduser("~")
    if path.isfile(f"{home}/.ssh/id_rsa.pub"):
        print("local id_rsa key already exists.")
    else:
        cmd_runner.local(
            f'ssh-keygen -q -f {home}/.ssh/id_rsa'
            f' -t rsa -b 4096 -N "{password}"'
        )
    cmd_runner.local(
        template(
            "ssh-copy-id -i ~/.ssh/id_rsa.pub "
            f"{env.host_string} 2>ssh_copy_id.log"
        )
    )
