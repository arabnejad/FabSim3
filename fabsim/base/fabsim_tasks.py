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
def clear_results(name: str = "") -> None:
    """
    Completely wipe all result files from the remote.

    Args:
        name (str, optional): the name of result folder
    """
    job_manager.configure_job_paths(name)
    cmd_runner.run(template("rm -rf $job_results_contents"))

@task
def clean_fabsim_dirs(prefix=""):
    """
    Cleans up FabSim directories on remote machine by removing the relevant files
    and directories based on the provided prefix.
    """
    clean_commands = (
        f"rm -rf $config_path/{prefix}*; "
        f"rm -rf $results_path/{prefix}*; "
        f"rm -rf $scripts_path/{prefix}*"
    )
    cmd_runner.run(template(clean_commands))
