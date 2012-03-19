from suds.client import *

class GAEClient(Client):
    def __init__(self, url, **kwargs):
        """
        @param url: The URL for the WSDL.
        @type url: str
        @param kwargs: keyword arguments.
        @see: L{Options}
        """
        options = Options()
        options.transport = HttpAuthenticated()
        self.options = options

        options.cache = NoCache() #patch: appengine
#        options.cache = ObjectCache(days=1)

        self.set_options(**kwargs)
        reader = DefinitionsReader(options, Definitions)
        self.wsdl = reader.open(url)
        plugins = PluginContainer(options.plugins)
        plugins.init.initialized(wsdl=self.wsdl)
        self.factory = Factory(self.wsdl)
        self.service = ServiceSelector(self, self.wsdl.services)
        self.sd = []
        for s in self.wsdl.services:
            sd = ServiceDefinition(self.wsdl, s)
            self.sd.append(sd)
        self.messages = dict(tx=None, rx=None)

