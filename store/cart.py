from decimal import Decimal
from django.conf import settings
from .models import Product, CartItem, Coupon
import copy
from django.utils import timezone

class Cart:
    def __init__(self, request):
        self.session = request.session
        self.request = request
        cart = self.session.get('cart_session_id')
        if not cart:
            cart = self.session['cart_session_id'] = {}
        self.cart = cart
        
        # كود الكوبون
        self.coupon_id = self.session.get('coupon_id')

        # إذا كان المستخدم مسجلاً، قم بجلب السلة من قاعدة البيانات ودمجها
        if self.request.user.is_authenticated:
            self.merge_db_cart()

    def merge_db_cart(self):
        db_items = CartItem.objects.filter(user=self.request.user)
        for item in db_items:
            product_id = str(item.product.id)
            if product_id not in self.cart:
                self.cart[product_id] = {
                    'quantity': item.quantity, 
                    'price': str(item.product.final_price)
                }
        self.save_session()

    def add(self, product, quantity=1, update_quantity=False):
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {'quantity': 0, 'price': str(product.final_price)}
        
        if update_quantity:
            self.cart[product_id]['quantity'] = quantity
        else:
            self.cart[product_id]['quantity'] += quantity
        
        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self):
        self.save_session()
        if self.request.user.is_authenticated:
            self.sync_db()

    def save_session(self):
        self.session.modified = True

    def sync_db(self):
        user = self.request.user
        current_product_ids = []
        for product_id, item_data in self.cart.items():
            current_product_ids.append(product_id)
            product = Product.objects.get(id=product_id)
            cart_item, created = CartItem.objects.get_or_create(
                user=user, 
                product=product
            )
            cart_item.quantity = item_data['quantity']
            cart_item.save()
        CartItem.objects.filter(user=user).exclude(product__id__in=current_product_ids).delete()

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        # نستخدم deepcopy لتجنب خطأ JSON
        cart_copy = copy.deepcopy(self.cart)

        for product in products:
            cart_copy[str(product.id)]['product'] = product
        
        for item in cart_copy.values():
            item['price'] = Decimal(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    # --- الدوال الحسابية (تأكد من وجودها) ---

    def get_total_price(self):
        """حساب مجموع المنتجات قبل الخصم"""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    @property
    def coupon(self):
        """جلب الكوبون الحالي"""
        if self.coupon_id:
            try:
                return Coupon.objects.get(id=self.coupon_id)
            except Coupon.DoesNotExist:
                pass
        return None

    def get_discount(self):
        """حساب قيمة الخصم"""
        if self.coupon:
            return (self.coupon.discount / Decimal(100)) * self.get_total_price()
        return Decimal(0)

    def get_total_price_after_discount(self):
        """حساب المجموع النهائي بعد الخصم"""
        return self.get_total_price() - self.get_discount()
        
    def clear(self):
        """تفريغ السلة تماماً"""
        if 'coupon_id' in self.session:
            del self.session['coupon_id']
            
        del self.session['cart_session_id']
        self.save_session()
        
        if self.request.user.is_authenticated:
            CartItem.objects.filter(user=self.request.user).delete()