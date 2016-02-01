#!/bin/bash

tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static templates

ansible-playbook ./deploy_to_localhost.yml

