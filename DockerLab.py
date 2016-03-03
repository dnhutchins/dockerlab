#!/usr/bin/python

# DockerLab is a play on Virtualized Desktop Infrastructure (VDI)
# using docker containers. The goal of DockerLab is to provide a
# lightweight environment where workload specific desktop images
# can be created, modified, and shared between a working group
# of users. In the spirit of lightness, DockerLab doesn't use any
# datastore other than Docker itself. Image metadata is stored
# directly in the comment field of the image as a JSON object

import threading
import cherrypy
import socket
import sys
import json
import os
from docker import Client
from mako.template import Template
from mako.lookup import TemplateLookup
from controller.AuthController import (AuthController,
                                       require,
                                       member_of,
                                       name_is)
from controller.DockerController import DockerController
from controller.WebsockifyToken import WebsockifyToken
from lib.websockify.websocketproxy import WebSocketProxy

SESSION_KEY = '_cp_username'
SESSION_DIR = '/opt/dockerlab/sessions'
lookup = TemplateLookup(directories=['view'])
cli = Client(base_url='unix://var/run/docker.sock')
port = 6000

websocket_proxy_server = WebSocketProxy(listen_host='', listen_port='6000', token_plugin=WebsockifyToken())
websocket_thread = threading.Thread(target=websocket_proxy_server.start_server, args=())
websocket_thread.daemon = True
websocket_thread.start()

if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)


# Decorator to designate mime type

def mimetype(type):
    def decorate(func):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = type
            return func(*args, **kwargs)
        return wrapper
    return decorate


def handle_error():
    tmpl = lookup.get_template('error.html')
    cherrypy.response.status = 500
    cherrypy.response.body = [
        tmpl.render()
    ]


class DockerLab(object):

    _cp_config = {
        'tools.sessions.on': True,
        'tools.sessions.storage_type': 'file',
        'tools.sessions.storage_path': SESSION_DIR,
        'tools.auth.on': True,
        'tools.proxy.on': True,
        'tools.proxy.local': 'X-Forwarded-Host',
        'tools.proxy.local': 'Host',
        'request.error_response': handle_error
    }

    auth = AuthController()
    docker = DockerController()

    @cherrypy.expose
    @require()
    def index(self):
        sess = cherrypy.session
        username = cherrypy.session.get(SESSION_KEY)
        runningimages = self.docker.getrunningcontainers(username)
        runningcount = len(runningimages)
        baseimages = self.docker.getbaseimages()
        savedcount = len(baseimages)
        userimages = self.docker.getuserimages(username)
        savedcount += len(userimages)
        admin = self.auth.isadmin(username)
        tmpl = lookup.get_template('index.html')
        return tmpl.render(baseimages=baseimages,
                           userimages=userimages,
                           runningimages=runningimages,
                           runningcount=runningcount,
                           savedcount=savedcount,
                           username=username,
                           admin=admin)

    # Launch a new container
    #
    # Public port availability gets checked at launch time.
    # Ports that are already in use get skipped until
    # the next available port is found. This maintains ligntness
    # by not managing a port mapping in an unnecessary data structure.

    @cherrypy.expose
    @require()
    def launch(self, container):
        cid = self.docker.launchcontainer(cherrypy.session.get(SESSION_KEY), container)
        tmpl = lookup.get_template('connect.html')
        return tmpl.render(wait='4',
                           action='Loading Session.......',
                           cid=str(cid),
                           password='password')

    # Connect to a container

    @cherrypy.expose
    @require()
    def connect(self, cid):
        username = cherrypy.session.get(SESSION_KEY)
        password = str(os.urandom(32).encode('hex'))[0:32]
        self.docker.setvncpassword(username, cid, password)
        path = '/getstream/getstream/websockify'
        token = username + ':' + cid
        tmpl = lookup.get_template('vnc.html')
        return tmpl.render(password=password,
                           path=path,
                           token=token)

    # Delete a container

    @cherrypy.expose
    @require()
    def delete(self, cid):
        username = cherrypy.session.get(SESSION_KEY)
        self.docker.deletecontainer(username, cid)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Removing Image')

    # Reboot a container

    @cherrypy.expose
    @require()
    def reboot(self, cid):
        username = cherrypy.session.get(SESSION_KEY)
        self.docker.rebootcontainer(cid)
        password = str(os.urandom(32).encode('hex'))[0:32]
        self.docker.setvncpassword(username, cid, password)
        tmpl = lookup.get_template('connect.html')
        return tmpl.render(wait='4',
                           action='Rebooting Container',
                           cid=cid,
                           password=password)

    # End the session but leave the container running

    @cherrypy.expose
    @require()
    def endsession(self, cid):
        info = self.docker.getimagemetadata(cid)
        tmpl = lookup.get_template('endsession.html')
        return tmpl.render(cid=cid, name=info['Name'], desc=info['Desc'])

    # Display the metadata form for saving to a user image

    @cherrypy.expose
    @require()
    def saveinst(self, cid):
        info = self.docker.getimagemetadata(cid)
        tmpl = lookup.get_template('save.html')
        return tmpl.render(cid=cid, name=info['Name'], desc=info['Desc'])

    # Save the container as a new user image

    @cherrypy.expose
    @require()
    def save(self, cid, name, desc):
        sess = cherrypy.session
        username = cherrypy.session.get(SESSION_KEY)
        self.docker.saveimage(username, cid, name, desc)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Saving Container')

    # Display the metadata form for promoting to base image
    # Requires ADMIN group

    @cherrypy.expose
    @require(member_of('admin'))
    def promote(self, sourcename):
        info = self.docker.getimagemetadata(0, sourcename)
        tmpl = lookup.get_template('promote.html')
        return tmpl.render(repo=sourcename,
                           reponame=sourcename.split(
                               ':')[1].split('-')[1],
                           name=info['Name'],
                           desc=info['Desc'])

    # tags an image as a base image
    # requires ADMIN group

    @cherrypy.expose
    @require(member_of('admin'))
    def commit(self, repo, reponame, name, desc):
        self.docker.commitimage(repo, reponame, name, desc)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Committing Image.')

    # Removes a running container

    @cherrypy.expose
    @require()
    def destroy(self, cid):
        username = cherrypy.session.get(SESSION_KEY)
        self.docker.destroycontainer(username, cid)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Destroying Container')

    # Downloads a copy of the running containers /home directory

    @cherrypy.expose
    @require()
    @mimetype('application/x-tar')
    def downloadhome(self, cid):
        hometar = self.docker.getcontainerhome(cid)
        cherrypy.response.headers['Content-Disposition'] = hometar['filename']
        return hometar['data']

    @cherrypy.expose
    @require(member_of('admin'))
    def adduser(self):
        tmpl = lookup.get_template('adduser.html')
        return tmpl.render()

    @cherrypy.expose
    @require(member_of('admin'))
    def commituser(self, username, password, comment, admin=''):
        adminflag = False
        if admin == 'true':
            adminflag = True
        self.auth.adduser(username, password, comment, adminflag)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Creating User')

    @cherrypy.expose
    @require()
    def changepassword(self):
        tmpl = lookup.get_template('changepassword.html')
        return tmpl.render()

    @cherrypy.expose
    @require()
    def commitchangepassword(self, oldpassword, newpassword):
        username = cherrypy.session.get(SESSION_KEY)
        self.auth.changepassword(username, oldpassword, newpassword)
        tmpl = lookup.get_template('redirect.html')
        return tmpl.render(url='/', wait='4', action='Changing Password')


cherrypy.quickstart(DockerLab())
