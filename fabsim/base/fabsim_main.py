from __future__ import absolute_import

import builtins
import inspect
import sys
from optparse import OptionParser, make_option
from pprint import pformat, pprint

from rich import get_console
from rich import print as rich_print
from rich.panel import Panel

from fabsim.base.environment_manager import env
from fabsim.base.fab import *

from fabsim.base.fabsim_tasks import *
# from fabsim.deploy.machines import (
#     # available_remote_machines,
#     remote_machines,
#     # machine_config_info,
#     # load_machine,
#     # load_plugins,
# )
import glob

from fabsim.base.error_handler import FabSimError
from fabsim.base.config_fabsim import FABSIM_CONFIG_DIR
# from fabsim.base.setup_fabsim import avail_plugin, install_plugin
# from fabsim.base.decorators import add_prefix_to_print
from fabsim.base.plugin_manager import plugin_manager
from fabsim.base.remote_machine_manager import remote_machine_manager
from fabsim.base.command_line_parser import CommandLineParser
from fabsim.base.utils import (
    OpenVPNContext,
    # find_all_avail_tasks,
    show_avail_tasks,
)
# def getPluginRootDir(path : str) -> bool:
#     """check if the fabsim is called from a valid plugin directory

#     Args:
#         path (str): the path of the directory from which the script is called

#     Returns:
#         bool: true if the script is called from a valid plugin directory
#     """
#     pattern = "Fab*.py"
#     # Stop before falling off root of filesystem (should be platform agnostic)
#     while os.path.split(os.path.abspath(path))[1]:
#         # look for a py file named started with fab_ in the directory
#         if glob.glob(os.path.join(path, pattern)):
#             fab_files = [os.path.basename(f) for f in glob.glob(os.path.join(path, pattern))]
#             if len(fab_files) > 1:
#                 raise FabSimError.ValueError(
#                     f"Multiple Fab* files {fab_files} found in the plugin directory.",
#                     details="Please make sure there is only one Fab* file in the plugin directory."
#                 )
#             return path, os.path.splitext(fab_files[0])[0]
#         path = os.path.split(path)[0]
#     return None, None



# def load_plugin():
#     """
#     Load the current plugin which fabsim command is called from
#     """
#     # here, if we use the globals(), new changes will no be permanent for other
#     # files, so, we need to write them into global namespace seen by this frame
#     caller_globals = inspect.stack()[1][0].f_globals

#     try:
#         with add_print_prefix(prefix="loading plugin", color=28):
#             print("{} ...".format(env.plugin_name))

#         plugin = importlib.import_module("{}".format(env.plugin_name))
#         plugin_dict = plugin.__dict__

#         try:
#             to_import = plugin.__all__
#         except AttributeError:
#             to_import = [
#                 name for name in plugin_dict if not name.startswith("_")
#             ]

#         caller_globals.update(
#             {name: plugin_dict[name] for name in to_import}
#         )
#         env.localplugins.update({env.plugin_name: env.plugin_dir})

#     except ImportError as e:
#         print(e)
#         raise FabSimError.ImportError(e.message if hasattr(e, "message") else e)


def main():
    """
    Main FabSim3 command-line execution function
    """

    """
    # replace builtin python print function with the new print function
    # from rich module
    builtins.print = rich_print
    # use soft wrapping
    # https://github.com/willmcgugan/rich/issues/1041
    console = get_console()
    console.soft_wrap = True
    """

    custom_usage = """
    fabsim [remote_machine] <task>[:arg1=val1,arg2=val2,...]
    or
    fabsim [optional arguments]

    """

    #####################################################
    # check if fabsim configuration files are available #
    #####################################################
    if not os.path.exists(FABSIM_CONFIG_DIR):
        raise FabSimError.RuntimeError(
            f"FabSim3 configuration files are not available in {FABSIM_CONFIG_DIR}",
            details="Please run config_fabsim command to create the configuration files."
        )


    # Create the parser
    cli = CommandLineParser()
    cli.parse_arguments()

    ##########################################################
    # find the plugin root directory if the script is called #
    # from a plugin directory or its subdirectories          #
    ##########################################################
    plugin_manager.loadPlugin(os.getcwd())
    remote_machine_manager.loadPluginMachinesConfig()


    '''
    plugin_manager.setPluginRootDir(os.getcwd())

    if env.plugin_dir != None:
        # add current plugin directory to the PYTHONPATH
        sys.path.insert(0, env.plugin_dir)
        # load plugin specific configurations for machines
        remote_machines.load_plugin_machines_config(env.plugin_name)
        # load the plugin
        load_plugin()
    '''


    #####################################
    # find all available tasks/machines #
    #####################################
    # env.avail_tasks = find_all_avail_tasks()
    # print(env.avail_tasks)
    # env.avail_machines = remote_machine_manager.available_remote_machines()

    #####################################
    # checking input optional arguments #
    #####################################
    if cli.requestShowAvailableTasks():
        show_avail_tasks()
        sys.exit()
    elif cli.requestShowAvailableMachines():
        remote_machine_manager.showAvailMachines()
        sys.exit()
    elif cli.requestShowAvailablePlugins():
        plugin_manager.showAvailPlugins()
        sys.exit()
    elif cli.requestShowRemoteMachineConfig():
        remote_machine_manager.printMachineConfigInfo()
        sys.exit()
    elif cli.requestInstallPlugin():
        if env.plugin_name != None:
            raise FabSimError.RuntimeError(
                "Install plugin command is not allowed to run from a plugin directory.",
                details=f"Install plugin command called inside {env.plugin_name} plugin directory."
            )
        else:
            # install_plugin(cli.getRequestedPluingName())
            plugin_manager.installPlugin(cli.getRequestedPluingName(), os.getcwd())
            sys.exit()
    '''
    if args.list:
        if args.list == "tasks":
            show_avail_tasks()
            sys.exit()
        elif args.list == "machines":
            show_avail_machines()
            sys.exit()
        elif args.list == "plugins":
            avail_plugin()
            sys.exit()
    elif args.install != None:
        if env.plugin_name != None:
            raise FabSimError.RuntimeError(
                "Install plugin command is not allowed to run from a plugin directory.",
                details=f"Install plugin command called inside {env.plugin_name} plugin directory."
            )
        else:
            install_plugin(args.install)
        sys.exit()
    elif args.remote != None:
        env.host = args.remote
        remote_machine_manager.printMachineConfigInfo()
        sys.exit()
    '''

    # at this point, we are sure that the user is trying to execute a plugin task, so we need to check if the script is called from a valid plugin directory
    if env.plugin_dir == None:
        raise FabSimError.RuntimeError(
        "The script is not called from a valid FabSim3 plugin directory.",
        details="To run fabsim command, you need to be in root or any subdirectory of a FabSim3 plugin."
        )



    # ###########################################################
    # # check if fabsim is called inside a valid FabSim3 plugin #
    # ###########################################################
    # if env.plugin_dir == None:
    #     raise FabSimError.RuntimeError(
    #         "The script is not called from a valid FabSim3 plugin directory.",
    #         details="To run fabsim command, you need to be in root or subdirectory of a FabSim3 plugin."
    #     )



    ##########################################################################
    # set the target remote machine                                          #
    # by default, our assumption is the first arguments after fabsim command #
    # should be the name of target remote machine                            #
    ##########################################################################
    sub_commands = cli.getSubCommands()

    if len(sub_commands) == 0:
        raise FabSimError.ValueError(
            "First argument expected to be target remote machine.",
            details="Try `-h` for usage information."
        )

    env.host = sub_commands[0]
    if env.host not in env.avail_machines:
        raise FabSimError.ValueError(
            f"The requested remote machine '{env.host}' did not listed in the "
            "machines.yml file, so it can not be used as a target remote host.",
            details=f"The available remote machines are : {env.avail_machines.keys()}"
        )


    # env.complete_environment()

    ####################################################
    # check if the task is a valid FabSim3 task or not #
    ####################################################
    if len(sub_commands) == 1:
        raise FabSimError.RuntimeError(
            "There is no task specified to execute. Please provide a task name after remote machine name to execute.",
            details="Try 'fabsim -l tasks` to see the list of available tasks."
        )

    env.task = sub_commands[1].split(":", 1)[0]
    if env.task not in env.avail_tasks:
        raise FabSimError.RuntimeError(
            f"The request task {env.task} is not available!!",
            details="Try 'fabsim -l tasks` to see the list of available tasks."
        )



    env.exec_func = env.avail_tasks[env.task]

    ################################################################
    # set the task and its input args                              #
    # by default, the next input arguments after machine name is   #
    # the task name, followed by the input arguments for the task. #
    ################################################################

    # Convert key-value task args string to a dictionary
    try:
        task_args_str = sub_commands[1].split(":", 1)[1]
    except IndexError:
        task_args_str = None

    task_args = []
    task_kwargs = []
    if task_args_str is not None:
        for sub in task_args_str.split(","):
            if "=" in sub:
                task_kwargs.append(map(str.strip, sub.split("=", 1)))
            else:
                task_args.append(sub)

    env.task_args = task_args
    env.task_kwargs = dict(task_kwargs)

    ############################################
    # Load the machine-specific configurations #
    ############################################
    # remote_machines.load_machine(env.host)
    remote_machine_manager.loadMachine(env.host)


    ##############################
    # execute the requested task #
    ##############################
    with OpenVPNContext(env):
        env.exec_func(*env.task_args, **env.task_kwargs)


if __name__ == "__main__":
    main()
