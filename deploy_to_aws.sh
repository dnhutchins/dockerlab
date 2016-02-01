#!/bin/bash

. private/aws_api_key

export EC2_REGION='us-west-2'
export SUBNET='subnet-f4a12aad'
export INSTANCE_TYPE='t2.micro'
export INIT_KEY='<Your EC2 keypair name>'
export ANSIBLE_HOST_KEY_CHECKING=False
export DOMAIN_NAME="example.com" # Your Route53 ZONE
export HOST_NAME="dockerlab.example.com" # The FQDN to be added/updated in Route53

eval `ssh-agent -s`
ssh-add private/init_key.pem

tar zcvf dl.tgz auth.py DockerLab.py genconf.sh static templates

ansible-playbook ./deploy_to_aws.yml

eval `ssh-agent -k`
