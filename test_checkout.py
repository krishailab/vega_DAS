import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.api.b2b_order_api import B2BOrderOperations

try:
    user_id = "krish@vegaauto.in"
    address_id = "ADDR-26042309509"
    res = B2BOrderOperations.get_checkout_summary(user_id, address_id, coupon_code="")
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
