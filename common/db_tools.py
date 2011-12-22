import logging
from django.db.models.fields import related
from django.db.models.fields.related import ForeignKey, OneToOneField
from billing.models import BillingInfo
from ordering.models import Passenger

def merge_passenger(master_p):
    def get_reverse_props(entity, related_entity):
        res = []
        for f in related_entity._meta.fields:
            if type(f) in [ForeignKey, OneToOneField] and f.related.parent_model == type(entity):
                res.append(f)

        return res

    def set_master_p(passenger, related_instance):
        passengers_fields = get_reverse_props(passenger, related_instance)
        for passenger_field in passengers_fields:
            related_passenger = getattr(related_instance, passenger_field.name)
            if related_passenger == passenger:
                logging.info("changing %s[%s].%s" % (related_instance._meta.object_name, related_instance.id, passenger_field.name))
                #setattr(related_instance, passenger_field.name, master_p)
                #related_instance.save()

    passengers = list(Passenger.objects.filter(phone=master_p.phone))
    passengers.remove(master_p)

    logging.info("*** merging passenger: %s --> %s" % (passengers, master_p))

    all_related_objects = get_all_related_objects(Passenger)

    for passenger in passengers:
        logging.info("--- merging %s ---" % passenger)
        for ro in all_related_objects:
            accessor_name = ro.get_accessor_name()
            try:
                field = getattr(passenger, accessor_name)
            except Exception, e:
                logging.info(e.message)
                continue

            relation_type = type(getattr(Passenger, accessor_name))
            if relation_type == related.SingleRelatedObjectDescriptor:
                set_master_p(passenger, field)
            else:
                for entity in field.all():
                    set_master_p(passenger, entity)

    for passenger in passengers:
        try:
            logging.info("Deleting %s" % passenger.billing_info)
            #passenger.billing_info.delete()
        except BillingInfo.DoesNotExist:
            pass
        logging.info("Deleting %s" % passenger)
        #passenger.delete()

    logging.info("*** end merge ***")



def deep_relate_object(o, level=0):
    def _print(s):
        indent = "\t" * level
        print("%s%s" % (indent, s))

    model = type(o)
    all_related_objects = get_all_related_objects(model)
    print("\n")
    _print("--- %s[%s] ---" % (model._meta.object_name, o.id))

    for ro in all_related_objects:
        _print("%s" % ro.name)
        accessor_name = ro.get_accessor_name()
        try:
            prop = getattr(o, accessor_name)
        except Exception, e:
            continue

        relation_type = type(getattr(model, accessor_name))
        if relation_type == related.SingleRelatedObjectDescriptor:
            deep_relate_object(prop, level + 1)
        else:
            for entity in prop.all():
                deep_relate_object(entity, level + 1)


def get_all_related_objects(model):
    related = model._meta.get_all_related_objects()
    return related
