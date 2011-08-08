from django import template

register = template.Library()

def divide(value, arg):
    return float(value)/float(arg)

register.filter('divide', divide)
