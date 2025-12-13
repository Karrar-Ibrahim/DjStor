from django import template

register = template.Library()

@register.filter(name='currency')
def currency(value):
    try:
        # تحويل القيمة إلى رقم عشري ثم صحيح لإزالة الكسور
        value = int(float(value))
        # استخدام دالة بايثون الأصلية لإضافة الفواصل
        return "{:,}".format(value)
    except (ValueError, TypeError):
        return value
    
@register.filter
def range_loop(number):
    return range(number)

@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value