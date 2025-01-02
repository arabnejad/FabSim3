from os import path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from fabsim.base.decorators import task
from beartype.typing import Optional
from beartype import beartype
from pathlib import Path
import yaml
from fabsim.base.environment_manager import env
from fabsim.base.command_runner import cmd_runner
from shutil import copy, copyfile, rmtree

from fabsim.deploy.templates import (
    script_templates,
    template,
)
from fabsim.base.job_manager import job_manager
@task
@beartype
def fetch_results(
    name: Optional[str] = "",
    regex: Optional[str] = "",
    files: Optional[str] = None,
) -> None:
    """
    This is a wrapper for the job_manager.fetch_results method.
    """
    job_manager.fetch_results(name, regex, files)


@task
@beartype
def clear_results(name: str) -> None:
    """
    Completely wipe all result files from the remote.

    Args:
        name (str, optional): the name of result folder
    """
    job_manager.configure_job_paths(name)
    cmd_runner.run(template("rm -rf $job_results_contents"))


@task
@beartype
def fetch_configs(config: str) -> None:
    """
    Fetch config files from the remote machine, via `rsync`.

    Example Usage:

    ```sh
    fab eagle_vecma fetch_configs:mali
    ```

    Args:
        config (str): the name of config directory
    """
    job_manager.set_config(config)
    if env.manual_gsissh:
        cmd_runner.local(
            template(
                "globus-url-copy -cd -r -sync "
                "gsiftp://$remote/$job_config_path/ "
                "file://$job_config_path_local/"
            )
        )
    else:
        cmd_runner.local(
            template(
                "rsync -pthrvz $username@$remote:$job_config_path/ "
                "$job_config_path_local"
            )
        )


@task
@beartype
def put_results(name: str) -> None:
    # TODO: #############################################################
    # TODO: this seems to be not used at all anywhere, should be removed
    # TODO: #############################################################
    """
    Transfer result files to a remote. Local path to find result
    directories is specified in machines_user.json. This method is not
    intended for normal use, but is useful when the local machine
    cannot have an entropy mount, so that results from a local machine
    can be sent to entropy, via 'fab legion fetch_results; fab entropy
    put_results'

    Args:
        name (str, optional): the name of results directory
    """
    job_manager.configure_job_paths(name)
    cmd_runner.run(template("mkdir -p $job_results"))
    if env.manual_gsissh:
        cmd_runner.local(
            template(
                "globus-url-copy -p 10 -cd -r -sync "
                "file://$job_results_local/ "
                "gsiftp://$remote/$job_results/"
            )
        )
    else:
        cmd_runner.rsync_project(
            local_dir=env.job_results_local + "/", remote_dir=env.job_results
            )



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
            f"ssh-copy-id -i ~/.ssh/id_rsa.pub {env.host_string}"
        )
    )
