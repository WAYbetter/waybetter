from pricing.models import Promotion, DiscountRule, PromoCode
import datetime

class DiscountData:
    pickup_dt = None
    discount_rule = None
    promotion = None
    promo_code = None

    def __init__(self, pickup_dt, discount_rule, promotion=None, promo_code=None):
        if not isinstance(pickup_dt, datetime.datetime):
            raise TypeError("pickup_dt must be a datetime instance")
        if not isinstance(discount_rule, DiscountRule):
            raise TypeError("discount_rule must be a DiscountRule instance")
        if promotion and not promo_code:
            raise ValueError("promo_code is required when setting promotion")
        if promo_code and not promotion:
            raise ValueError("promotion is required when setting promo_code")

        self.pickup_dt = pickup_dt
        self.discount_rule = discount_rule
        self.promotion = promotion
        self.promo_code = promo_code

    @staticmethod
    def dump(inst):
        return {
            'pickup_dt': inst.pickup_dt,
            'discount_rule_id': inst.discount_rule.id,
            'promotion_id': inst.promotion.id if inst.promotion else None,
            'promo_code_id': inst.promo_code.id if inst.promo_code else None
        }

    @classmethod
    def load(cls, dump_data):
        pickup_dt = dump_data.get('pickup_dt')
        discount_rule = DiscountRule.by_id(dump_data.get('discount_rule_id'))

        promotion_id = dump_data.get('promotion_id')
        promo_code_id = dump_data.get('promo_code_id')

        promotion = Promotion.by_id(promotion_id)
        promo_code = PromoCode.by_id(promo_code_id)

        if promotion_id and not promotion:
            raise Promotion.DoesNotExist("id = %s" % promotion_id)
        if promo_code_id and not promo_code:
            raise PromoCode.DoesNotExist("id = %s" % promo_code_id)

        return cls(pickup_dt, discount_rule, promotion=promotion, promo_code=promo_code)
