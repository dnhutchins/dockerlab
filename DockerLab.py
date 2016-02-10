#!/usr/bin/python

# DockerLab is a play on Virtualized Desktop Infrastructure (VDI)
# using docker containers. The goal of DockerLab is to provide a
# lightweight environment where workload specific desktop images
# can be created, modified, and shared between a working group
# of users. In the spirit of lightness, DockerLab doesn't use any
# datastore other than Docker itself. Image metadata is stored
# directly in the comment field of the image as a JSON object

import cherrypy
import socket
import sys
import json
from docker import Client
from mako.template import Template
from mako.lookup import TemplateLookup
from auth import AuthController, require, member_of, name_is

SESSION_KEY = '_cp_username'
lookup = TemplateLookup(directories=['view'])
cli = Client(base_url='unix://var/run/docker.sock')
port = 6000


# Decorator to designate mime type

def mimetype(type):
    def decorate(func):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = type
            return func(*args, **kwargs)
        return wrapper
    return decorate


def handle_error():
    tmpl = lookup.get_template("error.html")
    cherrypy.response.status = 500
    cherrypy.response.body = [
        tmpl.render()
    ]


class DockerLab(object):

    _cp_config = {
        'tools.sessions.on': True,
        'tools.auth.on': True,
        'tools.proxy.on': True,
        'tools.proxy.local': 'X-Forwarded-Host',
        'tools.proxy.local': 'Host',
        'request.error_response': handle_error
    }

    auth = AuthController()

    @cherrypy.expose
    @require()
    def index(self):
        sess = cherrypy.session
        username = cherrypy.session.get(SESSION_KEY)
        runningcount = 0
        savedcount = 0
        # Running containers are identified by their public port that
        # correlates to their private port 6801. This is enforced as
        # unique by consequence of socket binding. The public port
        # number is also used in the path for the websocket as defined
        # in the nginx configuration.

        containers = cli.containers()
        runningimages = []
        for img in containers:
            active_container = {}
            runningcount += 1
            rinfo = cli.inspect_container(img['Id'])
            active_container['Image'] = img['Image']
            active_container['Name'] = img['Names'][0].replace('/', '')
            active_container['Start'] = rinfo['State']['StartedAt']
            for prt in img['Ports']:
                if prt['PrivatePort'] == 6081:
                    active_container['Port'] = prt['PublicPort']
            runningimages.append(active_container)

        # Base images will be identified with "dockerlab" as the
        # repository name.

        baseimages = self.getimagesbyrepo('dockerlab')
        savedcount += len(baseimages)

        # User owned images will be identified with "userimages_<username>"
        # at the repository name.

        userimages = self.getimagesbyrepo('userimages_' + username)
        savedcount += len(userimages)

        tmpl = lookup.get_template("index.html")
        return tmpl.render(baseimages=baseimages,
                           userimages=userimages,
                           runningimages=runningimages,
                           runningcount=runningcount,
                           savedcount=savedcount,
                           username=username)

    # Launch a new container
    #
    # Public port availability gets checked at launch time.
    # Ports that are already in use get skipped until
    # the next available port is found. This maintains ligntness
    # by not managing a port mapping in an unnecessary data structure.

    @cherrypy.expose
    @require()
    def launch(self, container):
        global port
        while testport(port):
            port += 1
        container = cli.create_container(image=container,
                                         ports=[6081],
                                         host_config=cli.create_host_config(
                                             port_bindings={6081: port}))
        response = cli.start(container=container.get('Id'))
        port += 1
        tmpl = lookup.get_template("connect.html")
        return tmpl.render(wait='4',
                           action='Loading Session.......',
                           port=str(port-1),
                           password='password')

    # Delete a container

    @cherrypy.expose
    @require()
    def delete(self, container):
        cli.remove_image(container)
        tmpl = lookup.get_template("redirect.html")
        return tmpl.render(url='/', wait='4', action='Removing Image')

    # Reboot a container

    @cherrypy.expose
    @require()
    def reboot(self, pubport):
        cli.restart(getcontainerbyport(pubport)['Id'])
        tmpl = lookup.get_template("connect.html")
        return tmpl.render(wait='4',
                           action='Rebooting Container',
                           port=str(port-1),
                           password='password')

    # Remove and start a fresh container from the same image

    @cherrypy.expose
    @require()
    def reset(self, pubport):
        cid = getcontainerbyport(pubport)
        cli.remove_container(container=cid['Id'], force=True)
        container = cli.create_container(image=cid['Image'],
                                         ports=[6081],
                                         host_config=cli.create_host_config(
                                             port_bindings={6081: pubport}))
        cli.start(container=container.get('Id'))
        tmpl = lookup.get_template("connect.html")
        return tmpl.render(wait='10',
                           action='Resetting Container',
                           port=str(port-1),
                           password='password')

    # End the session but leave the container running

    @cherrypy.expose
    @require()
    def endsession(self, pubport):
        cid = getcontainerbyport(pubport)
        iid = cli.inspect_image(cid['Image'])
        try:
            info = json.loads(cli.inspect_image(cid['Image'])['Comment'])
        except Exception as e:
            info = json.loads('{"Name": "Unnamed Image",' +
                              '"Desc": "Undescribed Image"}')
        tmpl = lookup.get_template("endsession.html")
        return tmpl.render(port=pubport, name=info['Name'], desc=info['Desc'])

    # Display the metadata form for saving to a user image

    @cherrypy.expose
    @require()
    def saveinst(self, pubport):
        cid = getcontainerbyport(pubport)
        iid = cli.inspect_image(cid['Image'])
        try:
            info = json.loads(cli.inspect_image(cid['Image'])['Comment'])
        except Exception as e:
            info = json.loads('{"Name": "Unnamed Image",' +
                              '"Desc": "Undescribed Image"}')
        tmpl = lookup.get_template("save.html")
        return tmpl.render(port=pubport, name=info['Name'], desc=info['Desc'])

    # Save the container as a new user image

    @cherrypy.expose
    @require()
    def save(self, pubport, name, desc):
        sess = cherrypy.session
        username = cherrypy.session.get(SESSION_KEY)
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
        tmpl = lookup.get_template("redirect.html")
        return tmpl.render(url='/', wait='4', action='Saving Container')

    # Display the metadata form for promoting to base image
    # Requires ADMIN group

    @cherrypy.expose
    @require(member_of('admin'))
    def promote(self, sourcename):
        try:
            info = json.loads(cli.inspect_image(sourcename))
        except Exception as e:
            info = json.loads('{"Name": "Unnamed Image",' +
                              '"Desc": "Undescribed Image"}')
        tmpl = lookup.get_template("promote.html")
        return tmpl.render(repo=sourcename,
                           reponame=sourcename.split(
                               ':')[1].split("-")[1],
                           name=info['Name'],
                           desc=info['Desc'])

    # tags an image as a base image
    # requires ADMIN group

    @cherrypy.expose
    @require(member_of('admin'))
    def commit(self, repo, reponame, name, desc):
        cli.tag(image=repo, repository="dockerlab", tag=reponame, force=True)
        tmpl = lookup.get_template("redirect.html")
        return tmpl.render(url='/', wait='4', action='Committing Image.')

    # Removes a running container

    @cherrypy.expose
    @require()
    def destroy(self, pubport):
        cid = getcontainerbyport(pubport)
        cli.remove_container(container=cid['Id'], force=True)
        tmpl = lookup.get_template("redirect.html")
        return tmpl.render(url='/', wait='4', action='Destroying Container')

    # Downloads a copy of the running containers /home directory

    @cherrypy.expose
    @require()
    @mimetype('application/x-tar')
    def downloadhome(self, pubport):
        cid = getcontainerbyport(pubport)
        name = cid['Names'][0].replace('/', '')
        filename = 'attachment; filename="' + name + '_homedir.tar"'
        hometar = cli.copy(container=cid['Id'], resource='/home')
        cherrypy.response.headers['Content-Disposition'] = filename
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


cherrypy.quickstart(DockerLab())
