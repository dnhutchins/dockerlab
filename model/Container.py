import json
import hashlib
import base64
import zlib
from docker import Client

cli = Client(base_url='unix://var/run/docker.sock')


class Container(object):

    containerDB = {}

    def __init__(self):
        self.containerDB = self.getdatabase()

    def getdatabase(self):
        container = cli.images('dockerlabconfig:container')
        if container:
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        else:
            self.createdatabase()
            self.writedatabase()
            container = cli.images('dockerlabconfig:container')
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        return info

    def createdatabase(self):
        nullimageenc = 'H4sIADODtVYAA+3PMQ6CQBAF0D3K3kB2V5bzmGhHIEHw' \
                       '/BLUxkIrbHyv+ZPMFH/Ol9thWPo+7KhZ1Vq3XL3nNqdc' \
                       '2zanklIXmpSPXQmx7FnqZbnOpynGMI3j/Onu2/7xR3rm' \
                       'T6oDAAAAAAAAAADwv+7c8q/OACgAAA=='
        nullimage = base64.b64decode(nullimageenc)
        cli.import_image_from_data(zlib.decompress(nullimage,
                                                   16 + zlib.MAX_WBITS),
                                   'dockerlabconfig',
                                   'container')

    def writedatabase(self):
        newcontainer = cli.create_container('dockerlabconfig:container',
                                            '/dev/null')
        cli.commit(newcontainer['Id'],
                   'dockerlabconfig',
                   'container',
                   json.dumps(self.containerDB))
        cli.remove_container(newcontainer['Id'])

    def getcontainer(self, username, cid):
        containers = self.getcontainers(username)
        if cid in containers.keys():
            return containers[cid]
        else:
            return False

    def getcontainers(self, username):
        if username in self.containerDB.keys():
            return self.containerDB[username]
        else:
            return {}

    def addcontainer(self, username, cid, port, vnckey):
        containers = self.getcontainers(username)
        container = {}
        container['port'] = port
        container['vnckey'] = vnckey
        if not containers:
            self.containerDB[username] = {}
            containers = self.containerDB[username]
        containers[cid] = container
        self.writedatabase()
        return True

    def removecontainer(self, username, cid):
        if username in self.containerDB.keys():
            if cid in self.containerDB[username].keys():
                del self.containerDB[username][cid]
                self.writedatabase()
                return True
        return False

    def setvncpassword(self, username, cid, vnckey):
        if username in self.containerDB.keys():
            if cid in self.containerDB[username].keys():
                self.containerDB[username][cid]['vnckey'] = vnckey
                self.writedatabase()
                return True
        return False

    def getport(self, username, cid):
        self.containerDB = self.getdatabase()
        containers = self.getcontainers(username)
        if containers:
            if cid in containers.keys():
                return containers[cid]['port']
        return False
