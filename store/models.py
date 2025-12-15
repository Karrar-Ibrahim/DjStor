from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator






class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="اسم الفئة")
    slug = models.SlugField(unique=True, allow_unicode=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="صورة الفئة")
    
    # --- الإضافة الجديدة: الأب (Parent) ---
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE, verbose_name="الفئة الرئيسية (الأب)")
    # --------------------------------------

    class Meta:
        verbose_name = "فئة"
        verbose_name_plural = "الفئات"

    def __str__(self):
        # دالة لطباعة الاسم الكامل (أب -> ابن)
        full_path = [self.name]
        k = self.parent
        while k is not None:
            full_path.append(k.name)
            k = k.parent
        return ' -> '.join(full_path[::-1])












class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, verbose_name="القسم")
    name = models.CharField(max_length=200, verbose_name="اسم المنتج")
    slug = models.SlugField(unique=True, allow_unicode=True)
    description = models.TextField(verbose_name="وصف المنتج")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر الأصلي")
    discount_percentage = models.PositiveIntegerField(default=0, verbose_name="نسبة الخصم %")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="الكمية المتوفرة")
    main_image = models.ImageField(upload_to='products/', verbose_name="الصورة الرئيسية")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    
    # This is the new field you added
    is_featured = models.BooleanField(default=False, verbose_name="منتج مميز (يظهر في السلايدر)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"
        ordering = ('-created_at',)

    def __str__(self):
        return self.name

    @property
    def final_price(self):
        if self.discount_percentage > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'قيد المعالجة'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="العميل")
    full_name = models.CharField(max_length=100, verbose_name="الاسم الكامل")
    phone = models.CharField(max_length=20, verbose_name="رقم الهاتف")
    address = models.TextField(verbose_name="العنوان")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="الإجمالي النهائي")
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=5000, verbose_name="مبلغ التوصيل")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="حالة الطلب")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الطلب")

    # --- الحقول الجديدة (أضفها هنا) ---
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الكوبون المستخدم")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="قيمة الخصم")
    # ----------------------------------

    class Meta:
        verbose_name = "طلب"
        verbose_name_plural = "الطلبات"
        ordering = ('-created_at',)

    def __str__(self):
        return f"طلب رقم {self.id} - {self.full_name}"
    

    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_cost(self):
        return self.price * self.quantity
    

    # 1. نموذج لحفظ رقم الهاتف (Profile)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=11, verbose_name="رقم الهاتف")
    # حقل جديد لحفظ كود التحقق
    otp_code = models.CharField(max_length=6, blank=True, null=True, verbose_name="كود التحقق")

    def __str__(self):
        return f"ملف {self.user.username}"
    

# 2. نموذج لحفظ السلة في قاعدة البيانات (CartItem)
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

# إشارة لإنشاء Profile تلقائياً عند إنشاء أي مستخدم جديد
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        # إذا لم يكن المستخدم يمتلك بروفايل (مثل الآدمن القديم)، قم بإنشاء واحد له الآن
        Profile.objects.create(user=instance, phone='')




# --- 1. مودل الكوبونات ---
class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="كود الخصم")
    discount = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="نسبة الخصم %")
    active = models.BooleanField(default=True, verbose_name="فعال")
    valid_from = models.DateTimeField(verbose_name="صالح من")
    valid_to = models.DateTimeField(verbose_name="صالح إلى")

    def __str__(self):
        return self.code

# --- 2. مودل التقييمات (سنستخدمه في الجزء الثاني) ---
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="المنتج")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="المستخدم")
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], verbose_name="التقييم")
    comment = models.TextField(blank=True, verbose_name="التعليق")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']






class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="المنتج")
    image = models.ImageField(upload_to='products/gallery/', verbose_name="الصورة")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"صورة لـ {self.product.name}"
    

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product') # منع تكرار نفس المنتج في المفضلة





class HomeSection(models.Model):
    SECTION_TYPES = (
        ('slider', 'شريط متحرك (Slider)'),
        ('grid', 'شبكة منتجات (Grid)'),
    )

    title = models.CharField(max_length=100, verbose_name="عنوان السكشن")
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES, default='grid', verbose_name="طريقة العرض")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="القسم (اختياري)")
    product_count = models.IntegerField(default=8, verbose_name="عدد المنتجات المعروضة")
    ordering = models.IntegerField(default=0, verbose_name="ترتيب الظهور")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ['ordering']
        verbose_name = "قسم الصفحة الرئيسية"
        verbose_name_plural = "أقسام الصفحة الرئيسية"

    def __str__(self):
        return self.title
