import json
import hashlib
import base64
from docker import Client

cli = Client(base_url='unix://var/run/docker.sock')


class User(object):

    authDB = []

    def __init__(self):
        self.authDB = self.getdatabase()

    def getdatabase(self):
        container = cli.images('dockerlabconfig:auth')
        if container:
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        else:
            self.createdatabase()
            container = cli.images('dockerlabconfig:auth')
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        return info

    def createdatabase(self):
            nullimageenc = 'H4sIADODtVYAA+3PMQ6CQBAF0D3K3kB2V5bzmGhHIEHw' \
                           '/BLUxkIrbHyv+ZPMFH/Ol9thWPo+7KhZ1Vq3XL3nNqdc' \
                           '2zanklIXmpSPXQmx7FnqZbnOpynGMI3j/Onu2/7xR3rm' \
                           'T6oDAAAAAAAAAADwv+7c8q/OACgAAA=='
            nullimage = base64.b64decode(nullimageenc)
            cli.import_image_from_data(nullimage, 'dockerlabconfig', 'auth')
            newcontainer = cli.create_container('dockerlabconfig:auth',
                                                '/dev/null')
            passhasher = hashlib.sha256()
            passhasher.update("notsecret")
            passhash = passhasher.hexdigest()
            dbinit = {}
            dbinit['admin'] = {}
            dbinit['admin']['password'] = passhash
            dbinit['admin']['security'] = 'admin'
            dbinit['admin']['comment'] = 'Default ADMIN account'
            dbinit['user'] = {}
            dbinit['user']['passowrd'] = passhash
            dbinit['user']['security'] = 'user'
            dbinit['user']['comment'] = 'Default USER account'
            cli.commit(newcontainer['Id'],
                       'dockerlabconfig',
                       'auth',
                       json.dumps(dbinit))
            cli.remove_container(newcontainer['Id'])

    def checkuserpass(self, username, password):
        if username in self.authDB.keys():
            passhasher = hashlib.sha256()
            passhasher.update(password)
            passhash = passhasher.hexdigest()
            if passhash == self.authDB[username]['password']:
                return None
            else:
                return u"Incorrect username or password"
        else:
            return u"Incorrect username or password."
