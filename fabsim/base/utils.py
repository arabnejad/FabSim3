import inspect
import os
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from os import system
from pathlib import Path
from pprint import pprint
from tempfile import NamedTemporaryFile
from beartype.typing import Callable
from beartype.typing import Dict
from rich import print as rich_print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table, box
from rich.text import Text
from fabsim.base.error_handler import FabSimError
from beartype import beartype
from beartype.typing import Optional

from fabsim.base.environment_manager import env


def show_avail_tasks() -> None:
    """
    Print the available and callable tasks (FabSim3 APIs or plugins tasks)
    """
    avail_task_dict = {}
    for task_name, task_obj in env.avail_tasks.items():

        if not hasattr(task_obj, "task_type"):
            continue

        if hasattr(task_obj, "plugin_name"):
            key = "{} {}".format(task_obj.plugin_name, task_obj.task_type)
        else:
            key = "{}".format(task_obj.task_type)

        if key not in avail_task_dict:
            avail_task_dict.update({key: []})
        avail_task_dict[key].append(task_name)

    table = Table(
        title="\n\nList of available Tasks",
        show_header=True,
        show_lines=True,
        # expand=True,
        box=box.ROUNDED,
        header_style="dark_cyan",
    )
    table.add_column("Task Type", style="blue")
    table.add_column("Tasks name", style="bright_yellow")

    for task_type, tasks_name in avail_task_dict.items():
        table.add_row(
            "{}".format(task_type),
            "{}".format(",\n".join(tasks_name)),
        )
    console = Console()
    console.print(table)


class Prefixer(object):
    def __init__(self, prefix, orig):
        self.prefix = prefix
        self.orig = orig

    def write(self, text):
        for t in text.rstrip().splitlines():
            self.orig.write(self.prefix + t + "\n")

    def __getattr__(self, attr):
        return getattr(self.orig, attr)


def colored(color_code, text):
    return "\033[38;5;{}m{}\033[0;0m ".format(color_code, text)


@contextmanager
def add_print_prefix(prefix, color=24):
    # source : https://stackabuse.com/how-to-print-colored-text-in-python
    # https://www.ditig.com/publications/256-colors-cheat-sheet
    current_out = sys.stdout
    try:
        sys.stdout = Prefixer(
            prefix=colored(color, "[{}]".format(prefix)), orig=current_out
        )
        yield
    finally:
        sys.stdout = current_out

'''
@beartype
def find_config_file_path(
    name: str,
    ExceptWhenNotFound: Optional[bool] = True
) -> str:
    """
    Find the config file path

    Args:
        name (str): Description
        ExceptWhenNotFound (bool, optional): Description

    Returns:
        Union[bool, str]: - `False`: if the input config name not found
        - the path of input config name
    """
    # Prevent of executing localhost runs on the FabSim3 root directory
    if env.host == "localhost" and env.work_path == env.fabsim_root:
        msg = (
            "The localhost run dir is same as your FabSim3 folder\n"
            "To avoid any conflict of config folder, please consider\n"
            "changing your home_path_template variable\n"
            "you can easily modify it by updating localhost entry in\n"
            "your FabSim3/fabsim/deploy/machines_user.yml file\n\n"
            "Here is the suggested changes:\n\n"
        )

        rich_print(
            Panel(
                "{}[green3]{}[/green3]".format(msg),
                title="[red1]Error[/red1]",
                border_style="red1",
                expand=False,
            )
        )
        exit()

    path_used = None
    for p in env.local_config_file_path:
        config_file_path = os.path.join(p, name)
        if os.path.exists(config_file_path):
            path_used = config_file_path

    if path_used is None:
        if ExceptWhenNotFound:
            raise FabSimError.FileNotFoundError(
                "Error: config file directory '{}' " "not found in: ".format(
                    name
                ),
                env.local_config_file_path,
            )
        else:
            return False
    return path_used
'''

@beartype
def execute(task: Callable, *args, **kwargs) -> None:
    """
    Execute a task (callable function).
    The input arg `task` can be an actual callable function or its name.

    The target function can be warped by @task or not.

    """
    f_globals = inspect.stack()[1][0].f_globals
    if callable(task):
        task(*args, **kwargs)
    elif task in f_globals:
        f_globals[task](*args, **kwargs)
    else:
        msg = (
            "The request task [green3]{}[/green3] passed to execute() "
            "function can not be found !!!".format(task)
        )
        console = Console()
        console.print(
            Panel(
                "{}".format(msg),
                title="[red1]Error[/red1]",
                border_style="red1",
                expand=False,
            )
        )


class OpenVPNContext(object):
    """
    Connect to and disconnect from OpenVPN,
    if a configuration is specified in the environment.
    Otherwise, do nothing.

    Usage:
    ```python
    with OpenVPNContext(env):
        # do stuff while (potentially) connected through VPN
    ```
    """

    _AUTH_ENV_VARS = ['OPENVPN_AUTH_USER', 'OPENVPN_AUTH_PASS']

    def __init__(self, env):
        self._config = None
        self._auth_user_pass = None
        path_err_msg = 'The value of X for this machine is not a valid file.'
        if hasattr(env, "openvpn_config"):
            self._config = env.openvpn_config
            if not Path(self._config).is_file():
                print(path_err_msg.replace('X', self._config), file=sys.stderr)
                exit(1)
        env_key_auth = 'openvpn_auth_user_pass'
        if hasattr(env, env_key_auth):
            self._auth_user_pass = env[env_key_auth]
            if not isinstance(self._auth_user_pass, bool) or \
                (isinstance(self._auth_user_pass, str) and
                    not Path(self._auth_user_pass).is_file()):
                print(path_err_msg.replace(
                    'X', self._auth_user_pass)[:-1] + ' or boolean.',
                    file=sys.stderr)
                exit(1)
            if len(set(OpenVPNContext._AUTH_ENV_VARS)
                   .intersection(os.environ)) != 2:
                print(' and '.join(OpenVPNContext._AUTH_ENV_VARS) +
                      f' must be set in environment ({env_key_auth} is true).')
                exit(1)

    def _print(msg):
        rich_print(
            Panel.fit(
                msg,
                title=f"[yellow]{OpenVPNContext.__name__}[/yellow]",
                border_style="yellow",
            )
        )

    def __enter__(self):
        self._p = None
        if self._config is not None:
            OpenVPNContext._print("Starting VPN...")
            cmd = ["openvpn", "--config", self._config]
            if platform.system().lower() in ["linux", "darwin"]:
                cmd = ["sudo", "-n"] + cmd  # OpenVPN requires root privileges
            # Create a temporary file for holding credentials from environment
            # (Workaround: The shell might not support the <() operator and
            #  using pipes does not seem to work with the OpenVPN client)
            with NamedTemporaryFile(mode='wt', delete=True) as temporaryFile:
                if self._auth_user_pass is True:
                    for v in OpenVPNContext._AUTH_ENV_VARS:
                        temporaryFile.write(f'{os.environ[v]}\n')
                    temporaryFile.flush()
                    self._auth_user_pass = temporaryFile.name
                if type(self._auth_user_pass) is str:
                    cmd += ["--auth-user-pass", self._auth_user_pass]
                self._p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL)
                # Wait a bit for the VPN connection to be established
                time.sleep(3)
            if platform.system().lower() in ["linux", "darwin"]:
                system("stty sane")  # sudo messes up the terminal output
            if self._p.poll() is not None:
                OpenVPNContext._print("VPN not running")
                exit(1)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._p is not None:
            OpenVPNContext._print("Stopping VPN...")
            try:
                self._p.kill()
                self._p = None
            except Exception as e:
                pass
