#!/bin/bash

# Ensure proper hostname configuration
HOSTNAME=$(hostname)
sed -i "s/^NodeName=.*/NodeName=$HOSTNAME CPUs=4 State=UNKNOWN/" /etc/slurm/slurm.conf
sed -i "s/^PartitionName=debug Nodes=.*/PartitionName=debug Nodes=$HOSTNAME Default=YES MaxTime=INFINITE State=UP/" /etc/slurm/slurm.conf

# Start MUNGE authentication service
echo "Starting MUNGE service..."
service munge start

# Start SLURM controller
echo "Starting SLURM controller..."
service slurmctld start || {
    echo "Failed to start slurmctld. Logs:"
    cat /var/log/slurm/slurmctld.log
    exit 1
}

# Start SLURM daemon
echo "Starting SLURM daemon..."
service slurmd start || {
    echo "Failed to start slurmd. Logs:"
    cat /var/log/slurm/slurmd.log
    exit 1
}

# Keep container running or execute provided command
if [ "$#" -eq 0 ]; then
    echo "Container is running. Use 'docker exec -it <container_name> /bin/bash' to debug."
    tail -f /dev/null
else
    exec "$@"
fi
