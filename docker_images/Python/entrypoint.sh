#!/bin/bash
set -e

# start sshd
echo "Starting sshd..."
/usr/sbin/sshd -D &

# ls -lha /app/FabSim3

# Function to prepend prefix to each line of output
add_prefix() {
    while IFS= read -r line; do
        echo "$LOG_PREFIX $line"
    done
}

# Save the original stdout and stderr file descriptors
exec 3>&1 4>&2


tty=$(readlink /proc/$$/fd/2)

# Loop over Python versions
# for python_version in "3.8" "3.9" "3.10" "3.11"
for python_version in "3.8" "3.9"
do
    ######################################################
    #  Add a prefix to every output (stdout and stderr)  #
    ######################################################
    export LOG_PREFIX="[python $python_version]"
    # Redirect stdout and stderr through the function to add prefix
    exec > >(tee $tty | add_prefix) 2> >(tee $tty | add_prefix)


    # Set pyenv to the current Python version
    pyenv global $python_version
    # Show the Python version
    echo "Using Python version: $(python --version)"
    # Updating pip version to the latest and show the version
    echo "Update pip, setuptools and wheel..."
    pip install --root-user-action=ignore -U pip setuptools wheel
    echo "Using Pip version: $(pip --version)"


    # Install FabSim3 as editable package
    echo "Installing FabSim3..."
    pip install --root-user-action=ignore -e /app/FabSim3

    config_fabsim
    fabsim --show_config


    # show available packages via pip freeze
    echo "Installed packages:"
    pip freeze

    # Reset stdout and stderr to the original file descriptors
    exec 1>&3 2>&4

done

# Restore the original stdout and stderr
exec 1>&3 2>&4

# Exit to terminate the container if no further tasks are required
sleep 1
echo "Completed Python version iterations."
exit 0


