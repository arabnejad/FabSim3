from fabsim.base.error_handler import FabSimError
from beartype import beartype
from beartype.typing import Callable, Optional, Tuple, Union
from rich import print as rich_print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table, box
from math import ceil
import os
from re import findall
from fabsim.base.environment_manager import env
from fabsim.base.command_runner import cmd_runner
from fabsim.deploy.templates import (
    script_template_content,
    script_templates,
    template,
)
import tempfile
from shutil import copy, copyfile, rmtree
from fabsim.base.MultiProcessingPool import MultiProcessingPool
import yaml
import subprocess

class JobManager():
    def __init__(self):
        pass


    @beartype
    def fetch_results(self,
        name: Optional[str] = "",
        regex: Optional[str] = "",
        files: Optional[str] = None,
    ) -> None:
        """
        Fetch results of remote jobs to local result store. Specify a job
        name to transfer just one job. Local path to store results is
        specified in machines_user.json, and should normally point to a
        mount on entropy, i.e. /store4/blood/username/results.
        If you can't mount entropy, `put results` can be useful, via
        `fab legion fetch_results`

        Args:
            name (str, optional): the job name, it no name provided, all
                directories from `fabric_dir` will be fetched
            regex (str, optional): the matching pattern
            files (str, optional): the list of files need to fetched from the
                remote machine. The list of file should be passed as string, and
                split by `;`. For example, to fetch only `out.csv` and `env.yml`
                files, you should pass `files="out.csv;env.yml" to this function.
        """
        fetch_files = []
        if files is not None:
            fetch_files = files.split(";")
        includes_files = ""
        if len(fetch_files) > 0:
            includes_files = " ".join(
                [
                    *["--include='*/' "],
                    *["--include='{}' ".format(file) for file in fetch_files],
                    *["--exclude='*'  "],
                    *["--prune-empty-dirs "],
                ]
            )

        env.job_results, env.job_results_local = self.configure_job_paths(name)

        # check if the local results directory exists or not
        if not os.path.isdir(env.job_results_local):
            os.makedirs(env.job_results_local)

        if env.manual_sshpass:
            sshpass_args = "-e" if env.env_sshpass else "-f $sshpass"
            cmd_runner.local(
                template(
                    "rsync -pthrvz -e 'sshpass {} ssh -p $port' {}"
                    "$username@$remote:$job_results/{}  "
                    "$job_results_local".format(
                        sshpass_args, includes_files, regex
                    )
                )
            )
        elif env.manual_gsissh:
            cmd_runner.local(
                template(
                    "globus-url-copy -cd -r -sync {}"
                    "gsiftp://$remote/$job_results/{} "
                    "file://$job_results_local/".format(includes_files, regex)
                )
            )
        else:
            cmd_runner.local(
                template(
                    "rsync -pthrvz -e 'ssh -p $port' {}"
                    "$username@$remote:$job_results/{} "
                    "$job_results_local".format(includes_files, regex)
                )
            )

    @beartype
    def get_config_file_path(self, config_name: str) -> str:
        """
        Find the config file path

        Args:
            name (str): Description
            ExceptWhenNotFound (bool, optional): Description

        Returns:
            Union[bool, str]: - `False`: if the input config name not found
            - the path of input config name
        """
        for path in env.local_config_file_path:
            config_file_path = os.path.join(path, config_name)
            if os.path.exists(config_file_path):
                return config_file_path

        raise FabSimError.FileNotFoundError(
            f"Error: Config file '{config_name}' not found in: {env.local_config_file_path}"
        )

    @beartype
    def set_config(self, config_dir: str):
        """
        Internal: augment the fabric environment with information
        regarding a particular configuration dir name.

        Definitions created:

        - `job_config_path`: the remote location where the config files for the
                job should be stored
        - `job_config_path_local`: the local location where the config files for
                the job may be found

        Args:
            name (str): the name of config directory
        """
        env.config = config_dir
        env.job_config_path = os.path.join(env.config_path, f"{env.config}{env.job_desc}")

        config_files_path = job_manager.get_config_file_path(env.config)

        env.job_config_path_local = os.path.join(config_files_path)
        env.job_config_contents = os.path.join(env.job_config_path, "*")
        env.job_config_contents_local = os.path.join(config_files_path, "*")
        # Define the job's shell submission script template
        env.job_name_template_sh = template(f"{env.job_name_template}.sh")

    def _transfer_config_files_via_scp(self) -> None:
        """
        Transfer files using SCP in monsoon mode.
        """
        # scp a monsoonfab:~/ ; ssh monsoonfab -C “scp ~/a xcscfab:~/”
        cmd_runner.local(
            template(
                f"scp -r $job_config_path_local $remote:$config_path{os.sep} && "
                "ssh $remote -C "
                f"'scp -r $job_config_path $remote_compute:$config_path{os.sep}'"
            )
        )

    def _transfer_config_files_via_sshpass(self) -> None:
        """
        Transfer config files using rsync with sshpass.
        """
        sshpass_args = "-e" if env.env_sshpass else "-f $sshpass"
        cmd_runner.local(
            template(
                f"rsync -pthrvz --rsh='sshpass {sshpass_args} ssh -p 22' "
                "$job_config_path_local/ "
                "$username@$remote:$job_config_path/"
            )
        )

    def _transfer_config_files_via_ssh(self) -> None:
        """
        Transfer config files using rsync with manual SSH.
        """
        cmd_runner.local(
            template(
                f"rsync -pthrvz -e 'ssh -p $port' "
                "$job_config_path_local/ "
                "$username@$remote:$job_config_path/"
            )
        )

    def _transfer_config_files_via_globus(self) -> None:
        """
        Transfer config files using Globus.
        """
        # TODO: implement prevent_results_overwrite here
        cmd_runner.local(
            template(
                "globus-url-copy -p 10 -cd -r -sync "
                "file://$job_config_path_local/ "
                "gsiftp://$remote/$job_config_path/"
            )
        )

    def _transfer_config_files_via_rsync(self,rsync_delete: bool) -> None:
        """
        Transfer config files using rsync.
        """
        cmd_runner.rsync_project(
            local_dir=env.job_config_path_local + "/",
            remote_dir=env.job_config_path,
            delete=rsync_delete,
        )

    def _create_config_directories(self):
        """
        Create the necessary FabSim3 directories automatically when a config file is uploaded.
        """
        directories = ["$config_path", "$results_path", "$scripts_path", "$job_config_path"]
        command = " && ".join(f"mkdir -p {directory}" for directory in directories)
        cmd_runner.run(template(command))

    def calculate_required_nodes(self) -> None:
        """
        Calculate the number of nodes required for job execution and update `env.nodes`.

        This calculation considers whether to reserve full nodes or handle scenarios
        where fewer cores are requested than one node's capacity.

        !!! tip
            - If less than a full node's worth of cores is requested, the calculation ensures that the number of cores per node (`cores_used_per_node`) does not exceed the total cores requested (`cores`).
        """
        # Determine cores to be used per node, ensuring it does not exceed the requested cores
        env.coresusedpernode = min(int(env.corespernode), int(env.cores))
        # Calculate the required number of nodes and set it in `env.nodes`
        env.nodes = int(ceil(float(env.cores) / float(env.coresusedpernode)))

    def calculate_total_memory(self) -> None:
        """
        Calculate the total amount of memory required for the job script.

        !!! tip
            When using the `PJ` option, ensure you set the total required memory
            for all sub-tasks.
        """
        # Set a default memory value if not defined in env
        if not hasattr(env, "memory"):
            env.memory = "2GB"

        # Extract memory size and unit
        memory_size = int(findall(r"\d+", str(env.memory))[0])
        memory_unit_match = findall(r"[a-zA-Z]+", str(env.memory))
        memory_unit = memory_unit_match[0].upper() if memory_unit_match else ""

        # Convert memory unit to a multiplier (1 for MB, 1000 for GB)
        memory_multiplier = 1000 if memory_unit in {"GB", "G"} else 1

        # Calculate total memory based on `PJ` option
        if getattr(env, "PJ", "").lower() == "true":
            env.total_mem = env.memory  # Use memory as is for PJ mode
        else:
            env.total_mem = memory_size * int(env.nodes) * memory_multiplier

    @beartype
    def transfer_config_files(self, config_dir: str) -> None:
        """
        Transfer config files to the remote machine using `rsync`.

        Args:
            config_dir (str): The path to the config directory
        """

        job_manager.set_config(config_dir)
        self._create_config_directories()

        if env.ssh_monsoon_mode:
            self._transfer_config_files_via_scp()
        elif env.manual_sshpass:
            self._transfer_config_files_via_sshpass()
        elif env.manual_ssh:
            self._transfer_config_files_via_ssh()
        elif env.manual_gsissh:
            self._transfer_config_files_via_globus()
        else:
            # Determine if results should be deleted during rsync
            rsync_delete = env.get("prevent_results_overwrite") == "delete"
            '''
            rsync_delete = False
            if (
                hasattr(env, "prevent_results_overwrite")
                and env.prevent_results_overwrite == "delete"
            ):
                rsync_delete = True
            '''
            self._transfer_config_files_via_rsync(rsync_delete)


    @beartype
    def generate_job_with_template(self,
        is_ensemble: Optional[bool] = False, job_label: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate a job name from environment parameters and update the environment

        Args:
            is_ensemble (bool, optional): Whether the job is an ensemble simulation. Defaults to False.
            job_label (str, optional): The job label. Defaults to None.

        Returns:
            Tuple[str, str]: Remote('job_results') and local('job_results_local) job result paths.
        """
        # Generate job name based on the template and label
        job_name = template(env.job_name_template)
        if job_label and not is_ensemble:
            job_name = f"{job_label}_{job_name}"

         # Delegate to the helper function to configure paths
        return self.configure_job_paths(job_name, is_ensemble, job_label)

    @beartype
    def configure_job_paths(self,
        name: str,
        is_ensemble: Optional[bool] = False,
        job_label: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Configure the environment for a specific job name, updating result paths.

        Environmet definitions created:

        - `job_results`: The remote location for storing job results
        - `job_results_local`: The local location for storing job results.


        Args:
            name (str): the job name
            is_ensemble (bool, optional): Indicates if the job is an ensemble simulation. Defaults to False.
            label (str, optional): The label for the job. Defaults to None

        Returns:
            Tuple[str, str]: Remote(`job_results`) and local(`job_results_local`) job result paths.
        """
        env.name = name

        # Determine job result paths based on ensemble mode
        if is_ensemble:
            # Ensemble-specific paths
            job_results = f"{env.pather.join(env.results_path, name)}/RUNS/{job_label}"
            job_results_local = f"{os.path.join(env.local_results, name)}/RUNS/{job_label}"
        else:
            # Standard paths
            job_results = env.pather.join(env.results_path, name)
            job_results_local = os.path.join(env.local_results, name)

        # Set environment variables for job result contents
        env.job_results_contents = env.pather.join(job_results, "*")
        env.job_results_contents_local = os.path.join(job_results_local, "*")

        # Configure the job script name template
        env.job_name_template_sh = f"{name}_{job_label}.sh" if job_label else f"{name}.sh"

        return job_results, job_results_local

    def _display_job_message(self, title: str, message: str):
        """
        Utility to display a message in a formatted panel.
        """
        rich_print(
            Panel.fit(
                message,
                title=f"[orange_red1]{title}[/orange_red1]",
                border_style="orange_red1",
            )
        )

    def _prepare_job_scripts(self, job_args: dict):
        """
        Create job folders and scripts in a temporary folder `<tmp_folder>/{results,scripts}`.
        These files and folders are later transferred in `transfer_job_files` using a single `rsync` command.
        This approach reduces the number of SSH connections and improves job submission stability.
        """
        # Set the job label
        env.label = job_args.get("label", "")

        job_scripts = []

        # Iterate over replicas to prepare job scripts
        replica_start = job_args["replica_start_number"]
        replica_end = replica_start + int(env.replicas)

        for idx in range(replica_start, replica_end):
            env.replica_number = idx

            # Generate job results and job results local paths
            env.job_results, env.job_results_local = job_manager.generate_job_with_template(is_ensemble=env.is_ensemble, job_label=env.label)

            # Append replica number if replicas > 1
            if int(env.replicas) > 1:
                suffix = f"_{idx}" if env.is_ensemble else f"_replica_{idx}"
                env.job_results += suffix

            tmp_job_results = env.job_results.replace(env.results_path, env.tmp_results_path)

            # Complete environment setup
            env["job_name"] = env.name[: env.max_job_name_chars]
            env.run_command = template(env.run_command)
            env.complete_environment()

            # Update run prefix cmds for job setup
            if env.label not in ["PJ_PYheader", "PJ_header"]:
                env.run_prefix += (
                    "\n\n"
                    "# copy files from config folder\n"
                    f"config_dir={env.job_config_path}\n"
                    "rsync -pthrvz --inplace --exclude SWEEP $config_dir/* ."
                )

            if env.is_ensemble:
                env.run_prefix += (
                    "\n\n"
                    "# copy files from SWEEP folder\n"
                    f"rsync -pthrvz --inplace $config_dir/SWEEP/{env.label}/ ."
                )

            # Install Python packages in run prefix cmds if required
            if not (hasattr(env, "venv") and str(env.venv).lower() == "true"):
                if hasattr(env, "py_pkg") and env.py_pkg:
                    env.run_prefix += (
                        "\n\n"
                        "# Install requested Python packages\n"
                        f"pip3 install --user --upgrade {' '.join(env.py_pkg)}"
                    )

            # Generate job script
            # Handle job script naming based on the type of run.
            # For ensemble runs or simple jobs, append `env.label` to the generated
            # job script name. However, for `PJ_PYheader` and `PJ_header` scripts,
            # no additional exec template script should be added to the job script
            if getattr(env, "only_batch_header", False):
                tmp_job_script = script_templates(env.batch_header)
            else:
                tmp_job_script = script_templates(env.batch_header, env.script)


            # Separate base from extension
            base_name, extension = os.path.splitext(env.pather.basename(tmp_job_script))
            # Create job script with appropriate naming
            if int(env.replicas) > 1:
                suffix = f"_{idx}" if env.is_ensemble else f"_replica_{idx}"
                dst_script_name = base_name + suffix + extension
            else:
                dst_script_name = base_name + extension
            dst_job_script = env.pather.join(env.tmp_scripts_path, dst_script_name)
            # Add target job script to the list
            job_scripts.append(env.pather.join(env.job_results, dst_script_name))
            # Copy and set permissions for the script
            copy(tmp_job_script, dst_job_script)
            # chmod +x dst_job_script
            # 755 means read and execute access for everyone and also
            # write access for the owner of the file
            os.chmod(dst_job_script, 0o755)

            # Create temporary job results directory and copy the script
            os.makedirs(tmp_job_results, exist_ok=True)
            copy(dst_job_script, env.pather.join(tmp_job_results, dst_script_name))

            # Write environment variables to a YAML file
            env_file_path = env.pather.join(tmp_job_results, "env.yml")
            with open(env_file_path, "w") as env_file:
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
                    env_file,
                    default_flow_style=False,
                )


        return job_scripts


    def _transfer_job_files(self):
        """
        Transfer all generated files and folders from

        `<tmp_folder>/{results,scripts}`

        to

        `<target_work_dir>/{results,scripts}`

        Supports different transfer modes based on the environment configuration
        """
        # Handles the prevention of results overwrite by using rsync to clear large directories efficiently
        if getattr(env, "prevent_results_overwrite", None) == "delete":
            # For large result directories with thousands of files and folders,
            # using the 'rm' command is inefficient. Instead, we use 'rsync' for better performance.
            # Note:
            # An alternative is using Perl, which can be faster than 'rsync -a --delete', but its availability across all HPC resources is uncertain.
            empty_folder = f"/tmp/{next(tempfile._get_candidate_names())}"

            for item in os.listdir(env.tmp_results_path):
                if env.ssh_monsoon_mode:
                    task_string = template(
                        f"mkdir -p {empty_folder} && "
                        f"mkdir -p {env.work_path}/results/{item} && "
                        f"rm -rf {env.work_path}/results/{item}/*"
                    )
                    cmd_runner.run(
                        template(f"{task_string} ; ssh $remote_compute -C '{task_string}'")
                    )

                else:
                    cmd_runner.run(
                        template(
                            f"mkdir -p {empty_folder} && "
                            f"mkdir -p {env.work_path}/results && "
                            f"rsync -a --delete --inplace {empty_folder}/ "
                            f"{env.work_path}/results/{item}/"
                        )
                    )

        # Define source and destination folder pairs for rsync
        transfer_paths = [
            (env.tmp_scripts_path, env.scripts_path),
            (env.tmp_results_path, env.results_path),
        ]

        rsyc_src_dst_folders = []
        rsyc_src_dst_folders.append((env.tmp_scripts_path, env.scripts_path))
        rsyc_src_dst_folders.append((env.tmp_results_path, env.results_path))
        # Transfer files using the appropriate method
        # for sync_src, sync_dst in rsyc_src_dst_folders:
        for source_path, destination_path in transfer_paths:
            if env.ssh_monsoon_mode:
                cmd_runner.local(
                    template(
                        f"ssh $remote -C 'mkdir -p {destination_path}' && "
                        f"scp -r {source_path} $username@$remote:{destination_path}/../ && "
                        f"ssh $remote -C 'scp -r {destination_path} "
                        f"$remote_compute:{destination_path}/../'"
                    )
                )
            elif env.manual_sshpass:
                sshpass_args = "-e" if env.env_sshpass else "-f $sshpass"
                cmd_runner.local(
                    template(
                        f"rsync -pthrvz --rsh='sshpass {sshpass_args} ssh -p 22' "
                        f"{source_path}/ $username@$remote:{destination_path}/"
                    )
                )
            elif env.manual_gsissh:
                cmd_runner.local(
                    template(
                        f"globus-url-copy -p 10 -cd -r -sync file://{source_path}/ "
                        f"gsiftp://$remote/{destination_path}/"
                    )
                )


            else:
                cmd_runner.rsync_project(local_dir=f"{source_path}/", remote_dir=destination_path)

    def _submit_job(self, job_args : dict):
        """
        Submit prepared job scripts to the target remote machine.

        Parameters:
            job_args (dict): Dictionary containing job arguments. Must include 'job_script'.

        !!! note
            Ensure the list of job scripts to be submitted is provided as input to this function.
        """

        job_script = job_args["job_script"]

        # Check if jobs should be dispatched locally
        if env.get("dispatch_jobs_on_localhost", False) is True:
            cmd_runner.local(template(f"$job_dispatch {job_script}"))
            print("job dispatch is done locally\n")
            return [job_script]

        # Determine the command and dispatch method
        job_dir = env.pather.dirname(job_script)

        if env.remote == "localhost":
            cmd = f"{env.run_prefix} && {template(f'$job_dispatch {job_script}')}"
            cmd_runner.run(cmd=cmd, cd=job_dir)

        elif env.ssh_monsoon_mode:
            cmd = template(
                f"ssh $remote_compute -C '$job_dispatch {job_script}'",
                number_of_iterations=2,  # Allow for variable references in job_dispatch
            )
            cmd_runner.run(cmd=cmd, cd=job_dir)
        else:
            cmd = template(
                f"$job_dispatch {job_script}",
                number_of_iterations=2,  # Allow for variable references in job_dispatch
            )
            cmd_runner.run(cmd=cmd, cd=job_dir)

        return [job_script]

    @beartype
    def ensemble2campaign(self,
        results_dir: str, campaign_dir: str, skip: Optional[Union[int, str]] = 0
    ) -> None:
        """
        Converts FabSim3 ensemble results to EasyVVUQ campaign definition.

        Args:
            results_dir: FabSim3 results root directory
            campaign_dir: EasyVVUQ root campaign directory
            skip: The number of runs (run_1 to run_skip) not to copy to the campaign.
        """
        # Convert skip to an integer (in case it's passed as a string)
        skip = int(skip)
        # If skip > 0, only copy run directories with run_id > skip
        if skip > 0:
            # Get all run directories from the results directory
            run_dirs = os.listdir(os.path.join(results_dir, "RUNS"))
            for run_dir in run_dirs:
                # Extract run_id from 'run_X' (X being the number)
                run_id = int(run_dir.split("_")[-1])
                # If run_id > skip, copy results back to campaign directory
                if run_id > skip:
                    source_path = os.path.join(results_dir, 'RUNS', run_dir)
                    destination_path = os.path.join(campaign_dir, 'runs')
                    rsync_command = f"rsync -pthrvz {source_path} {destination_path}"
                    cmd_runner.local(rsync_command)
        else:
            # Copy all run directories if skip is 0 or negative
            source_path = os.path.join(results_dir, 'RUNS')
            destination_path = os.path.join(campaign_dir, 'runs')
            rsync_command = f"rsync -pthrvz {source_path} {destination_path}"
            cmd_runner.local(rsync_command)


    @beartype
    def campaign2ensemble(self,
        config: str, campaign_dir: str, skip: Optional[Union[int, str]] = 0
    ) -> None:
        """
        Converts an EasyVVUQ campaign run set to a FabSim3 ensemble definition

        Args:
            config (str): FabSim3 configuration name (will create in top-level if
            non-existent, and overwrite existing content).
            campaign_dir (str): EasyVVUQ root campaign directory
            skip (Union[int, str], optional): The number of runs(run_1 to run_skip)
                not to copy to the FabSim3 sweep directory. The first skip number
                of samples will then not be computed.
        """
        # Retrieve the config file path and handle errors if it doesn't exist
        try:
            config_path = job_manager.get_config_file_path(config)
        except FabSimError.FileNotFoundError:
            config_path = os.path.join(env.local_config_file_path[-1], config)
            cmd_runner.local(f"mkdir -p {config_path}")

        # Define the sweep directory and ensure it exists
        sweep_dir = os.path.join(config_path, "SWEEP")
        cmd_runner.local(f"mkdir -p {sweep_dir}")
        # Clean up any previous sweep data
        cmd_runner.local(f"rm -rf {sweep_dir}{os.sep}*")

        # Convert skip to an integer (in case it's passed as a string)
        skip = int(skip)
        # Handle copying based on skip value
        if int(skip) > 0:
            # Get the list of runs from the campaign directory
            campaign_runs = os.listdir(f"{campaign_dir}/runs/")

        for run in campaign_runs:
            # Extract run number from the format run_X
            run_id = int(run.split("_")[-1])
            # Copy the run directory if the run_id is greater than skip
            if run_id > skip:
                print(f"Copying {run}")
                cmd_runner.local(f"rsync -pthrz {campaign_dir}/runs/{run} {sweep_dir}")
        else:
            # If skip = 0, copy all runs from EasyVVUQ to the sweep directory
            cmd_runner.local(f"rsync -pthrz {campaign_dir}/runs/ {sweep_dir}")

    def _count_folders(self, dir_path: str, prefix: str):
        """
        Count the number of folders in a path that match a pattern
        """
        dirs = os.listdir(dir_path)
        return len([d for d in dirs if d.startswith(prefix)])

    def job(self, job_args : dict, submit_job=True):
        """
        Internal low level job launcher.

        Executes a generic job submission on the remote machine. The workflow is divided into three phases to improve job submission efficiency:
            1. Job Preparation
            2. Job Transmission
            3. Job Submission

        Parameters:
            job_args (dict): Arguments for the job.
            submit_job (bool): If True, only prepare and transfer the job scripts.

        Returns:
            list: Generated job scripts for submission on the remote machine.

        """
        # Ensure that `set_config` has been called
        if not hasattr(env, "job_config_path"):
            raise FabSimError.RuntimeError(
                "Function 'job_manager.set_config' was not called, ",
                details="Please call it before 'job_manager.job()'"
            )
        # update the environment variables with the job arguments
        env.update(job_args)
        # Add required label, memory, and core settings to env
        job_manager.calculate_required_nodes()
        job_manager.calculate_total_memory()

        # check if the job is an ensemble simulation
        env.is_ensemble = "sweepdir_items" in job_args

        #  Set up temporary paths for job files, scripts, and results
        env.tmp_work_path = env.pather.join(
            tempfile._get_default_tempdir(),
            next(tempfile._get_candidate_names()),
            "FabSim3",
        )
        # Remove the temporary work path if it already exists
        if os.path.exists(env.tmp_work_path):
            rmtree(env.tmp_work_path)

        # Note: the config_files folder is already transfered by job_manager.transfer_config_files(...)
        env.tmp_results_path = env.pather.join(env.tmp_work_path, "results")
        env.tmp_scripts_path = env.pather.join(env.tmp_work_path, "scripts")
        os.makedirs(env.tmp_scripts_path)
        os.makedirs(env.tmp_results_path)

        # Initialize multiprocessing pool
        POOL = MultiProcessingPool(PoolSize=int(env.nb_process))

        #####################################
        #       Job Preparation Phase       #
        #####################################
        self._display_job_message(
            title="Job Preparation Phase",
            message=f"Temporary Work Path: {env.tmp_work_path}\n\n{yaml.dump(job_args, default_flow_style=False).rstrip()}",
        )

        env.replica_start_number = (
            [int(x) for x in job_args.get("replica_start_number", [1])]
            if isinstance(job_args.get("replica_start_number"), list)
            else int(job_args.get("replica_start_number", 1))
        )

        if env.is_ensemble:
            for idx, task_label in enumerate(env.sweepdir_items):
                replica_start_number = (
                    env.replica_start_number[idx]
                    if isinstance(env.replica_start_number, list)
                    else env.replica_start_number
                )

                POOL.add_task(
                    func=self._prepare_job_scripts,
                    func_args=dict(
                        is_ensemble=env.is_ensemble,
                        label=task_label,
                        replica_start_number=replica_start_number,
                    ),
                )
        else:
            job_args["replica_start_number"] = env.replica_start_number
            POOL.add_task(func=self._prepare_job_scripts, func_args=job_args)

        job_scripts  = POOL.wait_for_tasks()

        #####################################
        #       Job Transmission Phase      #
        #####################################
        self._display_job_message(
            title="Job Transmission Phase",
            message=f"Copying files from: {env.tmp_work_path}\nTo: {env.work_path}",
        )

        self._transfer_job_files()

        # If jobs are submitted using PilotJob option, return the job scripts and skip submission phase
        if submit_job == False:
            return job_scripts

        #####################################
        #        Job Submission Phase       #
        #####################################
        self._display_job_message(
            title="Job Submission Phase",
            message="Submitting all job scripts to the target remote machine.",
        )

        for job_script in job_scripts:
            self._submit_job(dict(job_script=job_script))


        #####################################
        #      Fetching Results Phase       #
        #####################################
        self._display_job_message(
            title="Fetching Results",
            message=f"All jobs are submitted to {env.machine_name}.\n\n"
            f"Use:\n\n"
            f"   fabsim {env.machine_name} fetch_results\n\n"
            "to copy results back to localhost after the jobs are complete.",
        )

        # POOL.shutdown_threads()
        return job_scripts

    @beartype
    def run_ensemble(self,
        config: str,
        sweep_dir: str,
        sweep_on_remote: Optional[bool] = False,
        transfer_config_files: Optional[bool] = True,
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
            sweep_dir (str): Directory containing inputs that will vary per ensemble simulation.
            sweep_on_remote (bool, optional): If True, the `SWEEP` directory is on a remote machine.
            transfer_config_files (bool, optional): If True, transfers `config` files to the remote machine.
            upsample (str, optional): Up-sampling options for directory items.
            replica_start_number (str, optional): Start number for the replica.
            **args: Additional arguments to update environment

        Raises:
            RuntimeError: - if `with_config` function did not called before calling
                    `run_ensemble` task.
                - if `env.script` variable did not set.
                - if `SWEEP` directory is empty.

        """
        # Update environment with provided arguments
        env.update(args)

        # Check for multiple replica_start_numbers
        if ";" in replica_start_number:
            raise NotImplementedError.NotImplementedError(
                "Multiple replica_start_numbers are not yet implemented for users."
            )
        # Validate 'script' presence in env
        if "script" not in env:
            raise FabSimError.RuntimeError(
                "ERROR: run_ensemble function has been called,"
                "but the parameter 'script' was not specified."
            )
        # Ensure that `set_config` has been called
        if not hasattr(env, "job_config_path"):
            raise FabSimError.RuntimeError(
                "Function 'job_manager.set_config' was not called, ",
                details="Please call it before 'job_manager.run_ensemble(...)'"
            )
        # Handle PilotJob option
        submit_job = True
        if getattr(env, "PJ", "").lower() == "true":
            # save all submitted jobs in a list, so it can be used in the PJ script
            env.submitted_jobs_list = []
            # do not submit jobs, only prepare and transfer the job scripts
            submit_job = False
            # Update the script header for PJ jobs, and use simple script, since it is handled in the PJ script
            env.batch_header = "bash_header"
            # check pilot job type
            if not hasattr(env, "PJ_TYPE"):
                raise FabSimError.RuntimeError(
                    "ERROR: 'PJ_TYPE' did not set. It should be set to 'RP' or 'QCG'. Exiting...")
            elif env.PJ_TYPE.lower() not in ["rp", "qcg"]:
                    raise FabSimError.RuntimeError(f"Error: 'PJ_TYPE' must be set to 'RP' or 'QCG'. Exiting...")

        if not sweep_on_remote:
            sweepdir_items = os.listdir(sweep_dir)
            if len(upsample) > 0:
                upsample_items = upsample.split(";")

                folder_name = f"{env.config}_{env.machine_name}_{env.cores}"
                path = os.path.join(env.results_path, folder_name, "RUNS")

                replica_start_number = list(
                    self._count_folders(path, dir) + 1 for dir in upsample_items
                )

                if set(upsample_items).issubset(set(sweepdir_items)):
                    sweepdir_items = upsample_items
                else:
                    missing_items = set(upsample_items) - set(sweepdir_items)
                    raise FabSimError.RuntimeError(f"ERROR: Missing upsample items: {missing_items} in SWEEP folder.")
        else:
            # Reading SWEEP folder from remote machine, so we need a SSH tunnel and then list the directories
            sweepdir_items = cmd_runner.run(f"ls -1 {sweep_dir}").splitlines()

        if len(sweepdir_items) == 0:
            raise FabSimError.RuntimeError(f"ERROR: No files found in the sweep_dir: {sweep_dir}")


        # Reorder `exec_first` item for priority execution.
        if hasattr(env, "exec_first"):
            sweepdir_items.insert(
                0, sweepdir_items.pop(sweepdir_items.index(env.exec_first))
            )

        # TODO: only use transfer_config_files in plugins and not set_config, set_config is already called in transfer_config_files
        if transfer_config_files:
            job_manager.transfer_config_files(config)

        job_scripts = self.job(
            dict(
                ensemble_mode=True,
                sweepdir_items=sweepdir_items,
                sweep_dir=sweep_dir,
                replica_start_number=replica_start_number,
            ),
            submit_job=submit_job,
        )

        # Determine PJ job type and run accordingly
        if hasattr(env, "PJ_TYPE"):
            if env.PJ_TYPE.lower() == "rp":
                # self.run_radical(job_scripts)
                raise NotImplementedError.NotImplementedError(
                    "RADICAL-Pilot is not yet implemented for users."
                )
            elif env.PJ_TYPE.lower() == "qcg":
                self._run_qcg(job_scripts)

    @beartype
    def _run_qcg(self, job_scripts: list):
        """
        Submits QCG Pilot Jobs based on provided job scripts.

        Args:
            job_scripts (list): List of job script paths to be submitted.
        """

        self._display_job_message(
            title="PJ job submission phase",
            message="Submitting QCG Pilot Jobs",
        )

        # Set task model to default if not already set
        env.setdefault("task_model", "default")

        # Collect job scripts for submission
        submitted_jobs = []
        for index, job_script in enumerate(job_scripts, start=1):
            env.idsID = index
            env.idsPath = job_script
            env.dirPath = os.path.dirname(env.idsPath)
            submitted_jobs.append(script_template_content("qcg-PJ-task-template"))

        env.submitted_jobs_list = "\n".join(submitted_jobs)

        # Prevent applying replicas functionality on Pilot Job folders
        env.replicas = "1"
        backup_batch_header = env.batch_header
        env.batch_header = env.PJ_PYheader

        # Generate PilotJob PY script
        job_scripts_to_submit = self.job(
            dict(
                is_ensemble=False, label="PJ_PYheader", only_batch_header=True
            ),
            submit_job=False,
        )

        env.PJ_PATH = job_scripts_to_submit[0]
        env.PJ_FileName = env.pather.basename(env.PJ_PATH)
        env.batch_header = env.PJ_header

        # Construct the run_QCG_PilotJob command
        qcg_pj_command_lines = []
        if hasattr(env, "venv") and str(env.venv).lower() == "true":
            # QCG-PJ should load from virtualenv
            qcg_pj_command_lines.extend([
                "# Activate the virtual environment",
                f"source {env.virtual_env_path}/bin/activate"
            ])

        qcg_pj_command_lines.extend([
            "echo 'Checking if the qcg-pilotjob package is installed...'",
            "python3 -c 'import qcg.pilotjob' 2>/dev/null || pip3 install --upgrade qcg-pilotjob",
            "echo 'Executing the qcg-pilotjob package using Python...'",
            f"python3 {env.PJ_PATH}",
        ])
        env.run_QCG_PilotJob = "\n".join(qcg_pj_command_lines)
        self.job(dict(is_ensemble=False, label="PJ_header", only_batch_header=True))
        env.batch_header = backup_batch_header
        env.only_batch_header = False

    '''
    @beartype
    def run_radical(self, job_scripts: list):

        self._display_job_message(
            title="PJ job submission phase",
            message="Submitting RADICAL-Pilot Jobs",
        )

        # Set task model to default if not already set
        env.setdefault("task_model", "default")

        # Create temporary working directory for Radical runtime files
        local_working_dir = os.path.join(env.tmp_results_path,
            f"radical_{env.config}_{env.machine_name}_{env.cores}"
        )
        remote_working_dir = os.path.join(env.results_path,
            f"radical_{env.config}_{env.machine_name}_{env.cores}"
        )
        os.makedirs(local_working_dir, exist_ok=True)

        # Prepare the environment for Radical TaskDescription
        task_descriptions = []
        for index, task_script in enumerate(job_scripts, start=1):
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
        sandbox_resources_path = os.path.join(
            local_working_dir, ".radical", "pilot", "configs"
        )
        os.makedirs(sandbox_resources_path, exist_ok=True)

        with open(
            os.path.join(sandbox_resources_path, "resource_fabsim.json"), "w"
        ) as f:
            f.write(radical_resources_content)

        # Generate radical-PJ-py script from template
        radical_script_content = script_template_content("radical-PJ-py")
        radical_script_name = f"{env.config}_{env.machine_name}_{env.cores}_radical.py"
        radical_local_script_path = os.path.join(
            local_working_dir, radical_script_name
        )
        radical_remote_script_path = os.path.join(
            remote_working_dir, radical_script_name
        )

        # Create a temporary local file with the radical script content
        with open(radical_local_script_path, "w") as f:
            f.write(radical_script_content)

        # Transfer Radical configuration script to remote machine
        cmd_runner.local(
            template(
                f"rsync -pthrvz {local_working_dir}/ $username@$remote:{remote_working_dir}/"
            )
        )

        # Construct the run_Radical_PilotJob command
        rp_cmd = []
        if str(env.get("venv", "False")).lower() == "true":
            rp_cmd.append("# Activate the virtual environment")
            rp_cmd.append(f"source {env.virtual_env_path}/bin/activate\n")

        rp_cmd.append("# Check if Job is installed")
        rp_cmd.append(
            "python3 -c 'import radical.pilot' 2>/dev/null || "
            "pip3 install --upgrade radical.pilot\n"
        )
        rp_cmd.append("# Python command for task submission")
        rp_cmd.append(f"python3 {radical_remote_script_path}\n")

        env.run_Radical_PilotJob = "\n".join(rp_cmd)

        # Avoid apply replicas functionality on PilotJob folders
        env.replicas = "1"
        backup_header = env.batch_header
        env.batch_header = env.radical_PJ_header
        # env.submit_job = True

        self.job(dict(is_ensemble=False, label="radical-PJ-header", only_batch_header=True))
        env.batch_header = backup_header
        env.only_batch_header = False
    '''

job_manager = JobManager()