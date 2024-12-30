
import os
import re
import subprocess
import tempfile
from pathlib import Path
from pprint import pformat, pprint
from shutil import copy, copyfile, rmtree

import numpy as np
from beartype import beartype
from beartype.typing import Callable, Optional, Tuple, Union
from rich import print as rich_print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table, box

from fabsim.base.job_manager import job_manager
from fabsim.base.decorators import task
from fabsim.base.environment_manager import env
from fabsim.base.manage_remote_job import *
from fabsim.base.MultiProcessingPool import MultiProcessingPool
from fabsim.base.command_runner import cmd_runner
from fabsim.base.setup_fabsim import *
# from fabsim.deploy._machines import *
import inspect
from fabsim.deploy.templates import (
    script_template_content,
    script_templates,
    template,
)
from fabsim.base.error_handler import FabSimError

def job(job_args : dict, prepare_only=False):
    """
    Internal low level job launcher.
    Parameters for the job are determined from the prepared fabric environment
    Execute a generic job on the remote machine.

    To improve the total job submission, and reduce the number of SSH
    connection for job files/folders transmission, the job submission workflow
    divided into 3 individual sub-tasks:

    1. job_preparation
    2. job_transmission
    3. job_submission

    Returns the generate jobs scripts for submission on the remote machine.
    """
    # check if with_config function is already called or not
    if not hasattr(env, "job_config_path"):
        raise FabSimError.RuntimeError(
            "Function with_config did NOT called, ",
            details="Please call it before calling job()"
        )

    env.update(job_args)

    #   Add label, mem, core to env.
    job_manager.calculate_required_nodes()
    job_manager.calculate_total_memory()

    if "sweepdir_items" in job_args:
        env.is_ensemble = True
    else:
        env.is_ensemble = False

    ########################################################
    #  temporary folder to save job files/folders/scripts  #
    ########################################################
    env.tmp_work_path = env.pather.join(
        tempfile._get_default_tempdir(),
        next(tempfile._get_candidate_names()),
        "FabSim3",
        # env.fabric_dir
    )

    if os.path.exists(env.tmp_work_path):
        rmtree(env.tmp_work_path)
    # the config_files folder is already transfered by put_config
    env.tmp_results_path = env.pather.join(env.tmp_work_path, "results")
    env.tmp_scripts_path = env.pather.join(env.tmp_work_path, "scripts")
    os.makedirs(env.tmp_scripts_path)
    os.makedirs(env.tmp_results_path)

    POOL = MultiProcessingPool(PoolSize=int(env.nb_process))

    #####################################
    #       job preparation phase       #
    #####################################
    msg = "tmp_work_path = {}\n\n{}".format(
        env.tmp_work_path, yaml.dump(job_args, default_flow_style=False).rstrip())
    rich_print(
        Panel.fit(
            msg,
            title="[orange_red1]job preparation phase[/orange_red1]",
            border_style="orange_red1",
        )
    )

    print("Submit tasks to multiprocessingPool : start ...")

    if "replica_start_number" in job_args:
        if isinstance(job_args["replica_start_number"], list):
            env.replica_start_number = list(
                int(x) for x in job_args["replica_start_number"]
            )
        else:
            env.replica_start_number = int(job_args["replica_start_number"])
    else:
        env.replica_start_number = 1

    if env.is_ensemble is True:
        for index, task_label in enumerate(env.sweepdir_items):
            if isinstance(env.replica_start_number, list):
                replica_start_number = env.replica_start_number[index]
            else:
                replica_start_number = env.replica_start_number

            POOL.add_task(
                func=job_preparation,
                func_args=dict(
                    is_ensemble=env.is_ensemble,
                    label=task_label,
                    replica_start_number=replica_start_number,
                ),
            )
    else:
        job_args["replica_start_number"] = env.replica_start_number
        POOL.add_task(func=job_preparation, func_args=job_args)

    print("Submit tasks to multiprocessingPool : done ...")
    job_scripts_to_submit = POOL.wait_for_tasks()

    if prepare_only:
        return job_scripts_to_submit

    #####################################
    #       job transmission phase      #
    #####################################
    msg = (
        "Copy all generated files/folder from\n"
        "tmp_work_path = {}\n"
        "to\n"
        "work_path = {}".format(env.tmp_work_path, env.work_path)
    )
    rich_print(
        Panel.fit(
            msg,
            title="[orange_red1]job transmission phase[/orange_red1]",
            border_style="orange_red1",
        )
    )
    job_transmission()

    if not (hasattr(env, "TestOnly") and env.TestOnly.lower() == "true"):
        # DO NOT submit any job
        # env.submit_job is False in case of using PilotJob option
        # therefore, DO NOT submit the job directly, only submit PJ script
        if not (
            hasattr(env, "submit_job")
            and isinstance(env.submit_job, bool)
            and env.submit_job is False
        ):
            #####################################
            #       job submission phase      #
            #####################################
            msg = "Submit all generated job scripts to target remote machine"
            rich_print(
                Panel.fit(
                    msg,
                    title="[orange_red1]job submission phase[/orange_red1]",
                    border_style="orange_red1",
                )
            )
            for job_script in job_scripts_to_submit:
                job_submission(dict(job_script=job_script))


    #####################################
    #       Fetching result phase       #
    #####################################
    msg = (
        "All jobs are submitted to {}\n"
        "Use:\n\n"
        "   [bright_yellow]fabsim {} fetch_results[/bright_yellow]\n\n"
        "to copy the results back to localhost\n\n"
        "Please make sure, all submitted jobs are finished on remote "
        "machine before calling fetch_results command".format(env.machine_name,env.machine_name)
    )
    rich_print(
        Panel.fit(
            msg,
            title="[orange_red1]Fetching result[/orange_red1]",
            border_style="orange_red1",
        )
    )

    # POOL.shutdown_threads()
    return job_scripts_to_submit


def job_preparation(job_args: dict):
    """
    here, all job folders and scripts will be created in the temporary folder
        `<tmp_folder>/{results,scripts}`, later, in job_transmission,
    we transfer all these files and folders with a single `rsync` command.
    This approach will helps us to reduce the number of SSH connection and
    improve the stability of job submission workflow which can be compromised
    by high parallel SSH connection
    """


    if "label" in job_args:
        env.label = job_args["label"]
    else:
        env.label = ""

    return_job_scripts = []

    for i in range(
        job_args["replica_start_number"],
        int(env.replicas) + job_args["replica_start_number"],
    ):
        env.replica_number = i

        env.job_results, env.job_results_local = job_manager.generate_job_with_template(
            is_ensemble=env.is_ensemble, job_label=env.label
        )

        if int(env.replicas) > 1:
            if env.is_ensemble is False:
                env.job_results += "_replica_" + str(i)
            else:
                env.job_results += "_" + str(i)

        tmp_job_results = env.job_results.replace(
            env.results_path, env.tmp_results_path
        )

        env["job_name"] = env.name[0: env.max_job_name_chars]
        # remote_machines.complete_environment()
        env.complete_environment()

        env.run_command = template(env.run_command)

        if env.label not in ["PJ_PYheader", "PJ_header"]:
            env.run_prefix += (
                "\n\n"
                "# copy files from config folder\n"
                "config_dir={}\n"
                "rsync -pthrvz --inplace --exclude SWEEP "
                "$config_dir/* .".format(env.job_config_path)
            )

        if env.is_ensemble:
            env.run_prefix += (
                "\n\n"
                "# copy files from SWEEP folder\n"
                "rsync -pthrvz --inplace $config_dir/SWEEP/{}/ .".format(
                    env.label
                )
            )

        if not (hasattr(env, "venv") and str(env.venv).lower() == "true"):
            if hasattr(env, "py_pkg") and len(env.py_pkg) > 0:
                env.run_prefix += (
                    "\n\n"
                    "# Install requested python packages\n"
                    "pip3 install --user --upgrade {}".format(
                        " ".join(pkg for pkg in env.py_pkg)
                    )
                )

        # this is a tricky situation,
        # in case of ensemble runs, or simple job, we need to add env.label
        # to generated job script name,
        # however, for PJ_PYheader and PJ_header header script, nothing should
        # be added at the end of script file name, so, here we pass a empty
        # string as label
        if hasattr(env, "NoEnvScript") and env.NoEnvScript:
            tmp_job_script = script_templates(env.batch_header)
        else:
            tmp_job_script = script_templates(env.batch_header, env.script)

        # Separate base from extension
        base, extension = os.path.splitext(env.pather.basename(tmp_job_script))
        # Initial new name if we have replicas or ensemble

        if int(env.replicas) > 1:
            if env.is_ensemble is False:
                dst_script_name = base + "_replica_" + str(i) + extension
            else:
                dst_script_name = base + "_" + str(i) + extension
        else:
            dst_script_name = base + extension

        dst_job_script = env.pather.join(env.tmp_scripts_path, dst_script_name)

        # Add target job script to return list

        """
        return_job_scripts.append(env.pather.join(env.scripts_path,
                                               dst_script_name)
        """
        # here, instead of returning PATH to script folder, it is better to
        # submit script from results_path folder, specially in case of PJ job
        return_job_scripts.append(
            env.pather.join(env.job_results, dst_script_name)
        )

        copy(tmp_job_script, dst_job_script)
        # chmod +x dst_job_script
        # 755 means read and execute access for everyone and also
        # write access for the owner of the file
        os.chmod(dst_job_script, 0o755)

        os.makedirs(tmp_job_results, exist_ok=True)
        copy(dst_job_script, env.pather.join(tmp_job_results, dst_script_name))

        # TODO: these env variables are not used anywhere
        # TODO: maybe it is better to remove them
        # job_name_template_sh
        # job_results_contents
        # job_results_contents_local
        with open(
            env.pather.join(tmp_job_results, "env.yml"
                            ), "w") as env_yml_file:
            yaml.dump(
                dict(
                    env,
                    **{
                        "sshpass": None,
                        "passwords": None,
                        "password": None,
                        "sweepdir_items": None,
                    },
                ),
                env_yml_file,
                default_flow_style=False,
            )

    return return_job_scripts


def job_transmission():
    """
    here, we only transfer all generated files/folders from

    `<tmp_folder>/{results,scripts}`

    to

    `<target_work_dir>/{results,scripts}`
    """

    if (
        hasattr(env, "prevent_results_overwrite")
        and env.prevent_results_overwrite == "delete"
    ):
        # if we have a large result directory contains thousands of files and
        # folders, using rm command will not be efficient,
        # so, here I am using rsync
        #
        # Note: there is another option, using perl which is much faster than
        #       rsync -a --delete, but I am not sure if we can use it on
        #       all HPC resources
        empty_folder = "/tmp/{}".format(next(tempfile._get_candidate_names()))
        results_dir_items = os.listdir(env.tmp_results_path)
        for results_dir_item in results_dir_items:
            print("empty folder: ", empty_folder)
            print("results_dir_item: ", results_dir_item)
            if env.ssh_monsoon_mode:
                task_string = template(
                    "mkdir -p {} && "
                    "mkdir -p {}/results/{} && "
                    "rm -rf {}/results/{}/*".format(
                        empty_folder,
                        env.work_path,
                        results_dir_item,
                        env.work_path,
                        results_dir_item,
                    )
                )

                cmd_runner.run(
                    template(
                        "{} ; ssh $remote_compute -C"
                        "'{}'".format(
                            task_string,
                            task_string,
                        )
                    )
                )

            else:
                cmd_runner.run(
                    template(
                        "mkdir -p {} && "
                        "mkdir -p {}/results &&"
                        "rsync -a --delete --inplace {}/ "
                        "{}/results/{}/".format(
                            empty_folder,
                            env.work_path,
                            empty_folder,
                            env.work_path,
                            results_dir_item,
                        )
                    )
                )

    rsyc_src_dst_folders = []
    rsyc_src_dst_folders.append((env.tmp_scripts_path, env.scripts_path))
    rsyc_src_dst_folders.append((env.tmp_results_path, env.results_path))

    for sync_src, sync_dst in rsyc_src_dst_folders:
        if env.ssh_monsoon_mode:
            # local(
            #    template(
            #        "scp -r "
            #        "{}/* $username@$remote:{}/ ".format(sync_src, sync_dst)
            #    )
            # )
            # scp a monsoonfab:~/ ; ssh monsoonfab -C “scp ~/a xcscfab:~/”
            cmd_runner.local(
                template(
                    "ssh $remote -C "
                    "'mkdir -p {}' && "
                    "scp -r {} "
                    "$username@$remote:{}/../ && "
                    "ssh $remote -C "
                    "'scp -r {} "
                    "$remote_compute:{}/../'".format(
                        sync_dst,
                        sync_src,
                        sync_dst,
                        sync_dst,
                        sync_dst,
                    )
                )
            )
        elif env.manual_sshpass:
            sshpass_args = "-e" if env.env_sshpass else "-f $sshpass"
            # TODO: maybe the better option here is to overwrite the
            #       rsync_project
            cmd_runner.local(
                template(
                    "rsync -pthrvz "
                    f"--rsh='sshpass {sshpass_args} ssh  -p 22  ' "
                    "{}/ $username@$remote:{}/ ".format(sync_src, sync_dst)
                )
            )
        elif env.manual_gsissh:
            # TODO: implement prevent_results_overwrite for this option
            cmd_runner.local(
                template(
                    "globus-url-copy -p 10 -cd -r -sync "
                    "file://{}/ "
                    "gsiftp://$remote/{}/".format(sync_src, sync_dst)
                )
            )
        else:
            cmd_runner.rsync_project(local_dir=sync_src + "/", remote_dir=sync_dst)


def job_submission(job_args : dict):
    """
    here, all prepared job scrips will be submitted to the
    target remote machine

    !!! note
        please make sure to pass the list of job scripts be summited as
        an input to this function
    """

    job_script = job_args["job_script"]

    if (
        hasattr(env, "dispatch_jobs_on_localhost")
        and isinstance(env.dispatch_jobs_on_localhost, bool)
        and env.dispatch_jobs_on_localhost
    ):
        cmd_runner.local(template("$job_dispatch " + job_script))
        print("job dispatch is done locally\n")

    elif not env.get("noexec", False):
        if env.dry_run:
            if env.host == "localhost":
                print("Dry run")
                subprocess.call(["cat", job_script])
            else:
                print("Dry run available only on localhost")
            exit()

        elif env.remote == "localhost":
            cmd_runner.run(
                cmd="{} && {}".format(
                    env.run_prefix,
                    template("$job_dispatch {}".format(job_script)),
                ),
                cd=env.pather.dirname(job_script),
            )
        elif env.ssh_monsoon_mode:
            cmd = template(
                "ssh $remote_compute " "-C '$job_dispatch {}'".format(
                    job_script
                ),
                # Allow for variable references in job_dispatch definition
                number_of_iterations=2,
            )
            cmd_runner.run(cmd, cd=env.pather.dirname(job_script))
        else:
            cmd_runner.run(
                cmd=template(
                    "$job_dispatch {}".format(job_script),
                    # Allow for variable references in job_dispatch definition
                    number_of_iterations=2,
                ),
                cd=env.pather.dirname(job_script),
            )

    return [job_script]


@task
@beartype
def ensemble2campaign(
    results_dir: str, campaign_dir: str, skip: Optional[Union[int, str]] = 0
) -> None:
    """
    Converts FabSim3 ensemble results to EasyVVUQ campaign definition.
    results_dir: FabSim3 results root directory
    campaign_dir: EasyVVUQ root campaign directory.
    skip: The number of runs (run_1 to run_skip) not to copy to the campaign
    """
    # update_environment(args)
    # if skip > 0: only copy the run directories run_X for X > skip back
    # to the EasyVVUQ campaign dir
    if int(skip) > 0:
        # all run directories
        runs = os.listdir("{}/RUNS/".format(results_dir))
        for run in runs:
            # extract X from run_X
            run_id = int(run.split("_")[-1])
            # if X > skip copy results back
            if run_id > int(skip):
                cmd_runner.local(
                    "rsync -pthrvz {}/RUNS/{} {}/runs".format(
                        results_dir, run, campaign_dir
                    )
                )
    # copy all runs from FabSim results directory to campaign directory
    else:
        cmd_runner.local("rsync -pthrvz {}/RUNS/ {}/runs".format(
            results_dir, campaign_dir)
        )


@task
@beartype
def campaign2ensemble(
    config: str, campaign_dir: str, skip: Optional[Union[int, str]] = 0
) -> None:
    """
    Converts an EasyVVUQ campaign run set TO a FabSim3 ensemble definition.

    Args:
        config (str): FabSim3 configuration name (will create in top level if
            non-existent, and overwrite existing content).
        campaign_dir (str): EasyVVUQ root campaign directory
        skip (Union[int, str], optional): The number of runs(run_1 to run_skip)
            not to copy to the FabSim3 sweep directory. The first skip number
            of samples will then not be computed.
    """
    # update_environment(args)
    try:
        config_path = job_manager.get_config_file_path(config)
    except FabSimError.FileNotFoundError:
        config_path = os.path.join(env.local_config_file_path[-1], config)
        cmd_runner.local("mkdir -p {}".format(config_path))

    sweep_dir = os.path.join(config_path,"SWEEP")
    cmd_runner.local("mkdir -p {}".format(sweep_dir))

    cmd_runner.local("rm -rf {}{}*".format(sweep_dir,os.sep))

    # if skip > 0: only copy the run directories run_X for X > skip to the
    # FabSim3 sweep directory. This avoids recomputing already computed samples
    # when the EasyVVUQ grid is refined adaptively.
    if int(skip) > 0:
        # all runs in the campaign dir
        runs = os.listdir("{}/runs/".format(campaign_dir))

        for run in runs:
            # extract X from run_X
            run_id = int(run.split("_")[-1])
            # if X > skip, copy run directory to the sweep dir
            if run_id > int(skip):
                print("Copying {}".format(run))
                cmd_runner.local("rsync -pthrz {}/runs/{} {}".format(
                    campaign_dir, run, sweep_dir
                    )
                )
    # if skip = 0: copy all runs from EasyVVUQ run directort to the sweep dir
    else:
        cmd_runner.local("rsync -pthrz {}/runs/ {}".format(campaign_dir, sweep_dir))


@beartype
def run_ensemble(
    config: str,
    sweep_dir: str,
    sweep_on_remote: Optional[bool] = False,
    execute_put_configs: Optional[bool] = True,
    upsample: str = "",
    replica_start_number: str = "1",
    **args,
) -> None:
    """
    Map and execute ensemble jobs.
    The job results will be stored with a name pattern as defined in
    the environment

    !!! note
        function `with_config` should be called before calling this function in
        plugin code.

    Args:
        config (str): base config directory to use to define input files
        sweep_dir (str): directory containing inputs that will vary per
            ensemble simulation instance.
        sweep_on_remote (bool, optional): value `True` means the `SWEEP`
            directory is located to the remote machine.
        execute_put_configs (bool, optional): `True` means we already called
            `put_configs` function to transfer `config` files and folders to
            remote machine.
        **args: Description

    Raises:
        RuntimeError: - if `with_config` function did not called before calling
                `run_ensemble` task.
            - if `env.script` variable did not set.
            - if `SWEEP` directory is empty.

    """
    # env.updateEnvironment(args)
    env.update(args)

    if ";" in replica_start_number:
        raise NotImplementedError.NotImplementedError(
            "Multiple replica_start_numbers are not yet implemented for users."
        )

    if "script" not in env:
        raise FabSimError.RuntimeError(
            "ERROR: run_ensemble function has been called,"
            "but the parameter 'script' was not specified."
        )

    # check if with_config function is already called
    if not hasattr(env, "job_config_path"):
        raise FabSimError.RuntimeError(
            "Function with_config did NOT called, "
            "Please call it before calling run_ensemble()"
        )

    # check for PilotJob option
    if hasattr(env, "PJ") and env.PJ.lower() == "true":
        env.submitted_jobs_list = []
        env.submit_job = False
        env.batch_header = "bash_header"

    if sweep_on_remote is False:
        sweepdir_items = os.listdir(sweep_dir)
        if len(upsample) > 0:
            upsample = upsample.split(";")

            folder_name = f"{env.config}_{env.machine_name}_{env.cores}"
            path = os.path.join(env.results_path, folder_name, "RUNS")

            replica_start_number = list(
                count_folders(path, dir) + 1 for dir in upsample
            )

            if set(upsample).issubset(set(sweepdir_items)):
                sweepdir_items = upsample
            else:
                error = "ERROR: upsample item: "
                error += f"{set(upsample)-set(sweepdir_items)}"
                error += "not found in SWEEP folder"
                raise FabSimError.RuntimeError(error)
    else:
        # in case of reading SWEEP folder from remote machine, we need a
        # SSH tunnel and then list the directories
        sweepdir_items = cmd_runner.run("ls -1 {}".format(sweep_dir)).splitlines()
    print("reading SWEEP folder from remote machine")
    if len(sweepdir_items) == 0:
        raise FabSimError.RuntimeError(
            "ERROR: no files where found in the sweep_dir : {}".format(
                sweep_dir
            )
        )

    # reorder an exec_first item for priority execution.
    if hasattr(env, "exec_first"):
        sweepdir_items.insert(
            0, sweepdir_items.pop(sweepdir_items.index(env.exec_first))
        )

    if execute_put_configs is True:
        job_manager.transfer_config_files(config)
        # execute(put_configs, config)


    # output['everything'] = False
    # job_scripts_to_submit = job(
    #     dict(
    #         is_ensemble=True,
    #         sweepdir_items=sweepdir_items,
    #         sweep_dir=sweep_dir,
    #         replica_start_number=replica_start_number,
    #     ),
    #     prepare_only=True,
    # )


    if hasattr(env, "PJ_TYPE"):
        pj_type = env.PJ_TYPE.lower()
        if pj_type == "rp":
            run_radical(job_scripts_to_submit, env.get("venv", False))
        elif pj_type == "qcg":
            run_qcg(job_scripts_to_submit, env.get("venv", False))
        else:
            print("Error: 'PJ_TYPE' must be set to 'RP' or 'QCG'. Exiting...")
            sys.exit(1)
    else:
        # If PJ_TYPE is not set, submit the jobs normally
        job_scripts_to_submit = job(
            dict(
                is_ensemble=True,
                sweepdir_items=sweepdir_items,
                sweep_dir=sweep_dir,
                replica_start_number=replica_start_number,
            ),
            prepare_only=False,
        )


def run_radical(job_scripts_to_submit: list, venv="False"):
    rich_print(
        Panel.fit(
            "NOW, we are submitting RADICAL-Pilot Jobs",
            title="[orange_red1]PJ job submission phase[/orange_red1]",
            border_style="orange_red1",
        )
    )

    # Set task model to default
    if not hasattr(env, "task_model"):
        env.task_model = "default"

    # Create a temprary working directory for Radical runtime files
    local_working_dir = path.join(
        env.tmp_results_path, "radical_{}_{}_{}".format(
            env.config, env.machine_name, env.cores
        )
    )
    remote_working_dir = path.join(
        env.results_path, "radical_{}_{}_{}".format(
            env.config, env.machine_name, env.cores
        )
    )
    os.makedirs(local_working_dir, exist_ok=True)

    # Prepare the environment for Radical TaskDescription
    task_descriptions = []
    for index, task_script in enumerate(job_scripts_to_submit, start=1):
        env.update(
            {
                "task_name": f"{env.get('task_name_prefix', 'task')}.{index}",
                "executable": task_script,
            }
        )
        task_descriptions.append(task_script)

    # Prepare the environment for Radical pd_init
    env.update(
        {
            "task_descriptions": task_descriptions,
            "sandbox": remote_working_dir,
        }
    )

    # Locate and copy the radical resources script to the sandbox directory
    radical_resources_content = script_template_content("radical-resources")
    sandbox_resources_path = path.join(
        local_working_dir, ".radical", "pilot", "configs"
    )
    os.makedirs(sandbox_resources_path, exist_ok=True)
    with open(
        path.join(sandbox_resources_path, "resource_fabsim.json"), "w"
    ) as f:
        f.write(radical_resources_content)

    # Generate the radical-PJ-py script using the template
    radical_script_content = script_template_content("radical-PJ-py")
    radical_script_name = "{}_{}_{}_radical.py".format(
        env.config, env.machine_name, env.cores
    )
    radical_local_script_path = path.join(
        local_working_dir, radical_script_name
    )
    radical_remote_script_path = path.join(
        remote_working_dir, radical_script_name
    )

    # Create a temporary local file with the radical script content
    with open(radical_local_script_path, "w") as f:
        f.write(radical_script_content)

    # Transfer Radical configuration script to remote machine
    cmd_runner.local(
        template(
            "rsync -pthrvz {}/ $username@$remote:{}/".format(
                local_working_dir, remote_working_dir
            )
        )
    )

    # Construct the run_Radical_PilotJob command
    RP_CMD = []
    if hasattr(env, "venv") and str(env.venv).lower() == "true":
        RP_CMD.append("# Activate the virtual environment")
        RP_CMD.append(f"source {env.virtual_env_path}/bin/activate\n")

    RP_CMD.append("# Check if Job is installed")
    RP_CMD.append(
        "python3 -c 'import radical.pilot' 2>/dev/null || "
        "pip3 install --upgrade radical.pilot\n"
    )
    RP_CMD.append("# Python command for task submission")
    RP_CMD.append(f"python3 {radical_remote_script_path}\n")

    env.run_Radical_PilotJob = "\n".join(RP_CMD)

    # Avoid apply replicas functionality on PilotJob folders
    env.replicas = "1"
    backup_header = env.batch_header
    env.batch_header = env.radical_PJ_header
    env.submit_job = True

    job(dict(is_ensemble=False, label="radical-PJ-header", NoEnvScript=True))
    env.batch_header = backup_header
    env.NoEnvScript = False


def run_qcg(job_scripts_to_submit: list, venv: bool):
    rich_print(
        Panel.fit(
            "NOW, we are submitting QCG Pilot jobs",
            title="[orange_red1]PJ job submission phase[/orange_red1]",
            border_style="orange_red1",
        )
    )

    # first, add all generated tasks script to PJ_PY
    submitted_jobs_list = []
    if not hasattr(env, "task_model"):
        env.task_model = "default"

    # Python's indexes start at zero, to start from 1, set start=1
    for index, job_script in enumerate(job_scripts_to_submit, start=1):
        env.idsID = index
        env.idsPath = job_script
        env.dirPath = path.dirname(env.idsPath)
        submitted_jobs_list.append(
            script_template_content("qcg-PJ-task-template")
        )
    env.submitted_jobs_list = "\n".join(submitted_jobs_list)

    # Avoid apply replicas functionality on PilotJob folders
    env.replicas = "1"
    backup_header = env.batch_header
    env.batch_header = env.PJ_PYheader
    job_scripts_to_submit = job(
        dict(
            is_ensemble=False, label="PJ_PYheader", NoEnvScript=True
        )
    )

    env.PJ_PATH = job_scripts_to_submit[0]
    env.PJ_FileName = env.pather.basename(env.PJ_PATH)
    env.batch_header = env.PJ_header
    env.submit_job = True

    # Construct the run_QCG_PilotJob command
    PJ_CMD = []
    if hasattr(env, "venv") and str(env.venv).lower() == "true":
        # QCG-PJ should load from virtualenv
        PJ_CMD.append("# Activate the virtual environment")
        PJ_CMD.append(f"source {env.virtual_env_path}/bin/activate\n")

    PJ_CMD.append("# Check if qcg-pilotjob is installed")
    PJ_CMD.append(
        "python3 -c 'import qcg-pilotjob' 2>/dev/null || "
        "pip3 install --upgrade qcg-pilotjob\n"
    )
    PJ_CMD.append("# Python command for qcg-pilotjob execution")
    PJ_CMD.append(f"python3 {env.PJ_PATH}")

    env.run_QCG_PilotJob = "\n".join(PJ_CMD)
    job(dict(is_ensemble=False, label="PJ_header", NoEnvScript=True))
    env.batch_header = backup_header
    env.NoEnvScript = False


def input_to_range(arg, default):
    ttype = type(default)
    # regexp for a array generator like [1.2:3:0.2]
    gen_regexp = r"\[([\d\.]+):([\d\.]+):([\d\.]+)\]"
    if not arg:
        return [default]
    match = re.match(gen_regexp, str(arg))
    if match:
        vals = list(map(ttype, match.groups()))
        if ttype == int:
            return range(*vals)
        else:
            return np.arange(*vals)
    return [ttype(arg)]


@task
def install_packages(venv: bool = "False"):
    """
    Install list of packages defined in deploy/applications.yml

    !!! note
        if you got an error on your local machine during the build wheel
        for scipy, like this one
            ```sh
            ERROR: lapack_opt_info:
            ```
        Try to install BLAS and LAPACK first. by
            ```sh
            sudo apt-get install libblas-dev
            sudo apt-get install liblapack-dev
            sudo apt-get install libatlas-base-dev
            sudo apt-get install gfortran
            ```

    Args:
        venv (str, optional): `True` means the VirtualEnv is already installed
            in the remote machine
    """
    applications_yml_file = os.path.join(
        env.fabsim_root, "deploy", "applications.yml"
    )
    user_applications_yml_file = os.path.join(
        env.fabsim_root, "deploy", "applications_user.yml"
    )
    if not os.path.exists(user_applications_yml_file):
        copyfile(applications_yml_file, user_applications_yml_file)

    config = yaml.load(
        open(user_applications_yml_file), Loader=yaml.SafeLoader
    )

    tmp_app_dir = "{}/tmp_app".format(env.localroot)
    cmd_runner.local("mkdir -p {}".format(tmp_app_dir))

    for dep in config["packages"]:
        cmd_runner.local("pip3 download --no-binary=:all: -d {} {}".format(
                tmp_app_dir, dep
            )
        )
    add_dep_list_compressed = sorted(
        Path(tmp_app_dir).iterdir(), key=lambda f: f.stat().st_mtime
    )
    for it in range(len(add_dep_list_compressed)):
        add_dep_list_compressed[it] = os.path.basename(
            add_dep_list_compressed[it]
        )

    # Create  directory in the remote machine to store dependency packages
    cmd_runner.run(template("mkdir -p {}".format(env.app_repository)))

    # Send the dependencies (and the dependencies of dependencies) to the
    # remote machine
    for whl in os.listdir(tmp_app_dir):
        cmd_runner.local(
            template(
                "rsync -pthrvz -e 'ssh -p $port'  {}/{} "
                "$username@$remote:$app_repository".format(
                    tmp_app_dir, whl
                )
            )
            # "rsync -pthrvz %s/%s eagle:$app_repository"%(tmp_app_dir, whl)
        )

    # Set required env variable
    env.config = "Install_VECMA_App"
    # env.nodes = 1
    env.nodes = env.cores
    script = os.path.join(tmp_app_dir, "script")
    # Write the Install command in a file
    with open(script, "w") as sc:
        install_dir = "--user"
        if venv.lower() == "true":
            sc.write(
                "if [ ! -d {} ]; then \n\t python -m virtualenv "
                "{} || echo 'WARNING : virtualenv is not installed "
                "or has a problem' \nfi\n\nsource {}/bin/activate\n".format(
                    env.virtual_env_path,
                    env.virtual_env_path,
                    env.virtual_env_path,
                )
            )
            install_dir = ""

        # First install the additional_dependencies
        for dep in reversed(add_dep_list_compressed):
            print(dep)
            if dep.endswith(".zip"):
                sc.write(
                    "\nunzip {}/{} -d {} && cd {}/{} "
                    "&& python3 setup.py install {}".format(
                        env.app_repository,
                        dep,
                        env.app_repository,
                        env.app_repository,
                        dep.replace(".zip", ""),
                        install_dir,
                    )
                )
            elif dep.endswith(".tar.gz"):
                sc.write(
                    "\ntar xf {}/{} -C {} && cd {}/{} "
                    "&& python3 setup.py install {}\n".format(
                        env.app_repository,
                        dep,
                        env.app_repository,
                        env.app_repository,
                        dep.replace(".tar.gz", ""),
                        install_dir,
                    )
                )

    # Add the tmp_app_dir directory in the local templates path because the
    # script is saved in it
    env.local_templates_path.insert(0, tmp_app_dir)

    install_dict = dict(script="script")
    # env.script = "script"
    # env.updateEnvironment(install_dict)
    env.update(install_dict)

    # Determine a generated job name from environment parameters
    # and then define additional environment parameters based on it.
    env.job_results, env.job_results_local = job_manager.generate_job_with_template()

    # Create job script based on "sbatch header" and script created above in
    # deploy/.jobscript/
    env.job_script = script_templates(env.batch_header_install_app, env.script)

    # Create script's destination path to remote machine based on
    env.dest_name = env.pather.join(
        env.scripts_path, env.pather.basename(env.job_script)
    )

    # Send Install script to remote machine
    cmd_runner.put(env.job_script, env.dest_name)
    #
    cmd_runner.run(template("mkdir -p $job_results"))
    with cd(env.pather.dirname(env.job_results)):
        cmd_runner.run(template("{} {}".format(env.job_dispatch, env.dest_name)))

    cmd_runner.local("rm -rf {}".format(tmp_app_dir))


@task
def install_app(name="", external_connexion="no", venv="False"):
    """
    Install a specific Application through FasbSim3

    """
    applications_yml_file = os.path.join(
        env.fabsim_root, "deploy", "applications.yml"
    )
    user_applications_yml_file = os.path.join(
        env.fabsim_root, "deploy", "applications_user.yml"
    )
    if not os.path.exists(user_applications_yml_file):
        copyfile(applications_yml_file, user_applications_yml_file)

    config = yaml.load(
        open(user_applications_yml_file), Loader=yaml.SafeLoader
    )
    info = config[name]

    # Offline cluster installation - --user install
    # Temporary folder
    tmp_app_dir = "{}/tmp_app".format(env.localroot)
    cmd_runner.local("mkdir -p {}".format(tmp_app_dir))

    # First download all the Miniconda3 installation script
    cmd_runner.local(
        "wget {} -O {}/miniconda.sh".format(
            config["Miniconda-installer"]["repository"], tmp_app_dir
        )
    )

    # Install app-specific requirements

    if name == "RADICAL-Pilot":
        cmd_runner.local("pip3 install radical.pilot")

    if name == "QCG-PilotJob":
        cmd_runner.local("pip3 install -r " + env.localroot + "/qcg_requirements.txt")

    # Next download all the additional dependencies
    for dep in info["additional_dependencies"]:
        cmd_runner.local("pip3 download --no-binary=:all: -d {} {}".format(
            tmp_app_dir, dep
            )
        )
    add_dep_list_compressed = sorted(
        Path(tmp_app_dir).iterdir(), key=lambda f: f.stat().st_mtime
    )
    for it in range(len(add_dep_list_compressed)):
        add_dep_list_compressed[it] = os.path.basename(
            add_dep_list_compressed[it]
        )

    # Download all the dependencies of the application
    # This first method should download all the dependencies needed
    # but for the local plateform !
    # --> Possible Issue during the installation in the remote
    # (it's not a cross-plateform install yet)
    cmd_runner.local(
        "pip3 download --no-binary=:all: -d {} git+{}@v{}".format(
            tmp_app_dir, info["repository"], info["version"]
        )
    )

    # Create  directory in the remote machine to store dependency packages
    cmd_runner.run(template("mkdir -p {}".format(env.app_repository)))
    # Send the dependencies (and the dependencies of dependencies) to the
    # remote machine
    for whl in os.listdir(tmp_app_dir):
        cmd_runner.local(
            template(
                "rsync -pthrvz -e 'ssh -p $port'  {}/{} "
                "$username@$remote:$app_repository".format(tmp_app_dir, whl)
            )
        )

    # Set required env variable
    env.config = "Install_VECMA_App"
    # env.nodes = 1
    env.nodes = env.cores
    script = os.path.join(tmp_app_dir, "script")
    # Write the Install command in a file
    with open(script, "w") as sc:
        install_dir = ""
        if venv == "True":
            # clean virtualenv and App_repo directory on remote machine side
            # To make sure everything is going to be installed from scratch
            """
            sc.write("find %s/ -maxdepth 1 -mindepth 1 -type d \
                -exec rm -rf \"{}\" \\;\n" % (env.app_repository))
            sc.write("rm -rf %s\n" % (env.virtual_env_path))
            """

            # It seems some version of python/virtualenv doesn't support
            # the option --no-download. So there is sometime a problem :
            # from pip import main
            # ImportError: cannot import name 'main'
            #
            # TODO Check python version and raised a Warning if not the
            # right version ?
            # TODO
            #
            sc.write(
                "if [ ! -d {} ]; then \n\t bash {}/miniconda.sh -b -p {} "
                "|| echo 'WARNING : virtualenv is not installed "
                "or has a problem' \nfi".format(
                    env.virtual_env_path,
                    env.app_repository,
                    env.virtual_env_path,
                )
            )
            sc.write(
                '\n\neval "$$({}/bin/conda shell.bash hook)"\n\n'.format(
                    env.virtual_env_path
                )
            )
            # install_dir = ""
            """
            with the latest version of numpy, I got this error:
            1. Check that you expected to use Python3.8 from ...,
                and that you have no directories in your PATH or PYTHONPATH
                that can interfere with the Python and numpy version "1.18.1"
                you're trying to use.
            so, since that we are using VirtualEnv, to avoid any conflict,
            it is better to clear PYTHONPATH
            """
            # sc.write("\nexport PYTHONPATH=\"\"\n")
            sc.write("\nmodule unload python\n")

        # First install the additional_dependencies
        for dep in reversed(add_dep_list_compressed):
            print(dep)
            if dep.endswith(".zip"):
                sc.write(
                    "\nunzip {}/{} -d {} && cd {}/{} "
                    "&& {}/bin/python3 setup.py install {}\n".format(
                        env.app_repository,
                        dep,
                        env.app_repository,
                        env.app_repository,
                        dep.replace(".zip", ""),
                        env.virtual_env_path,
                        install_dir,
                    )
                )
            elif dep.endswith(".tar.gz"):
                sc.write(
                    "\ntar xf {}/{} -C {} && cd {}/{} "
                    "&& {}/bin/python3 setup.py install {}\n".format(
                        env.app_repository,
                        dep,
                        env.app_repository,
                        env.app_repository,
                        dep.replace(".tar.gz", ""),
                        env.virtual_env_path,
                        install_dir,
                    )
                )

        sc.write(
            "{}/bin/pip install --no-index --no-build-isolation "
            "--find-links=file:{} {}/{}-{}.zip {} || "
            "{}/bin/pip install --no-index "
            "--find-links=file:{} {}/{}-{}.zip".format(
                env.virtual_env_path,
                env.app_repository,
                env.app_repository,
                info["name"],
                info["version"],
                install_dir,
                env.virtual_env_path,
                env.app_repository,
                env.app_repository,
                info["name"],
                info["version"],
            )
        )

    # Add the tmp_app_dir directory in the local templates path because the
    # script is saved in it
    env.local_templates_path.insert(0, tmp_app_dir)

    install_dict = dict(script="script")
    # env.script = "script"
    env.updateEnvironment(install_dict)

    # Determine a generated job name from environment parameters
    # and then define additional environment parameters based on it.
    env.job_results, env.job_results_local = job_manager.generate_job_with_template()

    # Create job script based on "sbatch header" and script created above in
    # deploy/.jobscript/

    env.job_script = script_templates(env.batch_header_install_app, env.script)

    # Create script's destination path to remote machine based on
    cmd_runner.run(template("mkdir -p $scripts_path"))
    env.dest_name = env.pather.join(
        env.scripts_path, env.pather.basename(env.job_script)
    )

    # Send Install script to remote machine
    cmd_runner.put(env.job_script, env.dest_name)
    #
    cmd_runner.run(template("mkdir -p $job_results"))

    env.job_dispatch += " -q standard"

    print(env.job_dispatch)
    print(env.dest_name)

    cmd_runner.run(template("{} {}".format(env.job_dispatch, env.dest_name)))

    cmd_runner.local("rm -rf {}".format(tmp_app_dir))


def count_folders(dir_path: str, prefix: str):
    """
    Count the number of folders in a path that match a pattern
    """
    dirs = os.listdir(dir_path)
    return len([d for d in dirs if d.startswith(prefix)])
