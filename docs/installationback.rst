.. _installationback:

Installation and Testing (old)
==============================

Dependencies
------------

1. FabSim3 requires the following Python modules 
    - PyYAML (any version) 
    - fabric3 (1.1.13.post1 has worked for us)
    - numpy
    - ruamel.yaml

    .. note:: You **ONLY** need to install `ruamel.yaml <https://pypi.org/project/ruamel.yaml>`_ package, others will be installed by FabSim3.
        To install that python package, simply type
        ::
        
            pip3 install ruamel.yaml


2. To perform the ``Py.test`` tests (not required for using FabSim3, but essential for running the tests), you will need `pytest <https://docs.pytest.org/en/latest/getting-started.html>`_ and `pytest-pep8 <https://pypi.org/project/pytest-pep8>`_.


3. To install FabSim3 plugins, **git** needs to be installed in your machine. 

 

Installing FabSim3
------------------

1. Clone the code from the GitHub repository.


    .. code:: console

            git clone https://github.com/djgroen/FabSim3.git


2. To install **all** packages automatically and configure yml files, please got to your FabSim3 directory, and type

    .. code:: console

            python3 configure_fabsim.py



    .. note :: During this installation process, you will be asked for your local machine **password** for installation the required packages.


        
2. After installation process, the main FabSim3 directory is **added** in your ``$PYTHONPATH`` and ``$PATH`` environment variable. You can find these changes on your bash profile (for linux check ``~/.bashrc``, and for MacOS check ``~/.bash_profile``)


3. To make the **fabsim** command available in you system, please restart the shell by opening a new terminal or just re-load your bash profile by ``source`` command.

    .. code:: console

            [Linux machines] source ~/.bashrc
            [MacOS machines] source ~/.bash_profile

    
.. note:: You may have to restart the shell for these changes to apply.

3. Copy ``machines_user_example.yml`` in the ``deploy/`` subdirectory to``machines_user.yml``. Modify its contents so that it matches with your local settings. For first (local) testing, one must change the settings under the sections **default:** and **localhost:** so as to update the paths of FabSim3 directory and lammps executable respectively. 

For Mac Users, make sure to override the default home directory, by switching the **home_path_template** variable by uncommenting the following line::

    home_path_template: "/Users/$username"

4. To enable use of FabSim3 on your local host, type::

    fab localhost setup_fabsim
    
As part of this command, you will be logging in to your own machine through SSH once, which can trigger a password prompt. In this case, simply type the password for the machine in which you are running these commands.

.. note:: For Mac Users, in the ``deploy/machines.yml``, change
    ::    
    runtime_path_template:"$home_path" to runtime_path_template:"~"

5. To enable use of FabSim3 on any other remote machine, make sure that (a) machines.yml contains the specific details of the remote machine, and (b) machines_user.yml contains the specific information for your user account and home directory for the machine. After that, simply type::

    fab <machine_name> setup_fabsim

.. note:: FabSim3 commands can now be launched using the **fabsim** command. Note that some older tutorials might use **fab** commands instead of **fabsim**. If **fabsim** command is not found, simply add PATH and PYTHONPATH (step 2) to ``~/.bash_profile``, as well as set environment for Python3 in the ``bin/fabsim`` by replacing **#!/usr/bin/python3** to **#!/usr/bin/env python3**. The two commands can be used interchangably, although the **fabsim** command gives clearer outputs and can be launched from anywhere (**fab** can only be used within the FabSim3 installation directories). 

Installing plugins
------------------

By default, FabSim3 comes with the FabMD plugin installed. Other plugins can be installed, and are listed in ``deploy/plugins.yml``.

To install a specific plugin, simply type:: 

    fabsim localhost install_plugin:<plug_name>

To create your own plugin, please refer to doc/CreatingPlugins.rst

Updating FabSim3
----------------

If you have already installed FabSim3 and want to update to the latest version, in your local FabSim3 directory simply type::

    git pull
    
Your personal settings like the ``machines_user.yml`` will be unchanged by this.

To update plugins you will have to **git pull** from within each plugin directory as and when required.


Testing FabSim3
---------------

The easiest way to test FabSim3 is to simply go to the base directory of your FabSim3 installation and try the examples below.

Mac users may get a 
``ssh: connect to host localhost port 22: Connection refused`` error. This means you must enable remote login. This is done in ``System Preferences > Sharing > Remote Login``.

List available commands
-----------------------

Simply type::

    fabsim -l

FabDummy testing on the local host
----------------------------------

Plugin Installation
~~~~~~~~~~~~~~~~~~~
Simply type::

    fabsim localhost install_plugin:FabDummy

anywhere inside your FabSim3 install directory. **FabDummy** plugin will be downloaded under::
    
    <fabsim home folder>/plugins/FabDummy


Testing
~~~~~~~
1. To run a dummy job, type::

    fabsim localhost dummy:dummy_test
    
2. To run an ensemble of dummy jobs, type::

    fabsim localhost dummy_ensemble:dummy_test
    
3. for both cases, i.e., a single dummy job or an ensemble of dummy jobs, you can fetch the results by using::

    fabsim localhost fetch_results

For more advanced testing features, please refer to the FabDummy tutorial at https://github.com/djgroen/FabDummy/blob/master/README.md.


LAMMPS testing on the local host
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install LAMMPS (see http://lammps.sandia.gov for detailed download and installation instructions).
2. Modify ``machines_user.yml`` to make the **lammps_exec** variable point to the location of the LAMMPS executable. e.g.::
    
    lammps_exec: "/home/james/bin/lmp_serial"
    
3. FabSim3 contains sample LAMMPS input files, so there's no need to download that.
4. (first time use only) Create the required FabSim3 directory using the following command::
    
    fabsim localhost setup_fabsim
    
5. Before run LAMMPS test data set, you should install FabMD which provides functionality to extend FabSim3's workflow and remote submission capabilities to LAMMPS specific tasks. Please install it by typing::

    fabsim localhost install_plugin:FabMD
    
6. Run the LAMMPS test data set using:: 
    
    fabsim localhost lammps_dummy:lammps_dummy,cores=1,wall_time=1:00:0
    
7. Run the following command to copy the output of your job in the results directory. By default this will be a subdirectory in ``~/FabSim3/results``::

    fabsim localhost fetch_results

Creating the relevant FabSim3 directories on a local or remote host
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure that you have modified ``machines_user.yml`` to contain correct information for your target machine.

Auto bash-completion for fabsim
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable this option, please run on your FabSim3 directory::
     
     source fabsim-completion.bash
     
or you can add the following command into your ``$HOME/.bashrc`` file to have enable it everytime that the shell is activated::

    source (path of your FabSim3 directory)/fabsim-completion.bash

