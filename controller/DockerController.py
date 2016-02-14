import socket
import sys
import json
from docker import Client

cli = Client(base_url='unix://var/run/docker.sock')
port = 6000


class DockerController(object):

    def getrunningcontainers(self, username):

        # Running containers are identified by their public port that
        # correlates to their private port 6801. This is enforced as
        # unique by consequence of socket binding. The public port
        # number is also used in the path for the websocket as defined
        # in the nginx configuration.

        containers = cli.containers()
        runningimages = []
        for img in containers:
            active_container = {}
            rinfo = cli.inspect_container(img['Id'])
            active_container['Image'] = img['Image']
            active_container['Name'] = img['Names'][0].replace('/', '')
            active_container['Start'] = rinfo['State']['StartedAt']
            for prt in img['Ports']:
                if prt['PrivatePort'] == 6081:
                    active_container['Port'] = prt['PublicPort']
            runningimages.append(active_container)
        return runningimages

    # Base images will be identified with "dockerlab" as the
    # repository name.

    def getbaseimages(self):
        return self.getimagesbyrepo('dockerlab')

    # User owned images will be identified with "userimages_<username>"
    # at the repository name.

    def getuserimages(self, username):
        return self.getimagesbyrepo('userimages_' + username)

    # Launch a new container
    #
    # Public port availability gets checked at launch time.
    # Ports that are already in use get skipped until
    # the next available port is found. This maintains ligntness
    # by not managing a port mapping in an unnecessary data structure.

    def launchcontainer(self, container):
        global port
        while testport(port):
            port += 1
        container = cli.create_container(image=container,
                                         ports=[6081],
                                         host_config=cli.create_host_config(
                                             port_bindings={6081: port}))
        response = cli.start(container=container.get('Id'))
        port += 1
        return port-1

    # Delete a container

    def deletecontainer(self, container):
        return cli.remove_image(container)

    # Reboot a container

    def rebootcontainer(self, pubport):
        return cli.restart(getcontainerbyport(pubport)['Id'])

    # Remove and start a fresh container from the same image

    def resetcontainer(self, pubport):
        cid = getcontainerbyport(pubport)
        cli.remove_container(container=cid['Id'], force=True)
        container = cli.create_container(image=cid['Image'],
                                         ports=[6081],
                                         host_config=cli.create_host_config(
                                             port_bindings={6081: pubport}))
        cli.start(container=container.get('Id'))

    # get the metadata form for an image

    def getimagemetadata(self, pubport, sourcename=''):
        if sourcename != '':
            comment = cli.inspect_image(sourcename)['Comment']
        else:
            cid = getcontainerbyport(pubport)
            comment = cli.inspect_image(cid['Image'])['Comment']
        try:
            info = json.loads(comment)
        except Exception as e:
            info = json.loads('{"Name": "Unnamed Image",' +
                              '"Desc": "Undescribed Image"}')
        return info

    # Save the container as a new user image

    def saveimage(self, username, pubport, name, desc):
        cid = getcontainerbyport(pubport)
        if (cid['Image'].split(':')[0] == 'userimages_'+username):
            cli.commit(container=cid['Id'],
                       repository='userimages_'+username,
                       tag=str(cid['Image']).split(':')[1],
                       message='{"Name": "' +
                       name +
                       '", "Desc": "' + desc + '"}')
        else:
            cli.commit(container=cid['Id'],
                       repository='userimages_'+username,
                       tag=str(cid['Names'][0]).replace('/', '') +
                       '-'+str(cid['Image']).split(':')[1],
                       message='{"Name": "' +
                       name+'", "Desc": "' + desc + '"}')
        cli.remove_container(container=cid['Id'], force=True)
        return True

    # tags an image as a base image
    # requires ADMIN group

    def commitimage(self, repo, reponame, name, desc):
        cli.tag(image=repo, repository="dockerlab", tag=reponame, force=True)
        return True

    # Removes a running container

    def destroycontainer(self, pubport):
        cid = getcontainerbyport(pubport)
        cli.remove_container(container=cid['Id'], force=True)
        return True

    # gets a copy of the running containers /home directory

    def getcontainerhome(self, pubport):
        cid = getcontainerbyport(pubport)
        name = cid['Names'][0].replace('/', '')
        hometar = {}
        hometar['filename'] = 'attachment; filename="' + name + '_homedir.tar"'
        hometar['data'] = cli.copy(container=cid['Id'], resource='/home')
        return hometar

    # Used to get images using repository name
    # Base image metadata is stored in the comment
    # field of the image in JSON.  If the metadata is absent
    # defaults are assumed for display.

    def getimagesbyrepo(self, repository):
        storedImages = []
        images = cli.images(repository)
        for img in images:
            try:
                info = json.loads(cli.inspect_image(img['Id'])['Comment'])
            except Exception as e:
                info = json.loads('{"Name": "Unnamed Image",' +
                                  '"Desc": "Undescribed Image"}')
            imagedef = {}
            imagedef['RepoTag'] = img['RepoTags'][0]
            imagedef['Name'] = info['Name']
            imagedef['Desc'] = info['Desc']
            storedImages.append(imagedef)
        return storedImages


# Used to confirm the availability of a local port

def testport(portnum):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('0.0.0.0', port))
    except socket.error as e:
        s.close()
        return True
    s.close()
    return False


# Used to reference a public port number to a running container

def getcontainerbyport(pubport):
    containers = cli.containers()
    for img in containers:
        for prt in img['Ports']:
            if prt['PrivatePort'] == 6081:
                if (int(prt['PublicPort']) == int(pubport)):
                    return img
