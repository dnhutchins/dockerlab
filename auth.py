import cherrypy

from mako.template import Template
from mako.lookup import TemplateLookup
from docker import Client
import json
import base64
import hashlib

lookup = TemplateLookup(directories=['templates'])
SESSION_KEY = '_cp_username'
cli = Client(base_url='unix://var/run/docker.sock')


def check_auth(*args, **kwargs):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('auth.require', None)
    if conditions is not None:
        username = cherrypy.session.get(SESSION_KEY)
        if username:
            cherrypy.request.login = username
            for condition in conditions:
                # A condition is just a callable that returns true or false
                if not condition():
                    raise cherrypy.HTTPRedirect("/auth/login")
        else:
            raise cherrypy.HTTPRedirect("/auth/login")

cherrypy.tools.auth = cherrypy.Tool('before_handler', check_auth)


def require(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


# Conditions are callables that return True
# if the user fulfills the conditions they define, False otherwise
#
# They can access the current username as cherrypy.request.login
#
# Define those at will however suits the application.

def member_of(groupname):
    def check():
        # replace with actual check if <username> is in <groupname>
        return cherrypy.request.login == 'joe' and groupname == 'admin'
    return check


def name_is(reqd_username):
    return lambda: reqd_username == cherrypy.request.login

# These might be handy


def any_of(*conditions):
    """Returns True if any of the conditions match"""
    def check():
        for c in conditions:
            if c():
                return True
        return False
    return check


# By default all conditions are required, but this might still be
# needed if you want to use it inside of an any_of(...) condition

def all_of(*conditions):
    """Returns True if all of the conditions match"""
    def check():
        for c in conditions:
            if not c():
                return False
        return True
    return check


# Controller to provide login and logout actions

class AuthController(object):

    authDB = []

    def __init__(self):
        self.authDB = self.getdatabase()

    # This will load the existing database from the null
    # image dockerlabconfig:auth If the image doesn't exist
    # a new image is created, started, and then committed
    # with a the default admin account

    def getdatabase(self):
        try:
            container = cli.images('dockerlabconfig:auth')
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        except Exception as e:
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
            container = cli.images('dockerlabconfig:auth')
            info = json.loads(cli.inspect_image(container[0]['Id'])['Comment'])
        return info

    def check_credentials(self, username, password):
        """Verifies credentials for username and password.
        Returns None on success or a string describing the error on failure"""
        # Adapt to your needs
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

        # An example implementation which uses an ORM could be:
        # u = User.get(username)
        # if u is None:
        #     return u"Username %s is unknown to me." % username
        # if u.password != md5.new(password).hexdigest():
        #     return u"Incorrect password"

    def on_login(self, username):
        """Called on successful login"""

    def on_logout(self, username):
        """Called on logout"""

    def get_loginform(self,
                      username,
                      msg="Enter login information",
                      from_page="/"):
        tmpl = lookup.get_template("login.html")
        return tmpl.render(from_page=from_page, msg=msg)
        return """<html><body>
         <form method="post"
               action="/auth/login">
         <input type="hidden"
                name="from_page"
                value="%(from_page)s"/>
         %(msg)s<br/>
         Username: <input type="text"
                          name="username"
                          value="%(username)s"/><br/>
         Password: <input type="password"
                          name="password"/><br/>
         <input type="submit"
                value="Log in"/>
        </body></html>""" % locals()

    @cherrypy.expose
    def login(self, username=None, password=None, from_page="/"):
        if username is None or password is None:
            return self.get_loginform("", from_page=from_page)

        error_msg = self.check_credentials(username, password)
        if error_msg:
            return self.get_loginform(username, error_msg, from_page)
        else:
            cherrypy.session[SESSION_KEY] = cherrypy.request.login = username
            self.on_login(username)
            raise cherrypy.HTTPRedirect(from_page or "/")

    @cherrypy.expose
    def logout(self, from_page="/"):
        sess = cherrypy.session
        username = sess.get(SESSION_KEY, None)
        sess[SESSION_KEY] = None
        if username:
            cherrypy.request.login = None
            self.on_logout(username)
        raise cherrypy.HTTPRedirect(from_page or "/")
