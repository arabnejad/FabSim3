from beartype import beartype
from beartype.typing import List, Optional, Tuple
import subprocess
import os

from fabsim.base.environment_manager import env
from fabsim.base.logger import add_print_prefix
from fabsim.deploy.templates import template
from fabsim.base.error_handler import FabSimError
from fabsim.base.ssh_connection import HostConnection



class CommandRunner:
    def __init__(self):
        pass


    @beartype
    def local(self,
        command: str,
        cwd: Optional[str] = None,
    ) -> None:
        """
        Run a command on the local system.

        Args:
            command (str): the command to be executed
            cwd (str, optional): the current working directory
        """

        with add_print_prefix(prefix="local", color=36):
            print("{}".format(command))

        cmd_stderr = None
        # execute the command on the local system
        try:
            p = subprocess.Popen(
                command, cwd=cwd, shell=True, stdout=None, stderr=subprocess.PIPE
            )
            # p.wait()
            # yield f"{command} Rsync process completed."
            (_, cmd_stderr) = p.communicate()

        except Exception as e:
            raise FabSimError.RuntimeError("Unexpected error: {}".format(e))
            # sys.exit()


        if p.returncode != 0:
            # Typically, returncode == 0 indicates that it ran successfully
            raise FabSimError.RuntimeError(
                "\nlocal() encountered an error (return code {})"
                "while executing '{}'".format(p.returncode, command),
                details="stderr : {}\n".format(cmd_stderr.decode("utf-8") if cmd_stderr else "NO OUTPUT")
            )

    @beartype
    def run(self, cmd: str, cd: Optional[str] = None):
        if env.manual_sshpass:
            self._local_sshpass(cmd)
        elif env.manual_gsissh:
            self._local_gsissh(cmd)
        elif env.manual_ssh:
            self._local_ssh(cmd)
        else:
            self._remote_run(cmd, cd=cd)

    @beartype
    def _build_run_command(self, cmd: str) -> str:
        # Get command prefixes or an empty list
        commands = env.get("command_prefixes", [])[:]
        # Append 'cd' command if 'cwd' exists in env
        if env.get("cwd"):
            commands.append("cd {}".format(env.cwd))
        # Add the provided command
        commands.append(cmd)
        # Join all commands with '&&' and return
        return " && ".join(commands)

    @beartype
    def _local_sshpass(self, cmd: str):
        # Validate SSHPASS environment or configuration
        if not hasattr(env, "sshpass") and not env.env_sshpass:
            raise FabSimError.RuntimeError(
            "Neither SSHPASS set in environment nor sshpass value set for this remote machine"
        )

        # Construct the full command to be executed
        full_command = self._build_run_command(cmd)

        # Determine sshpass arguments
        sshpass_options = "-e" if env.env_sshpass else f"-f '{env.sshpass}'"

        # Construct the SSH pre-command
        ssh_prefix = f"sshpass {sshpass_options} ssh {env.username}@{env.remote}"

        # Execute the complete SSH command
        self.local(f"{ssh_prefix} '{full_command}'")

    @beartype
    def _local_gsissh(self, cmd: str):
        # Construct the full command to be executed
        full_command = self._build_run_command(cmd)

        # Construct the SSH pre-command
        ssh_prefix = f"gsissh -t -p {env.port} {env.remote}"

        # Execute the complete SSH command
        self.local(f"{ssh_prefix} '{full_command}'")

    @beartype
    def _local_ssh(self, cmd: str):
        """
        Execute a command using SSH
        """
        # Construct the full command to be executed
        full_command = self._build_run_command(cmd)

        # Construct the SSH command prefix
        ssh_prefix = f"ssh -Y -p {env.port} {env.username}@{env.remote}"

        # Execute the command
        self.local(f"{ssh_prefix} '{full_command}'")

    def _remote_run(self, cmd: str, cd: str = None):
        """
        Execute a command on the remote machine.
        """
        conn = HostConnection()
        conn.run_command(command=cmd, cd=cd)


    @beartype
    def rsync_project(self,
        remote_dir: str,
        local_dir: str,
        exclude: List[str] = [],
        delete: Optional[bool] = False,
        ssh_opts: Optional[str] = "",
        default_opts: Optional[str] = "-pthrvz",
        quiet: Optional[bool] = False,
    ) -> None:
        """
        Synchronize a remote directory with the current project directory via
        `rsync`. It uses the env variables (such as user, remote machine address,
        and port) to prepare the needed input options for `rsync` command.

        Args:
            remote_dir (str): the path to the directory on the remote machine.
            local_dir (str): the path to the local directory as the source
                directory
            exclude (list, optional): the list of files/folders to be excluded.
                The list will be pass to `--exclude` option via `rsync` command.
                For example, the input `exclude=['file1.txt','dir1/*','dir2']` will
                be send to `rsync` command as :
                `--exclude={'file1.txt','dir1/*','dir2'}`
            delete (bool, optional): a boolean flag which indicates whether
                the `--delete` option should be passed via `rsync` command or not.
            ssh_opts (str, optional): the extra input args for the SSH options
                string, such as `--rsh` flag.
            default_opts (str, optional): the default rsync options `-pthrvz`,
                override if desired to remove verbosity

        !!! note
            Please make sure both input arguments `remote_dir` and `local_dir`
            ended with a trailing slash.
        """
        # check if input args remote_dir and local_dir end by a trailing slash
        # or not
        if not remote_dir.endswith("/"):
            remote_dir = remote_dir + "/"
        if not local_dir.endswith("/"):
            local_dir = local_dir + "/"

        # create --exclude options from exclude list
        exclude_options = " ".join([f"--exclude={item}" for item in exclude]) if len(exclude) > 0 else ""

        # add --delete options if needed
        delete_option = "--delete" if delete else ""

        # add --quiet option if needed
        quiet_option = "--quiet" if quiet else ""

        # set port arg
        port_option = f"-p {env.port}"

        # set SSH options
        ssh_options = f"--rsh='ssh {' '.join([port_option, ssh_opts])}'"

        # Build the rsync command
        rsync_command = f"rsync {delete_option} {exclude_options} {quiet_option} {default_opts} {ssh_options} {local_dir} {env.host_string}:{remote_dir}"

        with add_print_prefix(prefix="rsync_project", color=36):
            print("{}".format(rsync_command))

        self.local(command=rsync_command)


    @beartype
    def put(self, src: str, dst: str) -> None:
        """
        Upload a file or directory to a remote host.

        !!! note
            In case of `isdir(src) = True`
            - if `dst` ends with `/`, then `src` contents and not the directory
                itself (i.e., all files and sub-directories) will be copied to the
                root of `dst` folder
            - if `dst` *NOT* ends with `/`, the directory  `src` itself with all
                contents will copied to `dst` folder

        Args:
            src (str): Absolute local file or directory path.
            dst (str): Absolute remote destination path.
        """

        # Check if the source is a valid file or director, src should points to a regular file or a directory
        if not (os.path.isfile(src) or os.path.isdir(src)):
            raise FabSimError.RuntimeError(
                "The input path {} is no file neither folder !!! ".format(src)
            )

        # Remove trailing slash ('/') from the source if it's a directory
        if os.path.isdir(src):
            src = src.rstrip("/")
        # Ensure destination directory ends with '/' if source is a file and destination is a directory
        if os.path.isfile(src) and os.path.isdir(dst) and not dst.endswith("/"):
            dst = dst + "/"
        # Adjust the source for directories to include all contents
        if os.path.isdir(src) and os.path.isdir(dst) and dst.endswith("/"):
            src += "/*"

        pu_cmd = ""
        if env.manual_gsissh:
            # TODO : I did not test globus-url-copy, and used the initialize code
            if os.path.isdir(src):
                env.manual_src = f"{src}/" if not src.endswith("/") else src
                env.manual_dest = f"{dst}/"
            else:
                env.manual_src = src
                env.manual_dest = dst
            put_cmd = template(
                "globus-url-copy -sync -r -cd -p 10 "
                "file://$manual_src gsiftp://$host/$manual_dest"
            )
        elif env.manual_ssh:
            scp_opts = "-rp" if os.path.isdir(src.rstrip("*")) else ""
            put_cmd = f"scp {scp_opts} {src} {env.host_string}:{dst}"
        else:
            # Use rsync for file transfer when not using SSH or GSISS
            default_opts = "-pthrvz"
            port_opt = f"-p {env.port}"
            rsh_opts = f"--rsh='ssh {port_opt}'"
            put_cmd = f"rsync {default_opts} {rsh_opts} {src} {env.host_string}:{dst}"

        with add_print_prefix(prefix="put", color=36):
            print("{}".format(put_cmd))

         # Execute the command
        self.local(command=put_cmd)


# TODO: def put shoud move to jobManger
cmd_runner = CommandRunner()