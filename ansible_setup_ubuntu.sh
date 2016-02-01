#!/bin/bash

apt-get install software-properties-common
apt-add-repository ppa:ansible/ansible
apt-get update
apt-get install ansible
ansible-galaxy install angstwad.docker_ubuntu
ansible-galaxy install jdauphant.ssl-certs
ansible-galaxy install jdauphant.nginx
apt-get install python-pip
pip install boto

