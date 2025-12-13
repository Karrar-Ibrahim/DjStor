from django.contrib import admin
from .models import Category, Product, Order, OrderItem, Coupon, Review, Profile

# تسجيل الفئات
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

# تسجيل المنتجات
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_quantity', 'is_active', 'is_featured')
    list_filter = ('category', 'is_active', 'is_featured')
    list_editable = ('price', 'stock_quantity', 'is_active', 'is_featured')
    prepopulated_fields = {'slug': ('name',)}

# تسجيل الطلبات
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'phone', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [OrderItemInline]

# تسجيل الكوبونات (لحل مشكلتك الحالية)
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount', 'valid_from', 'valid_to', 'active')
    list_filter = ('active', 'valid_from', 'valid_to')
    search_fields = ('code',)

# تسجيل التقييمات
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')

# تسجيل البروفايل
admin.site.register(Profile)