import os
from model.Container import Container


class WebsockifyToken(object):
    # gets port from Container model from the
    # username and container Id from the token
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
