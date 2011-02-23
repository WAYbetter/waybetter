from common.util import blob_to_image_tag
from django.template import Library
register = Library()

@register.simple_tag
def blob_to_img(blob_data):
    return blob_to_image_tag(blob_data)