import json
import hashlib
import base64
import zlib
from docker import Client

cli = Client(base_url='unix://var/run/docker.sock')


class User(object):

    userDB = {}

    def __init__(self):
        self.userDB = self.getdatabase()

    def getdatabase(self):
        container = cli.images('dockerlabconfig:auth')
        if container:
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        else:
            self.createdatabase()
            self.initdatabase()
            container = cli.images('dockerlabconfig:auth')
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
                                   'auth')

    def initdatabase(self):
        self.adduser('admin', 'notsecret', 'admin', 'Default ADMIN account.')
        self.adduser('user', 'notsecret', 'user', 'Default USER account.')

    def writedatabase(self):
        newcontainer = cli.create_container('dockerlabconfig:auth',
                                            '/dev/null')
        cli.commit(newcontainer['Id'],
                   'dockerlabconfig',
                   'auth',
                   json.dumps(self.userDB))
        cli.remove_container(newcontainer['Id'])

    def checkuserpass(self, username, password):
        user = self.getuser(username)
        if user:
            passhasher = hashlib.sha256()
            passhasher.update(password)
            passhash = passhasher.hexdigest()
            if passhash == user['password']:
                return False
            else:
                return u"Incorrect username or password"
        else:
            return u"Incorrect username or password."

    def adduser(self, username, password, group, comment):
        if self.getuser(username):
            return False
        else:
            userrecord = {}
            userrecord['group'] = group
            userrecord['comment'] = comment
            self.userDB[username] = {}
            self.userDB[username] = userrecord
            self.setpassword(username, password)
            return True

    def changepassword(self, username, oldpassword, newpassword):
        user = self.getuser(username)
        if user:
            passhasher = hashlib.sha256()
            passhasher.update(oldpassword)
            passhash = passhasher.hexdigest()
            if passhash == user['password']:
                self.setpassword(username, newpassword)
            else:
                return u"Incorrect old password"
        else:
            return u"Incorrect old password"

    def setpassword(self, username, password):
        if self.getuser(username):
            passhasher = hashlib.sha256()
            passhasher.update(password)
            passhash = passhasher.hexdigest()
            self.userDB[username]['password'] = passhash
            self.writedatabase()
            return True
        else:
            return False

    def getuser(self, username):
        if username in self.userDB.keys():
            return self.userDB[username]
        else:
            return False

    def deleteuser(self, username):
        if getuser(username):
            del userDB[username]
            self.writedatabase()
            return True
        else:
            return False
