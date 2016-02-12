#!/bin/bash

. private/aws_api_key
. private/aws_target_config

export ANSIBLE_HOST_KEY_CHECKING=False

eval `ssh-agent -s`
ssh-add private/init_key.pem

tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static view model controller

ansible-playbook ./deploy_to_aws.yml

eval `ssh-agent -k`
