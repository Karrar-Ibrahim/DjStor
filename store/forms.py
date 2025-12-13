from django import forms
from .models import Order
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import Order, Profile
from store.models import Profile 



class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'phone', 'address']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'الاسم الكامل'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'رقم الهاتف'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'العنوان بالتفصيل'}),
        }

#class UserRegisterForm(UserCreationForm):
    # Add extra fields if needed, standard Django form works too
#    pass

class UserRegisterForm(UserCreationForm):
    # 1. التحقق من اسم المستخدم (إنجليزي وأرقام فقط)
    username = forms.CharField(
        label="اسم المستخدم",
        help_text="أحرف إنجليزية وأرقام فقط.",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9]+$',
                message='اسم المستخدم يجب أن يحتوي على أحرف إنجليزية وأرقام فقط.',
                code='invalid_username'
            ),
        ],
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # 2. إضافة حقل الهاتف
    phone = forms.CharField(
        label="رقم الهاتف",
        max_length=11,
        min_length=11,
        help_text="يجب أن يتكون من 11 رقماً.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07700000000'})
    )

    # تحسين حقول الاسم الأول والأخير والبريد
    first_name = forms.CharField(label="الاسم الأول", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone']

    # التحقق المخصص لرقم الهاتف (أن يكون أرقاماً فقط)
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.isdigit():
            raise forms.ValidationError("رقم الهاتف يجب أن يحتوي على أرقام فقط.")
        if len(phone) != 11:
            raise forms.ValidationError("رقم الهاتف يجب أن يكون 11 مرتبة.")
        return phone

    # حفظ البيانات (المستخدم + البروفايل)
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # حفظ رقم الهاتف في البروفايل
            if hasattr(user, 'profile'):
                user.profile.phone = self.cleaned_data['phone']
                user.profile.save()
            else:
                Profile.objects.create(user=user, phone=self.cleaned_data['phone'])
        return user
    


class UserUpdateForm(forms.ModelForm):
    # جعل اسم المستخدم غير مفعل (للقراءة فقط)
    username = forms.CharField(
        label="اسم المستخدم",
        disabled=True,  # هذا يمنع التعديل
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}) # تنسيق إضافي
    )
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label="الاسم الأول", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email'] # أضفنا username 

class ProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(label="رقم الهاتف", widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        fields = ['phone']