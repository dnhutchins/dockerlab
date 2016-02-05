# dockerlab

DockerLab is a play on Virtualized Desktop Infrastructure (VDI) using docker containers. The goal of DockerLab is to provide a lightweight environment where workload specific desktop images can be created, modified, and shared between a working group of users.

## Common prerequisites

1. git clone https://github.com/dnhutchins/dockerlab.git
2. Obatin Dockerlab.base.image from [HERE](https://drive.google.com/file/d/0BzoMGTw__FoWeUhBNEYtcHdzY28/view?usp=sharing)
3. Place Dockerlab.base.image in the dockerlab directory
4. Execute sudo ./ansible_setup_ubuntu.sh (For Ubuntu, otherwise you will need to set ansible up for your distro)

## Local Installation

1. Execute ./deploy_to_localhost.sh

## Deploy to AWS with ansible playbook

1. Copy the "example_private/" directory to "private/"
2. Edit private/aws_api_key with your AWS API key
3. Edit private/aws_target_config with the values for your target instance
4. Replace the files in "private/ssl" with your SSL certificate and private key
5. Execute ./deploy_to_aws.sh

