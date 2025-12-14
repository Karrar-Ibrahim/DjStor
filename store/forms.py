from django import forms
from .models import Order
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from .models import Order, Profile
from store.models import Profile 
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from .models import Profile


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

# store/forms.py

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label="الاسم الأول", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    phone = forms.CharField(
        label="رقم الهاتف",
        max_length=11,
        min_length=11,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07700000000'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone']

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        
        # --- هذا الكود هو الحل الجذري ---
        # نحدد قائمة الحقول التي نريدها فقط
        allowed_fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'password_1', 'password_2']
        
        # نقوم بحذف أي حقل موجود في النموذج ولكنه غير موجود في قائمتنا
        # هذا سيحذف الحقل المزعج "Password-based authentication" أياً كان مصدره
        for field_name in list(self.fields.keys()):
            if field_name not in allowed_fields:
                del self.fields[field_name]
        # -------------------------------

        # تحسين مظهر حقول كلمة المرور (لأنها تأتي من UserCreationForm)
        if 'password_1' in self.fields:
            self.fields['password_1'].widget.attrs.update({'class': 'form-control'})
            self.fields['password_1'].label = "كلمة المرور"
            self.fields['password_1'].help_text = None # حذف نصوص المساعدة المزعجة
            
        if 'password_2' in self.fields:
            self.fields['password_2'].widget.attrs.update({'class': 'form-control'})
            self.fields['password_2'].label = "تأكيد كلمة المرور"
            self.fields['password_2'].help_text = None

    # التحقق من الإيميل
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مسجل مسبقاً.")
        return email

    # التحقق من الهاتف
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.isdigit() or len(phone) != 11:
            raise forms.ValidationError("رقم الهاتف يجب أن يكون 11 رقماً.")
        if Profile.objects.filter(phone=phone).exists():
            raise forms.ValidationError("رقم الهاتف هذا مرتبط بحساب آخر.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            if not hasattr(user, 'profile'):
                Profile.objects.create(user=user, phone=self.cleaned_data['phone'])
            else:
                user.profile.phone = self.cleaned_data['phone']
                user.profile.save()
        return user
    
    

# 2. نموذج طلب استعادة كلمة المرور (إدخال الإيميل)
class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="البريد الإلكتروني",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'أدخل بريدك الإلكتروني المسجل'})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("هذا البريد غير مسجل لدينا.")
        return email

# 3. نموذج إدخال كلمة المرور الجديدة
class SetNewPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
    


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



class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        label="رمز التحقق",
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center text-primary fw-bold fs-4', 
            'placeholder': 'XXXXXX',
            'style': 'letter-spacing: 5px;'
        })
    )