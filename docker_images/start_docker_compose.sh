#!/bin/bash

# docker compose up --build --scale slurm-base=0 -d
docker compose up --build --scale slurm-base=0 --exit-code-from python-tests