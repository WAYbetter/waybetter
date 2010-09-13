from models import Order
from dbindexer.api import register_index
import logging

logging.info("registering index")
register_index(Order, {'from_raw': 'icontains', 'to_raw': 'icontains'})