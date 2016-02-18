#!/bin/bash

if [ ! -e static/noVNC/README.md ]; then
    git submodule init
    git submodule update
fi

if [ $# -ne 1 ]; then
    echo ""
    echo "usage:"
    echo ""
    echo "Deploy to AWS (See README.md for more details)"
    echo "    $0 AWS"
    echo ""
    echo "Deploy to another host with ansible"
    echo "    $0 <hostname>"
    echo ""
    exit 1
elif [ $1 == "AWS" ]; then
    . private/aws_api_key
    . private/aws_target_config

    export ANSIBLE_HOST_KEY_CHECKING=False

    eval `ssh-agent -s`
    ssh-add private/init_key.pem

    tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static view model controller

    ansible-playbook ./deploy_to_aws.yml

    eval `ssh-agent -k`
else
    export deployment_host=$1

    tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static view model controller

    ansible-playbook ./deploy_to_localhost.yml
fi

