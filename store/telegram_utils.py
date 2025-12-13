import requests

def send_telegram_order(order):
    # -------------------------------------------------------
    # استبدل القيم التالية بالتي حصلت عليها من تلجرام
    BOT_TOKEN = '7846123604:AAG3hHxQMp8be71opByo6v5rKNiAqdsL7Us'
    CHAT_ID = '6656634781'
    # -------------------------------------------------------

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # حساب مجموع المنتجات فقط (بدون توصيل وخصم) للعرض
    # الإجمالي النهائي = (مجموع المنتجات - الخصم) + التوصيل
    # إذن مجموع المنتجات = الإجمالي النهائي - التوصيل + الخصم
    subtotal = order.total_amount - order.delivery_fee + order.discount_amount

    message = f"""
📦 <b>طلب جديد #{order.id}</b>
------------------------
👤 <b>العميل:</b> {order.full_name}
📱 <b>الهاتف:</b> {order.phone}
📍 <b>العنوان:</b> {order.address}
------------------------
💵 <b>مجموع المنتجات:</b> {subtotal:,.0f} د.ع
🚚 <b>التوصيل:</b> {order.delivery_fee:,.0f} د.ع
"""

    # إضافة سطر الخصم فقط إذا وجد
    if order.discount_amount > 0:
        coupon_code = order.coupon.code if order.coupon else "كود"
        message += f"🏷 <b>خصم ({coupon_code}):</b> -{order.discount_amount:,.0f} د.ع\n"

    message += f"""------------------------
💰 <b>الإجمالي النهائي: {order.total_amount:,.0f} د.ع</b>

🔗 <a href="http://172.16.0.21:8000/dashboard/orders/{order.id}/">عرض التفاصيل في اللوحة</a>
"""

    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }

    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram Error: {e}")