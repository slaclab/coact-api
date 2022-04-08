
from functools import wraps

import logging

class Authnz():

    LOG = logging.getLogger(__name__)
    
    def authentication_required(self, wrapped_function):
        @wraps(wrapped_function)
        def function_interceptor(*args, **kwargs):
            info = kwargs["info"]
            self.LOG.debug(info.path.key)
            info.context.authn()
            return wrapped_function(*args, **kwargs)
        return function_interceptor
        
    def authorization_required(self, *params):
        if len(params) < 1:
            raise Exception("Application privilege not specified when specifying the authorization")
        priv_name = params[0]
        def wrapper(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                info = kwargs["info"]
                self.LOG.debug("Looking to authorize {info.context.user} for privilege {priv_name} for repo {info.context.repo}")
                return f(*args, **kwargs)
            return wrapped
        return wrapper
        
    def check_repo(self, wrapped_function):
        @wraps(wrapped_function)
        def function_interceptor(*args, **kwargs):
            info = kwargs["info"]
            if info.path.key.startswith("repo"):
                info.context.repo = kwargs["name"]
                self.LOG.debug(f"Setting repo to {info.context.repo}")
            return wrapped_function(*args, **kwargs)
        return function_interceptor

