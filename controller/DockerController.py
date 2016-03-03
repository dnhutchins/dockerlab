import socket
import sys
import json
from docker import Client
from model.Container import Container

cli = Client(base_url='unix://var/run/docker.sock')
port = 6000
containers = Container()


class DockerController(object):

    def getrunningcontainers(self, username):

        # Running containers are identified by their public port that
        # correlates to their private port 6801. This is enforced as
        # unique by consequence of socket binding. The public port
        # number is also used in the path for the websocket as defined
        # in the nginx configuration.

        runningimages = []
        for img in containers.getcontainers(username).keys():
            active_container = {}
            rinfo = cli.inspect_container(img)
            active_container['Image'] = rinfo['Config']['Image']
            active_container['Name'] = rinfo['Name'].replace('/', '')
            active_container['Start'] = rinfo['State']['StartedAt']
            active_container['Cid'] = img
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

    def launchcontainer(self, username, container):
        global port
        while testport(port):
            port += 1
        container = cli.create_container(image=container,
                                         ports=[5901],
                                         host_config=cli.create_host_config(
                                             port_bindings={5901: port}))
        response = cli.start(container=container.get('Id'))
        containers.addcontainer(username,
                                container.get('Id'),
                                port,
                                'password')
        port += 1
        return container.get('Id')

    # Set VNC password

    def setvncpassword(self, username, cid, password):
        cmdexc = cli.exec_create(container=cid,
                                 cmd='bash -c \'echo -e "' +
                                 password +
                                 '\n' + password + '\n\n"|vncpasswd\'',
                                 tty=True, user="user")
        cli.exec_start(cmdexc)
        containers.setvncpassword(username, cid, password)
        return True

    # Delete a container

    def deletecontainer(self, username, cid):
        containers.removecontainer(username, cid)
        cli.remove_image(cid)
        return True

    # Reboot a container

    def rebootcontainer(self, cid):
        return cli.restart(cid)

    # get the metadata form for an image

    def getimagemetadata(self, cid, sourcename=''):
        if sourcename != '':
            comment = cli.inspect_image(sourcename)['Comment']
        else:
            rinfo = cli.inspect_container(cid)
            comment = cli.inspect_image(rinfo['Config']['Image'])['Comment']
        try:
            info = json.loads(comment)
        except Exception as e:
            info = json.loads('{"Name": "Unnamed Image",' +
                              '"Desc": "Undescribed Image"}')
        return info

    # Save the container as a new user image

    def saveimage(self, username, cid, name, desc):
        rinfo = cli.inspect_container(cid)
        if (rinfo['Config']['Image'].split(':')[0] == 'userimages_'+username):
            repository = 'userimages_' + username
            tag = str(rinfo['Config']['Image']).split(':')[1]
            message = {}
            message['Name'] = name
            message['Desc'] = desc

            cli.commit(container=cid,
                       repository=repository,
                       tag=tag,
                       message=json.dumps(message))
        else:
            repository = 'userimages_'+username
            containername = str(rinfo['Name']).replace('/', '')
            reponame = str(rinfo['Config']['Image']).split(':')[1]
            tag = containername + '-' + reponame
            message = {}
            message['Name'] = name
            message['Desc'] = desc

            cli.commit(container=cid,
                       repository=repository,
                       tag=tag,
                       message=json.dumps(message))

        containers.removecontainer(username, cid)
        cli.remove_container(container=cid, force=True)
        return True

    # tags an image as a base image
    # requires ADMIN group

    def commitimage(self, repo, reponame, name, desc):
        cli.tag(image=repo, repository="dockerlab", tag=reponame, force=True)
        return True

    # Removes a running container

    def destroycontainer(self, username, cid):
        cli.remove_container(container=cid, force=True)
        containers.removecontainer(username, cid)
        return True

    # gets a copy of the running containers /home directory

    def getcontainerhome(self, cid):
        rinfo = cli.inspect_container(cid)
        name = rinfo['Name'].replace('/', '')
        hometar = {}
        hometar['filename'] = 'attachment; filename="' + name + '_homedir.tar"'
        hometar['data'] = cli.copy(container=cid, resource='/home')
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
