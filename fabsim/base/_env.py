import getpass
import io
import os
import posixpath
from io import StringIO
from pathlib import Path
from platformdirs import user_config_dir
from rich import pretty, traceback
from rich.console import Console
from rich.table import Table, box
from fabsim.base.error_handler import FabSimError
# Better Logging and Tracebacks with Rich :)
# traceback.install()
# any data structures will be pretty printed and highlighted
# pretty.install()



FABSIM_CONFIG_DIR = Path(user_config_dir("fabsim3"))

# work_dir = os.path.dirname(os.path.abspath(__file__))
# localroot = os.path.dirname(os.path.dirname(work_dir))
# fabsim_root = os.path.dirname(work_dir)
# plugins_root = os.path.join(localroot, "plugins")



SSH_DEFAULT_PORT = "22"


ENVIRONMENT_INIT_VALUES = {
        "host": None,
        "username": None,
        "default_port": SSH_DEFAULT_PORT,
        "port": SSH_DEFAULT_PORT,
        "avail_hosts": [],
        "local_user": getpass.getuser(),
        "use_sudo": False,
        "task": None,
        "task_args": [],
        "task_kwargs": {},
        # "localroot": localroot,
        "fabsim_root": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "fabsim_config_dir": FABSIM_CONFIG_DIR,
        "plugin_dir": None,
        "localplugins": {},
        "command_prefixes": [],
        "pather": posixpath,
        "replicas": 1,
        "max_job_name_chars": 15,
        "local_templates_path": [
            os.path.join(FABSIM_CONFIG_DIR, "templates")
            ],
        # "local_config_file_path": [os.path.join(fabsim_root, "config_files")],
        "default_ssh_config_path": os.path.join(
            os.path.expanduser("~"), ".ssh", "config"
        ),
        "env_sshpass": "SSHPASS" in os.environ,

        # TODO: all radical env values should be only enabled when radical is used
        "radical_PJ_py": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-py"
        ),
        "radical_PJ_header": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-header"
        ),
        "PJ_PYheader": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-PYheader"
            ),
        "PJ_header": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-header"
            )
    }


class FabSimEnv(dict):
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

'''
# inspired by fabric 1.x
# https://github.com/fabric/fabric/blob/1.10/fabric/utils.py#L186
class _lookupDict(dict):
    """
    Dictionary superclass which allows users to have direct access to
    key/values.
    t=_lookupDict({"x" : 56})
    t.x is equivalent to t["x"]
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            # to conform with __getattr__ spec
            raise AttributeError(
                f"The environment variable {key} is not defined"
            )
        except Exception as e:
            raise FabSimError.RuntimeError(
                f"Error while trying to access the environment variable {key}",
                details=e.message if hasattr(e, "message") else str(e),
            )


    def __setattr__(self, key, value):
        self[key] = value

    def __str__(self):
        if not env.rich_console:
            from pprint import pformat

            return pformat(self)
        table = Table(
            title="\n\nFabSim3 Environment variables",
            show_header=True,
            show_lines=True,
            expand=True,
            box=box.ROUNDED,
            header_style="dark_cyan",
        )
        table.add_column("Variables", style="blue")
        table.add_column("Value", style="magenta")
        for key, value in self.items():
            table.add_row(key, "{}".format(value))
        # console = Console()
        # console.print(table)
        f = io.StringIO()
        console = Console(file=f, force_terminal=True)
        console.print(table)
        return f.getvalue()

env = _lookupDict(
    {
        "host": None,
        "username": None,
        "default_port": SSH_DEFAULT_PORT,
        "port": SSH_DEFAULT_PORT,
        "avail_hosts": [],
        "local_user": getpass.getuser(),
        "use_sudo": False,
        "task": None,
        "task_args": [],
        "task_kwargs": {},
        "localroot": localroot,
        "fabsim_root": fabsim_root,
        "fabsim_config_dir": FABSIM_CONFIG_DIR,
        "plugin_dir": None,
        "localplugins": {},
        "command_prefixes": [],
        "pather": posixpath,
        "replicas": 1,
        "max_job_name_chars": 15,
        "local_templates_path": [
            os.path.join(FABSIM_CONFIG_DIR, "templates")
            ],
        # "local_config_file_path": [os.path.join(fabsim_root, "config_files")],
        "default_ssh_config_path": os.path.join(
            os.path.expanduser("~"), ".ssh", "config"
        ),
        "env_sshpass": "SSHPASS" in os.environ,

        # TODO: all radical env values should be only enabled when radical is used
        "radical_PJ_py": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-py"
        ),
        "radical_PJ_header": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "radical-PJ-header"
        ),
        "PJ_PYheader": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-PYheader"
            ),
        "PJ_header": os.path.join(
            FABSIM_CONFIG_DIR, "templates", "PJ-header"
            )
    }
)
'''
env = FabSimEnv(ENVIRONMENT_INIT_VALUES)

def update_environment(*dicts):
    for adict in dicts:
        env.update(adict)
