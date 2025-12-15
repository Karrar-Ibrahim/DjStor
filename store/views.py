from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.utils import timezone
from django.views.decorators.http import require_POST
import urllib.parse
import threading
from .models import Product, Category, Order, OrderItem, Coupon, Review, Wishlist
from .cart import Cart
from .forms import OrderCreateForm, UserRegisterForm
from .telegram_utils import send_telegram_order
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import UserUpdateForm, ProfileUpdateForm
import random
from django.core.mail import send_mail
from django.conf import settings
from .forms import OTPVerificationForm
    
from django.contrib.auth.models import User
from .forms import PasswordResetRequestForm, SetNewPasswordForm, OTPVerificationForm
    
from .models import Product, Category, Order, OrderItem, Coupon, Review, Profile, HomeSection

    



# --- دالة مساعدة لجلب الفئة وجميع أبنائها (لحل مشكلة عدم ظهور المنتجات) ---
def get_all_category_children(category):
    """
    هذه الدالة تعيد قائمة تحتوي الفئة الحالية + جميع الفئات الفرعية التابعة لها.
    """
    categories = [category]
    for child in category.children.all():
        # استدعاء ذاتي (Recursion) لجلب أحفاد الأحفاد إن وجدوا
        categories.extend(get_all_category_children(child))
    return categories
# -----------------------------------------------------------------------

def home(request):
    # جلب منتجات السلايدر (المميزة)
    sliders = Product.objects.filter(is_active=True, is_featured=True).order_by('-updated_at')[:5]
    
    # جلب أحدث المنتجات
    latest = Product.objects.filter(is_active=True).order_by('-created_at')[:8]
    
    # جلب الفئات الرئيسية فقط (التي ليس لها أب) للصفحة الرئيسية
    categories = Category.objects.filter(parent=None)
    
    return render(request, 'store/home.html', {
        'sliders': sliders, 
        'latest': latest, 
        'categories': categories
    })

def product_list(request, category_slug=None):
    category = None
    # للقائمة الجانبية: نعرض فقط الأقسام الرئيسية
    categories = Category.objects.filter(parent=None)
    
    products = Product.objects.filter(is_active=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        
        # --- التعديل الجوهري: استخدام الدالة المساعدة ---
        # نجلب الفئة المحددة + كل الفئات المتفرعة منها
        all_related_categories = get_all_category_children(category)
        
        # نفلتر المنتجات لتكون موجودة في أي من هذه الفئات
        products = products.filter(category__in=all_related_categories)
        # ----------------------------------------------
    
    # البحث
    query = request.GET.get('q')
    if query:
        products = products.filter(name__icontains=query)

    return render(request, 'store/product_list.html', {
        'category': category, 
        'categories': categories, 
        'products': products
    })


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # البحث عن المنتج في مفضلة المستخدم
    # إذا وجدناه، نحذفه (Remove). إذا لم نجده، ننشئه (Add).
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
    
    if wishlist_item:
        wishlist_item.delete()
        messages.info(request, f"تم حذف {product.name} من المفضلة.")
    else:
        Wishlist.objects.create(user=request.user, product=product)
        messages.success(request, f"تم إضافة {product.name} للمفضلة.")
    
    # إعادة المستخدم لنفس الصفحة التي ضغط منها الزر
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def wishlist_view(request):
    # جلب عناصر المفضلة الخاصة بالمستخدم الحالي
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    
    return render(request, 'store/wishlist.html', {
        'wishlist_items': wishlist_items
    })


# --- دالة تفاصيل المنتج (المعدلة) ---
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # 1. التحقق من المفضلة (الجديد)
    is_in_wishlist = False
    if request.user.is_authenticated:
        # هل هذا المنتج موجود في مفضلة هذا المستخدم؟
        is_in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()

    # 2. معالجة إضافة تقييم جديد
    if request.method == 'POST' and 'rating' in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, "يجب تسجيل الدخول لإضافة تقييم.")
            return redirect('login')
            
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "شكراً لك! تم إضافة تقييمك بنجاح.")
        return redirect('product_detail', slug=slug)

    # 3. حساب متوسط التقييم
    avg_rating = product.reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0
    reviews = product.reviews.all()

    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'review_count': reviews.count(),
        'is_in_wishlist': is_in_wishlist, # <--- تمرير المتغير للقالب
    }

    return render(request, 'store/product_detail.html', context)



# --- دوال السلة (Cart) ---

def cart_detail(request):
    cart = Cart(request)
    return render(request, 'store/cart.html', {'cart': cart})

def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.add(product=product, quantity=1)
    messages.success(request, "تمت إضافة المنتج إلى السلة")
    return redirect('cart_detail')

def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return redirect('cart_detail')

# --- دوال الدفع (Checkout) ---

def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        return redirect('home')
    
    DELIVERY_FEE = 5000 

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            try:
                # استخدام transaction لضمان سلامة البيانات
                with transaction.atomic():
                    order = form.save(commit=False)
                    if request.user.is_authenticated:
                        order.user = request.user
                    
                    # 1. حفظ مبلغ التوصيل
                    order.delivery_fee = DELIVERY_FEE
                    
                    # 2. حفظ الكوبون وقيمة الخصم
                    if cart.coupon:
                        order.coupon = cart.coupon
                        order.discount_amount = cart.get_discount()
                    else:
                        order.discount_amount = 0
                    
                    # 3. حساب الإجمالي النهائي
                    order.total_amount = cart.get_total_price_after_discount() + DELIVERY_FEE
                    
                    order.save()
                    
                    # حفظ المنتجات في الطلب وخصم المخزون
                    for item in cart:
                        product = item['product']
                        quantity = int(item['quantity'])
                        
                        if product.stock_quantity < quantity:
                            messages.error(request, f"الكمية غير متوفرة للمنتج {product.name}")
                            return redirect('cart_detail')
                            
                        product.stock_quantity -= quantity
                        product.save()

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            price=item['price'],
                            quantity=quantity
                        )
                    
                    # إرسال إشعار تلجرام (في الخلفية لعدم تعطيل المستخدم)
                    threading.Thread(target=send_telegram_order, args=(order,)).start()

                    # تفريغ السلة وتوجيه للنجاح
                    cart.clear()
                    return redirect('order_success', order_id=order.id)
            
            except Exception as e:
                print(f"Checkout Error: {e}") 
                messages.error(request, "حدث خطأ أثناء معالجة الطلب، يرجى المحاولة مرة أخرى.")
                return redirect('checkout')
    else:
        initial_data = {}
        if request.user.is_authenticated:
            try:
                initial_data = {'full_name': request.user.first_name, 'phone': request.user.profile.phone}
            except:
                pass
        form = OrderCreateForm(initial=initial_data)

    return render(request, 'store/checkout.html', {
        'cart': cart, 
        'form': form, 
        'delivery_fee': DELIVERY_FEE
    })

# --- صفحة العروض ---
def offers(request):
    # جلب المنتجات التي لديها خصم وترتيبها
    products = Product.objects.filter(is_active=True, discount_percentage__gt=0).order_by('-discount_percentage')
    return render(request, 'store/offers.html', {
        'products': products,
        'page_title': 'العروض المميزة والتخفيضات'
    })

# --- دوال المستخدمين ---
# 1. تعديل دالة التسجيل (register)
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # حفظ المستخدم لكن غير نشط
            user = form.save(commit=False)
            user.is_active = False # <--- مهم جداً: الحساب غير مفعل
            user.save()
            
            # إنشاء كود عشوائي من 6 أرقام
            otp = str(random.randint(100000, 999999))
            
            # حفظ الكود في البروفايل
            # ملاحظة: دالة create_user_profile في models.py ستنشئ البروفايل تلقائياً، نحن نحدثه فقط
            user.profile.otp_code = otp
            user.profile.save()

            # إرسال الكود عبر الإيميل
            subject = 'كود تفعيل حسابك - عشتار ستور'
            message = f'مرحباً {user.first_name}،\n\nكود التحقق الخاص بك هو: {otp}\n\nشكراً لتسجيلك معنا.'
            from_email = settings.EMAIL_HOST_USER
            recipient_list = [user.email]
            
            try:
                send_mail(subject, message, from_email, recipient_list)
                # تخزين الإيميل في السيشن لنستخدمه في الصفحة التالية
                request.session['auth_email'] = user.email
                messages.info(request, f'تم إرسال كود التحقق إلى {user.email}')
                return redirect('verify_email')
            
            except Exception as e:
                user.delete() # حذف المستخدم إذا فشل إرسال الإيميل
                messages.error(request, "فشل إرسال البريد الإلكتروني، يرجى التأكد من الإيميل.")

    else:
        form = UserRegisterForm()
    return render(request, 'store/register.html', {'form': form})

# 2. دالة التحقق الجديدة (verify_email)
def verify_email(request):
    # جلب الإيميل من السيشن
    email = request.session.get('auth_email')
    
    if not email:
        messages.error(request, "جلسة غير صالحة، يرجى التسجيل مرة أخرى.")
        return redirect('register')

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['otp_code']
            try:
                user = User.objects.get(email=email)
                
                # التحقق من تطابق الكود
                if user.profile.otp_code == code:
                    user.is_active = True # تفعيل الحساب
                    user.profile.otp_code = None # مسح الكود بعد الاستخدام
                    user.save()
                    user.profile.save()
                    
                    # تسجيل الدخول تلقائياً
                    from django.contrib.auth import login
                    login(request, user)
                    
                    # تنظيف السيشن
                    del request.session['auth_email']
                    
                    messages.success(request, "تم تفعيل حسابك بنجاح! أهلاً بك.")
                    return redirect('home')
                else:
                    messages.error(request, "كود التحقق غير صحيح.")
            
            except User.DoesNotExist:
                messages.error(request, "حدث خطأ، المستخدم غير موجود.")
    else:
        form = OTPVerificationForm()

    return render(request, 'store/verify_email.html', {'form': form, 'email': email})





def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # إعداد رسالة واتساب للعميل
    store_phone = "9647833003554" 
    message = f"مرحباً، أريد تأكيد طلبي رقم #{order.id}\n"
    message += f"الاسم: {order.full_name}\n"
    message += f"الإجمالي: {order.total_amount}\n"
    message += "يرجى تأكيد الطلب."
    
    whatsapp_url = f"https://wa.me/{store_phone}?text={urllib.parse.quote(message)}"
    
    return render(request, 'store/order_success.html', {
        'order': order,
        'whatsapp_url': whatsapp_url
    })

# --- دوال الكوبونات ---
@require_POST
def coupon_apply(request):
    now = timezone.now()
    code = request.POST.get('code')
    try:
        coupon = Coupon.objects.get(code__iexact=code, 
                                    valid_from__lte=now, 
                                    valid_to__gte=now, 
                                    active=True)
        request.session['coupon_id'] = coupon.id
        messages.success(request, f"تم تفعيل كود الخصم: {coupon.code}")
    except Coupon.DoesNotExist:
        request.session['coupon_id'] = None
        messages.error(request, "كود الخصم غير صالح أو منتهي الصلاحية.")
    return redirect('checkout')

def coupon_remove(request):
    if 'coupon_id' in request.session:
        del request.session['coupon_id']
        messages.info(request, "تمت إزالة كود الخصم.")
    return redirect('checkout')



@login_required
def user_orders(request):
    # جلب الطلبات الخاصة بالمستخدم الحالي فقط
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/user_orders.html', {'orders': orders})

@login_required
def user_order_detail(request, order_id):
    # جلب الطلب، مع التأكد أن هذا الطلب يملك لهذا المستخدم حصراً (للأمان)
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/user_order_detail.html', {'order': order})


@login_required
def profile_view(request):
    # التأكد من وجود بروفايل للمستخدم لتجنب الأخطاء
    if not hasattr(request.user, 'profile'):
        from .models import Profile
        Profile.objects.create(user=request.user)

    if request.method == 'POST':
        # 1. معالجة تحديث المعلومات الشخصية
        if 'update_info' in request.POST:
            u_form = UserUpdateForm(request.POST, instance=request.user)
            p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
            if u_form.is_valid() and p_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, 'تم تحديث بياناتك بنجاح!')
                return redirect('profile')
            else:
                # إعادة تهيئة فورم الباسورد فارغاً لتجنب الأخطاء في القالب
                pass_form = PasswordChangeForm(request.user)

        # 2. معالجة تغيير كلمة المرور
        elif 'change_password' in request.POST:
            pass_form = PasswordChangeForm(request.user, request.POST)
            if pass_form.is_valid():
                user = pass_form.save()
                # مهم جداً: تحديث الجلسة لكي لا يتم تسجيل الخروج
                update_session_auth_hash(request, user)
                messages.success(request, 'تم تغيير كلمة المرور بنجاح!')
                return redirect('profile')
            else:
                messages.error(request, 'يرجى التأكد من صحة كلمة المرور الحالية وتطابق الجديدة.')
                # إعادة تهيئة فورم المعلومات بالبيانات الحالية
                u_form = UserUpdateForm(instance=request.user)
                p_form = ProfileUpdateForm(instance=request.user.profile)
    
    else:
        # طلب GET (فتح الصفحة)
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)
        pass_form = PasswordChangeForm(request.user)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'pass_form': pass_form
    }
    return render(request, 'store/profile.html', context)



def forgot_password(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)
            
            # إنشاء كود OTP
            otp = str(random.randint(100000, 999999))
            user.profile.otp_code = otp
            user.profile.save()
            
            # إرسال الكود
            subject = 'استعادة كلمة المرور - عشتار ستور'
            message = f'مرحباً {user.first_name}،\n\nكود استعادة الحساب هو: {otp}\n\nلا تشارك هذا الكود مع أحد.'
            
            try:
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
                
                # حفظ ID المستخدم في السيشن للاستخدام في الخطوة القادمة
                request.session['reset_user_id'] = user.id
                messages.info(request, f"تم إرسال رمز التحقق إلى {email}")
                return redirect('verify_reset_code')
            except Exception as e:
                messages.error(request, "حدث خطأ أثناء إرسال الإيميل.")
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'store/forgot_password.html', {'form': form})

# 2. صفحة التحقق من كود الاستعادة
def verify_reset_code(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['otp_code']
            user = User.objects.get(id=user_id)
            
            if user.profile.otp_code == code:
                # الكود صحيح، نمسحه وننتقل لتعيين كلمة المرور
                user.profile.otp_code = None
                user.profile.save()
                # نضع علامة في السيشن أن المستخدم قد اجتاز التحقق
                request.session['reset_verified'] = True
                return redirect('set_new_password')
            else:
                messages.error(request, "كود التحقق غير صحيح، حاول مرة أخرى.")
    else:
        form = OTPVerificationForm()
    
    return render(request, 'store/verify_reset_code.html', {'form': form})

# 3. صفحة تعيين كلمة المرور الجديدة
def set_new_password(request):
    user_id = request.session.get('reset_user_id')
    is_verified = request.session.get('reset_verified')
    
    if not user_id or not is_verified:
        return redirect('forgot_password')
    
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        form = SetNewPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # تنظيف السيشن
            del request.session['reset_user_id']
            del request.session['reset_verified']
            
            messages.success(request, "تم تغيير كلمة المرور بنجاح! يمكنك الدخول الآن.")
            return redirect('login')
    else:
        form = SetNewPasswordForm(user)
    
    return render(request, 'store/set_new_password.html', {'form': form})


def about(request):
    return render(request, 'store/about.html')

def contact(request):
    if request.method == 'POST':
        # هنا يمكنك إضافة كود إرسال الإيميل لاحقاً
        name = request.POST.get('name')
        messages.success(request, f"شكراً لك {name}، تم استلام رسالتك وسنرد عليك قريباً.")
        return redirect('contact')
    return render(request, 'store/contact.html')




def home(request):
    # 1. السلايدر الرئيسي (ثابت) - للمنتجات المميزة فقط
    main_sliders = Product.objects.filter(is_active=True, is_featured=True).order_by('-updated_at')[:5]
    
    # 2. السكشنات الديناميكية (التي يضيفها الأدمن)
    dynamic_sections = []
    sections_db = HomeSection.objects.filter(is_active=True)
    
    for sec in sections_db:
        # جلب المنتجات لهذا السكشن
        products = Product.objects.filter(is_active=True)
        
        # إذا حدد الأدمن قسماً معيناً، نفلتر عليه
        if sec.category:
            # استخدام دالة get_all_category_children لجلب الفرعية أيضاً
            cats = get_all_category_children(sec.category)
            products = products.filter(category__in=cats)
        
        # الترتيب حسب الأحدث وأخذ العدد المحدد
        products = products.order_by('-created_at')[:sec.product_count]
        
        if products.exists():
            dynamic_sections.append({
                'config': sec,       # إعدادات السكشن (العنوان، النوع)
                'products': products # قائمة المنتجات
            })

    return render(request, 'store/home.html', {
        'sliders': main_sliders,
        'dynamic_sections': dynamic_sections, # <--- المتغير الجديد
    })