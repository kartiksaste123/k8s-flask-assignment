#!/usr/bin/env bash
# Usage: scripts/run_and_log.sh <NN_name> "<command>"
# Runs a command, prints it like a terminal session and saves it to evidence/logs/<NN_name>.txt
set -o pipefail
name="$1"; shift
cmd="$*"
out="evidence/logs/${name}.txt"
{
  echo "kartik@cloud-lab:~/k8s-assignment\$ ${cmd}"
  bash -c "${cmd}" 2>&1
  echo
} | tee "${out}"
