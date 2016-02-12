#!/bin/bash

tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static view model controller

ansible-playbook ./deploy_to_localhost.yml

