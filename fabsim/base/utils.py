import inspect
import os
import platform
import subprocess
import sys
import time
from os import path
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
from fabsim.deploy.templates import (
    script_templates,
    template,
)
import tempfile
import os
from fabsim.base.job_manager import job_manager
from fabsim.base.command_runner import cmd_runner

from fabsim.base.environment_manager import env, FABSIM_CONFIG_DIR


def display_fabsim_config() -> None:
    """
    Display the availability status of FabSim3 configuration files
    """
    console = Console()

    # Check if the configuration directory exists and set the message accordingly
    if os.path.exists(FABSIM_CONFIG_DIR):
        message = f"FabSim3 configuration files are available in [green]{FABSIM_CONFIG_DIR}"
    else:
        message = (
            f"[red]FabSim3 configuration files are not available in {FABSIM_CONFIG_DIR}\n\n"
            "[white]Please run [green]config_fabsim [white]command to create the configuration files"
        )

    # Display the message within a styled panel
    console.print(
        Panel(
            message,
            title="[dark_cyan]FabSim3 Configuration[/dark_cyan]",
            border_style="dark_cyan",
            expand=False,
        ),
        new_line_start=True,
    )


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

@beartype
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
            f"ssh-copy-id -i ~/.ssh/id_rsa.pub {env.host_string}"
        )
    )

@beartype
def install_packages(packages : list, venv: bool = False):
    """
    Install list of packages defined in deploy/applications.yml

    Args:
        venv (bool, optional): True means the VirtualEnv is already installed
            in the remote machine
    """
    tmp_app_dir = env.pather.join(
            tempfile._get_default_tempdir(),
            next(tempfile._get_candidate_names()),
            "tmp_app",
        )
    cmd_runner.local("mkdir -p {}".format(tmp_app_dir))
    # Download packages
    for package in packages:
        cmd_runner.local(f"pip3 download --no-binary=:all: -d {tmp_app_dir} {package}")
    # Sort downloaded packages by modification time
    dependencies = sorted(Path(tmp_app_dir).iterdir(), key=lambda f: f.stat().st_mtime)
    dependencies = [os.path.basename(dep) for dep in dependencies]
    # Create  directory in the remote machine to store dependency packages
    app_repository = template("/tmp/App_repo")
    cmd_runner.run(f"mkdir -p {app_repository}")
    # Transfer dependencies to remote machine
    for dep in os.listdir(tmp_app_dir):
        cmd_runner.local(
            template(
                f"rsync -pthrvz -e 'ssh -p $port' {tmp_app_dir}/{dep} {env.get_remote_address_str()}:{app_repository}"
            )
        )
    #
    script_path = os.path.join(tmp_app_dir, "script")
    # Write the Install command in a file
    with open(script_path , "w") as script_file:
        install_dir = "--user"
        if venv:
            script_file.write(
                f"""
                if [ ! -d {env.virtual_env_path} ]; then
                    python -m venv {env.virtual_env_path} || echo 'WARNING: virtualenv is not installed or has issues'
                fi
                source {env.virtual_env_path}/bin/activate
                """
            )
            install_dir_flag = ""

        # First install the additional_dependencies
        for dep in reversed(dependencies):
            print(dep)
            if dep.endswith(".zip"):
                pkg_dir = dep.replace(".zip", "")
                script_file.write(
                    f"unzip {app_repository}/{dep} -d {app_repository} && "
                    f"pip install {app_repository}/{pkg_dir}\n"
                )

            elif dep.endswith(".tar.gz"):
                pkg_dir = dep.replace(".tar.gz", "")
                script_file.write(
                    f"tar xf {app_repository}/{dep} -C {app_repository} && "
                    f"pip install {app_repository}/{pkg_dir}\n"
                )

    # Add temporary directory to local templates path
    env.local_templates_path.insert(0, tmp_app_dir)

    # Set environment variables
    env.update(dict(script="script", config="install_packages", job_name="install_packages"))

    # Generate job and ensure required directories exist
    env.job_results, env.job_results_local = job_manager.generate_job_with_template()
    directories = ["$config_path", "$results_path", "$scripts_path"]
    command = " && ".join(f"mkdir -p {directory}" for directory in directories)
    cmd_runner.run(template(command))

    # Create job script and transfer to remote machine
    env.job_script = script_templates(env.batch_header_install_app, env.script)
    env.dest_name = env.pather.join(env.scripts_path, env.pather.basename(env.job_script))
    cmd_runner.put(env.job_script, env.dest_name)
    # Execute/Submit the job script
    cmd_runner.run(template("mkdir -p $job_results"))
    cmd_runner.run(template(f"{env.job_dispatch} {env.dest_name}"), cd=env.pather.dirname(env.job_results))
    # Cleanup
    cmd_runner.local("rm -rf {}".format(tmp_app_dir))


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
