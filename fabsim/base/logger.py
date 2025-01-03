from contextlib import contextmanager

import sys


class Prefixer(object):
    def __init__(self, prefix, orig):
        self.prefix = prefix
        self.orig = orig

    def write(self, text):
        for t in text.rstrip().splitlines():
            self.orig.write(self.prefix + t + "\n")

    def __getattr__(self, attr):
        return getattr(self.orig, attr)


def colored(color_code, text):
    return "\033[38;5;{}m{}\033[0;0m ".format(color_code, text)


@contextmanager
def add_print_prefix(prefix, color=24):
    # source : https://stackabuse.com/how-to-print-colored-text-in-python
    # https://www.ditig.com/publications/256-colors-cheat-sheet
    current_out = sys.stdout
    try:
        sys.stdout = Prefixer(
            prefix=colored(color, "[{}]".format(prefix)), orig=current_out
        )
        yield
    finally:
        sys.stdout = current_out