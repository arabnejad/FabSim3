## FabSim : remote job management command

##### This document explains how users should set and use remote machine functionality.

Note that, in this tutorial, all parameters are set based on our tested target machine  (the Eagle cluster at PSNC) which uses [QCG Middleware](http://apps.man.poznan.pl/trac/qcg/) for resource management. For the local testing, you need to change them based your remote machine configuration and usage software.

### machine configuration
To execute jobs through remote resource schedulers, some **essential** machine-specific configurations are required to be set and stored. These parameters will be applied to all applications run on that remote machine. 

Here is a simple example for remote machine configuration in ```/deploy/machines.yml``` file.


> ```File : /deploy/machines.yml```
> ``` yaml
> ---
> qcg: # machine name
> 	remote: 'eagle.man.poznan.pl'
>	home_path_template: '/home/plgrid/$username'
>	manual_ssh: true
>	dispatch_jobs_on_localhost: true
>	job_dispatch : 'qcg-sub'
>	batch_header: qcg-eagle
>	stat: 'qcg-list -Q -s all -F "%-22I %-16S %-8H" | awk "{if(NR>2)print}"'
>	job_dispatch: 'qcg-sub'
>	cancel_job_command: 'qcg-cancel $jobID'
>	job_info_command : 'qcg-info -Q $jobID'
> ---
> ```


* `qcg` : the name of target remote machine machine, it will use by FabSim as ```fab qcg <command>```. internally, FabSim uses ```<$user_name>@<$remote>``` to connect to the remote machine.
* `remote` : the remote machine address. FabSim uses ```<$user_name>@<$remote>``` template internally all connection. 
	* `user_name` parameter should be set in ```/deploy/machines_user.yml``` file as :

		> `File : /deploy/machines_user.yml`
		> ``` yaml
		> ---
		> qcg: # machine name
		> 	username: "plg..." 
		> ---
		> ```


* `home_path_template` : used to the storage space to checkout and build on the remote machine

* `manual_ssh` :

* `dispatch_jobs_on_localhost` : if it is set to `true`, job dispatch is done locally. Otherwise, FabSim executes commands directly inside the remote machine by `ssh` connection. To dispatch job locally, the command-line interface for job management should be installed in your local machine.

* `batch_header` : it can be used to add some predefined templates to the submitted job script. The template file should be store at `/deploy/templates`.

* `stat` : filled by the command-line that displays report on the submitted jobs. In this example, according to our grid broker, `qcg-list` command displays table with information about tasks. <br/> please note that, it should be set in the way that only return jobID, job status, and host in the output (without column header). For example, the template output should be similar to :<br/>
		```
			...		...			...
			jobID1	FINISHED	eagle
			jobID2	FAILED		tryton
			jobID3	CANCELED	prometheus  
			...		...			...			
		```

* `job_dispatch` : the command to submit the task to be processed by remote machine

* `cancel_job_command` : the command to cancel the submitted task based on input `$jobID`. the `$jobID` variable will be set during the execution, keep the format as `$jobID` in the parameters list

* `job_info_command` : the command to display a comprehensive information of a specific `jobID`. please set this parameters based on the workload manager of target remote machine, i.e : `<command> <parameters> $jobID`. The `$jobID` variable will be set during the execution, keep the format as `$jobID` in the parameters list.