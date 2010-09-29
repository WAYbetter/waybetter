# Copyright 2009 Tim Savage <tim.savage@jooceylabs.com>
# See LICENSE for licence information

from django import template

from ajax_forms.utils import form_to_json

register = template.Library()


class RenderAjaxFieldsNode(template.Node):

    def __init__(self, form):
        super(RenderAjaxFieldsNode, self).__init__()
        self.form = template.Variable(form)

    def render(self, context):
        form = self.form.resolve(context)
        return form_to_json(form)


class AsDlNode(template.Node):

    def __init__(self, form, seperate_errors):
        super(AsDlNode, self).__init__()
        self.form = template.Variable(form)
        self.seperate_errors = seperate_errors

    def render(self, context):
        form = self.form.resolve(context)
        return form._html_output(u'<dt>%(label)s</dt><dd>%(field)s%(help_text)s%(errors)s</dd>', u'<li>%s</li>', '</dd>', u' %s', self.seperate_errors)


def do_render_ajax_fields(parser, token):
    """
    This will render a Django form into an ajax.

    Usage::

        {% render_ajax_form form %}

    """
    try:
        tag_name, form = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument"
            % token.contents.split()[0])
    return RenderAjaxFieldsNode(form)


def do_as_dl(parser, token):
    """
    Render form as a dl construct

    Usage::

        {% as_dl form %}

    """
    contents = token.split_contents()
    try:
        form = contents[1]
    except IndexError:
        raise template.TemplateSyntaxError("%r tag requires at leaset a form argument"
            % contents[0])
    try:
        seperate_errors = contents[2] == 'True'
    except IndexError:
        seperate_errors = False
    
    return AsDlNode(form, seperate_errors)

register.tag('render_ajax_fields', do_render_ajax_fields)
register.tag('as_dl', do_as_dl)
