from .cart import Cart
from .models import Category


def cart_processor(request):
    return {'cart': Cart(request)}


def categories_processor(request):
    # نجلب فقط الفئات الرئيسية (التي ليس لها أب)
    # ونستخدم prefetch_related لجلب الأبناء معها لتسريع الموقع
    main_categories = Category.objects.filter(parent=None).prefetch_related('children')
    return {'nav_categories': main_categories}