from pathlib import Path
from platformdirs import user_config_dir
from fabsim.base.error_handler import FabSimError
import getpass
import os
import posixpath
import time
from beartype import beartype
from beartype.typing import Optional
from string import Template

FABSIM_CONFIG_DIR = Path(user_config_dir("fabsim3"))
SSH_DEFAULT_PORT = "22"

class EnvironmentManager(dict):
    def __new__(cls, *args, **kwargs):
        # Create the instance
        instance = super().__new__(cls)

        # Set variables before __init__
        instance["avail_tasks"] = {}

        instance["host"] = None
        instance["username"] = None
        instance["default_port"] = SSH_DEFAULT_PORT
        instance["port"] = SSH_DEFAULT_PORT
        instance["avail_hosts"] = []
        instance["local_user"] = getpass.getuser()
        instance["use_sudo"] = False
        instance["task"] = None
        instance["task_args"] = []
        instance["task_kwargs"] = {}
        instance["fabsim_root"] =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        instance["fabsim_config_dir"] = FABSIM_CONFIG_DIR
        instance["plugin_dir"] = None
        # instance["localplugins"] = {}
        instance["command_prefixes"] = []
        instance["pather"] = posixpath
        instance["replicas"] = 1
        instance["max_job_name_chars"] = 15
        instance["local_templates_path"] =  [
            os.path.join(FABSIM_CONFIG_DIR, "templates")
            ]
        instance["default_ssh_config_path"] = os.path.join(
            os.path.expanduser("~"), ".ssh", "config"
        )
        instance["env_sshpass"] = "SSHPASS" in os.environ
        # TODO: this should be removed from here
        # TODO: all radical env values should be only enabled when radical is used
        instance["radical_PJ_py"] = os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-py"
        )
        instance["radical_PJ_header"] = os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-header"
        )
        instance["PJ_PYheader"] = os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-PYheader"
            )
        instance["PJ_header"] = os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-header"
            )


        # Must return the created instance.
        return instance

    def __init__(self, *args, **kwargs):
        # Initialize the dictionary with provided arguments
        super().__init__(*args, **kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            # to conform with __getattr__ spec
            raise AttributeError(
                f"The environment variable '{key}' not found"
            )
        except Exception as e:
            raise FabSimError.RuntimeError(
                f"Error while trying to access the environment variable {key}",
                details=e.message if hasattr(e, "message") else str(e),
            )

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"The environment variable '{key}' not found")

    @beartype
    def get_remote_address_str(self) -> str:
        """
        Get the remote address string based on the environment variables.
        """
        return self.template("$username@$remote")

    @beartype
    def get_sshpass_cmd(self) -> str:
        """
        Get the sshpass command based on the environment variable.
        """
        sshpass_args = self.template("-e" if env.env_sshpass else "-f $sshpass")
        return f"sshpass {sshpass_args}"

    @beartype
    def template(self, pattern: str) -> str:
        """
        Low-level templating function, insert env variables into any string pattern
            - number_of_iterations can be adjusted to allow recurring
                    templating using a single function call.
        """
        try:
             return Template(pattern).substitute(env)
        except KeyError as err:
            msg = "FABSIM_TEMPLATE_KEYERROR\n"\
                "Template variables were not found in FabSim env dictionary. " \
                "These variables need to be added, with a default value set.\n" \
                f"ORIGINAL PATTERN: {pattern}\n" \
                f"SAFELY SUBSTITUTED PATTERN: {Template(pattern).safe_substitute(env)}"

            details_msg = "FabSim performed a 'substitute' and print the original " \
                "template and the partially substituted one (both are given above" \
                "this message). Variables that are missing in the env dictionary" \
                "will be displayed unsubstituted in the output text. FabSim will" \
                "now terminate as these errors would result in unpredictable" \
                "behavior otherwise."

            # sys.tracebacklimit = 0
            raise FabSimError.KeyError(msg, details=details_msg)
            # sys.exit()

    def generate_module_commands(self, script=None):
        """
        Generates the required module commands for the remote machine scripts.
        It reads the `modules` env variables defined in machine yaml files.
        Example input entry:
        ```yaml
        modules:
            # list of modules to be loaded on remote machine
            loaded: ["python/3.7.3", "openmpi/4.0.0_gcc620"]
            # list of modules to be unloaded on remote machine
            unloaded: ["python"]

        ```
        and generates these lines in the job script
        ```sh
        # unload modules
        module unload python
        # load required modules
        module load python python/3.7.3 openmpi/4.0.0_gcc620
        ```
        """
        module_commands = [
            "module {}".format(module) for module in env.modules["all"]
        ]

        module_commands += [
            "module {}".format(module)
            for module in env.modules.get("nonexistent", "")
        ]

        module_commands += [
            "module unload {}".format(module)
            for module in env.modules.get("unloaded", "")
        ]
        module_commands += [
            "module load {}".format(module)
            for module in env.modules.get("loaded", "")
        ]
        if script is not None:
            module_commands += [
                "module {}".format(module)
                for module in env.modules.get(script, "")
            ]
        return module_commands

    def complete_environment(self) -> None:
        """
        Add paths to the environment based on information in the yaml configs
        files.

        Environment vars created can be used in job-script templates:

        - `results_path`: Path to store results
        - `remote_path` : Root of area for checkout and build on remote
        - `config_path` : Path to store config files
        - `scripts_path` : Path where job-queue-submission scripts generated by
            Fabric are sent.
        - `run_prefix` : Command string to invoke before any job is run.
        """
        env.host_string = "{}@{}".format(env.username, env.remote)
        env.home_path = self.template(env.home_path_template)
        env.runtime_path = self.template(env.runtime_path_template)
        env.work_path = self.template(env.work_path_template)
        env.remote_path = self.template(env.remote_path_template)
        env.stat = self.template(env.stat)
        env.results_path = os.path.join(env.work_path, "results")
        env.config_path = os.path.join(env.work_path, "config_files")
        env.scripts_path = os.path.join(env.work_path, "scripts")
        if env.plugin_dir:
            env.local_results = os.path.join(os.path.expanduser(
                self.template(env.plugin_dir)), "results")
        env.local_system_time = int(time.time())

        if hasattr(env, "flee_location"):
            env.flee_location = self.template(env.flee_location)

        for i in range(0, len(env.local_templates_path)):
            env.local_templates_path[i] = os.path.expanduser(
                self.template(env.local_templates_path[i])
            )

        for i in range(0, len(env.local_config_file_path)):
            env.local_config_file_path[i] = os.path.expanduser(
                self.template(env.local_config_file_path[i])
            )

        module_commands = self.generate_module_commands(script=env.get("script", None))
        run_prefix_commands = env.run_prefix_commands[:]
        env.run_prefix = (
            " \n".join(
                module_commands
                + list(map(self.template, map(self.template, run_prefix_commands)))
            )
            or "/bin/true || true"
        )


        if env.temp_path_template:
            env.temp_path = self.template(env.temp_path_template)

        if hasattr(env, "virtual_env_path") and env.virtual_env_path:
            env.virtual_env_path = self.template(env.virtual_env_path)

        if hasattr(env, "app_repository") and env.app_repository:
            env.app_repository = self.template(env.app_repository)

        if (
            # not any(
            #     "install_app" in str or "install_packages" in str
            #     for str in env.tasks
            # )
            env.task in ["install_app", "install_packages"]
            and hasattr(env, "venv")
            and str(env.venv).lower() == "true"
        ):
            # since we are going to load python VirtualEnv, so, it would be better
            # to unload any current loaded python modules, in order to avoid
            # conflicts during the execution of python program
            env.run_prefix += (
                "\n# load python from VirtualEnv"
                "\nmodule unload python\n"
                "source {}/bin/activate".format(env.virtual_env_path)
            )

    # def updateEnvironment(self, arg: dict )->None:
    #     self.update(arg)
    #     # for adict in dicts:
    #     #     self.update(adict)


env = EnvironmentManager()

'''
def update_environment(*dicts):
    env.updateEnvironment(*dicts)
    # for adict in dicts:
    #     env.update(adict)
'''