from django import forms
from store.models import Product, Category, Coupon
from django import forms
from django.contrib.auth.models import User, Permission
from store.models import HomeSection



# 1. فورم المنتجات
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'category', 'name', 'slug', 'description', 
            'price', 'discount_percentage', 'stock_quantity', 
            'main_image', 'is_active', 'is_featured'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'main_image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# 2. فورم الفئات (الأقسام)
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'image', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: هواتف ذكية'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: smart-phones'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'placeholder': 'الرابط المختصر (English)'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
        }

# 3. فورم الكوبونات (الجديد)
class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'discount', 'valid_from', 'valid_to', 'active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: SALE2025'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'نسبة الخصم %'}),
            
            # هنا التعديل المهم: type="datetime-local" يظهر التقويم والساعة
            'valid_from': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local'
            }),
            'valid_to': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local'
            }),
            
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }




PERMISSION_NAMES = {
    'add_product': 'إضافة منتجات',
    'change_product': 'تعديل منتجات',
    'delete_product': 'حذف منتجات',
    
    'add_category': 'إضافة أقسام',
    'change_category': 'تعديل أقسام',
    'delete_category': 'حذف أقسام',
    
    'change_order': 'تعديل حالة الطلبات',
    'delete_order': 'حذف الطلبات',
    # (عادة لا توجد صلاحية إضافة طلب من الداشبورد للموظف، لكن إن وجدت فهي add_order)
    
    'add_coupon': 'إضافة كوبونات',
    'change_coupon': 'تعديل كوبونات',
    'delete_coupon': 'حذف كوبونات',
}

# 2. كلاس مخصص لترجمة النصوص في القائمة
class TranslatedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        # نأخذ الاسم البرمجي (codename) ونبحث عنه في القاموس
        return PERMISSION_NAMES.get(obj.codename, obj.name)








# 4. فورم الموظفين والصلاحيات (هذا هو الكود الذي كان ناقصاً لديك)
class StaffUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, label="كلمة المرور")
    
    # استخدام الحقل المخصص للترجمة
    user_permissions = TranslatedModelMultipleChoiceField(
        queryset=Permission.objects.filter(
            content_type__app_label='store', # فقط صلاحيات تطبيق المتجر
            codename__in=PERMISSION_NAMES.keys() # فقط الصلاحيات التي عرفناها في القاموس
        ),
        widget=forms.CheckboxSelectMultiple,
        label="تحديد الصلاحيات",
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            if self.cleaned_data['user_permissions']:
                user.user_permissions.set(self.cleaned_data['user_permissions'])
        return user


class HomeSectionForm(forms.ModelForm):
    class Meta:
        model = HomeSection
        fields = ['title', 'section_type', 'category', 'product_count', 'ordering', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: هواتف آيفون'}),
            'section_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'product_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'ordering': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }