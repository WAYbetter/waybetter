from common.util import safe_fetch
from django.template.loader import get_template
from settings import BUILD_SERVICE_BASE_URL
from urllib import urlencode

PDF_SERVICE_URL = BUILD_SERVICE_BASE_URL + "html_to_pdf/"

def convert_to_pdf(html):
    """
    Using C{PDF_SERVICE_URL}, convert the given html to pdf

    @param html: the html will be encoded to C{utf-8}
    @return: the converted document
    """
    res = safe_fetch(PDF_SERVICE_URL, payload=urlencode({"html": html.encode("utf-8")}), method="POST")
    return res.content if res else None

def template_to_pdf(template_name, context):
    """
    Render template html and the convert it to PDF

    @param template_name:
    @param context: used for template rendering
    @return: the converted document
    """

    t = get_template(template_name)
    html = t.render(context)

    return convert_to_pdf(html)

