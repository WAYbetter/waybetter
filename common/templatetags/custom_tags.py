import urlparse
from django import template
from django.conf import settings
from django.template.defaulttags import url, URLNode

register = template.Library()
class AbsoluteURLNode(URLNode):
    def render(self, context):
        path = super(AbsoluteURLNode, self).render(context)
        schema = "http"
        for d in context.dicts:
            request = d.get("request")
            if request:
                server_protocol = request.META.get("SERVER_PROTOCOL")
                if server_protocol:
                    schema = server_protocol.split("/")[0].lower()
                    break


        domain = "%s://%s" % (schema, settings.DEFAULT_DOMAIN)
        return urlparse.urljoin(domain, path)

def absurl(parser, token, node_cls=AbsoluteURLNode):
    """Just like {% url %} but ads the domain of the current site."""
    node_instance = url(parser, token)
    return node_cls(view_name=node_instance.view_name,
        args=node_instance.args,
        kwargs=node_instance.kwargs,
        asvar=node_instance.asvar)
absurl = register.tag(absurl)
