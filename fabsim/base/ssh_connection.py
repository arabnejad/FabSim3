from fabsim.base.environment_manager import env
from contextlib import contextmanager
from fabric2 import Config, Connection
from fabsim.base.utils import add_print_prefix

class HostConnection:
    def __init__(self):
        self.host_address = env.remote
        self.user = env.username
        self.port = env.port
        self.use_sudo = env.use_sudo
        self.pty = True

    @contextmanager
    def ssh_connection(self):
        """
        Make and establish a fabric ssh connection
        """

        conn = Connection(
            host=self.host_address,
            user=self.user,
            port=self.port,
            config=None,
            gateway=None,
            forward_agent=False,
            connect_timeout=None,
            connect_kwargs=None,
            inline_ssh_env=False,
        )

        try:
            print("\x1b[6;30;42m" + "Opening a connection!" + "\x1b[0m")
            conn.open()
            yield conn
        finally:
            print("\x1b[6;30;45m" + "Closing a connection!" + "\x1b[0m")
            conn.close()

    def run_command(self, command, cd=None):
        """
        exec a command on the target remote machine
        """
        # TODO: implement the hide options here

        # this will load the login shell. this required to make sure
        # the module command can be found during job execution
        command = 'bash -l -c "{}"'.format(command)

        # env.remote : localhost
        # env.host_string : user@localhost
        with add_print_prefix(
            prefix="run on {}".format(env.host_string), color=36
        ):
            print("{}".format(command))

        # here, I only set to hide the stdout, and capture any stderr
        # possible values for hide: (None, False, 'out', 'stdout', 'err', 'stderr', 'both', True)
        hide = "out"
        with add_print_prefix(prefix=env.host_string):
            with self.ssh_connection() as conn:
                run = conn.sudo if self.use_sudo else conn.run
                if cd is None:
                    result = run(command, pty=self.pty, hide=hide)

                else:
                    with conn.cd(cd):
                        result = run(command, pty=self.pty, hide=hide)
        return result.stdout
