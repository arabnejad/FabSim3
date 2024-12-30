
from fabsim.base.decorators import task
from beartype.typing import Optional
from beartype import beartype
from fabsim.base.environment_manager import env
from fabsim.base.command_runner import cmd_runner
import os
from fabsim.deploy.templates import (
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