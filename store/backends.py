# store/backends.py

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """
    سماح بتسجيل الدخول باستخدام اسم المستخدم أو البريد الإلكتروني.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # البحث عن مستخدم يطابق اسمه أو إيميله النص المدخل
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # في حال وجود تكرار (نادر الحدوث إذا ضبطنا التسجيل)، نأخذ الأول
            user = User.objects.filter(Q(username=username) | Q(email=username)).order_by('id').first()

        # التحقق من كلمة المرور وصلاحية الحساب
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None