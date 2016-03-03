import os
from model.Container import Container


class WebsockifyToken(object):
    # source is a token file with lines like
    #   token: host:port
    # or a directory of such files
    def __init__(self, *args, **kwargs):
        self.containers = Container()

    def lookup(self, token):
        username = token.split(":")[0]
        cid = token.split(":")[1]
        port = self.containers.getport(username, cid)
        
        if port:
            return ('127.0.0.1', port)
        else:
            return None


