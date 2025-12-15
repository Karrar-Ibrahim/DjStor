from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.utils import timezone
from django.views.decorators.http import require_POST
import urllib.parse
import threading
import random
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User

# استيراد المودلز
from .models import Product, Category, Order, OrderItem, Coupon, Review, Profile, HomeSection, Wishlist

# استيراد الكارت والفورم
from .cart import Cart
from .forms import (
    OrderCreateForm, UserRegisterForm, OTPVerificationForm, 
    UserUpdateForm, ProfileUpdateForm, PasswordResetRequestForm, SetNewPasswordForm
)
from .telegram_utils import send_telegram_order

# --- دالة مساعدة لجلب الفئة وجميع أبنائها ---
def get_all_category_children(category):
    categories = [category]
    for child in category.children.all():
        categories.extend(get_all_category_children(child))
    return categories

# --- الصفحة الرئيسية ---
def home(request):
    # 1. السلايدر الرئيسي (المنتجات المميزة)
    main_sliders = Product.objects.filter(is_active=True, is_featured=True).order_by('-updated_at')[:5]
    
    # 2. الفئات الرئيسية (للقائمة المنسدلة في الصفحة)
    # هذا هو السطر الذي كان ناقصاً لديك وتسبب في اختفاء الفئات
    categories = Category.objects.filter(parent=None)

    # 3. السكشنات الديناميكية
    dynamic_sections = []
    sections_db = HomeSection.objects.filter(is_active=True)
    
    for sec in sections_db:
        products = Product.objects.filter(is_active=True)
        
        if sec.category:
            cats = get_all_category_children(sec.category)
            products = products.filter(category__in=cats)
        
        products = products.order_by('-created_at')[:sec.product_count]
        
        if products.exists():
            dynamic_sections.append({
                'config': sec,
                'products': products
            })

    return render(request, 'store/home.html', {
        'sliders': main_sliders,
        'categories': categories, # إرسال الفئات للقالب
        'dynamic_sections': dynamic_sections,
    })

# --- قائمة المنتجات ---
def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.filter(parent=None)
    products = Product.objects.filter(is_active=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        all_related_categories = get_all_category_children(category)
        products = products.filter(category__in=all_related_categories)
    
    query = request.GET.get('q')
    if query:
        products = products.filter(name__icontains=query)

    return render(request, 'store/product_list.html', {
        'category': category, 
        'categories': categories, 
        'products': products
    })

# --- تفاصيل المنتج ---
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    is_in_wishlist = False
    if request.user.is_authenticated:
        is_in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()

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

    avg_rating = product.reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0
    reviews = product.reviews.all()

    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'review_count': reviews.count(),
        'is_in_wishlist': is_in_wishlist,
    }
    return render(request, 'store/product_detail.html', context)

# --- المفضلة ---
@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
    
    if wishlist_item:
        wishlist_item.delete()
        messages.info(request, f"تم حذف {product.name} من المفضلة.")
    else:
        Wishlist.objects.create(user=request.user, product=product)
        messages.success(request, f"تم إضافة {product.name} للمفضلة.")
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'store/wishlist.html', {'wishlist_items': wishlist_items})

# --- السلة ---
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

# --- الدفع ---
def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        return redirect('home')
    
    DELIVERY_FEE = 5000 

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    order = form.save(commit=False)
                    if request.user.is_authenticated:
                        order.user = request.user
                    
                    order.delivery_fee = DELIVERY_FEE
                    
                    if cart.coupon:
                        order.coupon = cart.coupon
                        order.discount_amount = cart.get_discount()
                    else:
                        order.discount_amount = 0
                    
                    order.total_amount = cart.get_total_price_after_discount() + DELIVERY_FEE
                    order.save()
                    
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
                    
                    threading.Thread(target=send_telegram_order, args=(order,)).start()
                    cart.clear()
                    return redirect('order_success', order_id=order.id)
            
            except Exception as e:
                print(f"Checkout Error: {e}") 
                messages.error(request, "حدث خطأ أثناء معالجة الطلب.")
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

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    store_phone = "9647833003554" 
    message = f"مرحباً، أريد تأكيد طلبي رقم #{order.id}\n"
    whatsapp_url = f"https://wa.me/{store_phone}?text={urllib.parse.quote(message)}"
    return render(request, 'store/order_success.html', {'order': order, 'whatsapp_url': whatsapp_url})

# --- العروض والكوبونات ---
def offers(request):
    products = Product.objects.filter(is_active=True, discount_percentage__gt=0).order_by('-discount_percentage')
    return render(request, 'store/offers.html', {'products': products, 'page_title': 'العروض المميزة'})

@require_POST
def coupon_apply(request):
    now = timezone.now()
    code = request.POST.get('code')
    try:
        coupon = Coupon.objects.get(code__iexact=code, valid_from__lte=now, valid_to__gte=now, active=True)
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

# --- المستخدمين ---
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            
            otp = str(random.randint(100000, 999999))
            
            if not hasattr(user, 'profile'):
                Profile.objects.create(user=user, phone=form.cleaned_data.get('phone'))
            
            user.profile.otp_code = otp
            user.profile.save()

            subject = 'كود تفعيل حسابك - عشتار ستور'
            message = f'مرحباً {user.first_name}،\n\nكود التحقق الخاص بك هو: {otp}'
            from_email = settings.EMAIL_HOST_USER
            recipient_list = [user.email]
            
            try:
                send_mail(subject, message, from_email, recipient_list)
                request.session['auth_user_id'] = user.id
                request.session['auth_email'] = user.email
                messages.info(request, f'تم إرسال كود التحقق إلى {user.email}')
                return redirect('verify_email')
            except Exception as e:
                user.delete()
                messages.error(request, "فشل إرسال البريد الإلكتروني.")
    else:
        form = UserRegisterForm()
    return render(request, 'store/register.html', {'form': form})

def verify_email(request):
    user_id = request.session.get('auth_user_id')
    email = request.session.get('auth_email')
    
    if not user_id:
        return redirect('register')

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['otp_code']
            try:
                user = User.objects.get(id=user_id)
                if user.profile.otp_code == code:
                    user.is_active = True
                    user.profile.otp_code = None
                    user.save()
                    user.profile.save()
                    
                    from django.contrib.auth import login
                    login(request, user)
                    
                    if 'auth_user_id' in request.session: del request.session['auth_user_id']
                    if 'auth_email' in request.session: del request.session['auth_email']
                    
                    messages.success(request, "تم تفعيل حسابك بنجاح!")
                    return redirect('home')
                else:
                    messages.error(request, "كود التحقق غير صحيح.")
            except User.DoesNotExist:
                return redirect('register')
    else:
        form = OTPVerificationForm()
    return render(request, 'store/verify_email.html', {'form': form, 'email': email})

@login_required
def profile_view(request):
    if not hasattr(request.user, 'profile'):
        Profile.objects.create(user=request.user)

    if request.method == 'POST':
        if 'update_info' in request.POST:
            u_form = UserUpdateForm(request.POST, instance=request.user)
            p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
            if u_form.is_valid() and p_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, 'تم تحديث بياناتك بنجاح!')
                return redirect('profile')
        elif 'change_password' in request.POST:
            pass_form = PasswordChangeForm(request.user, request.POST)
            if pass_form.is_valid():
                user = pass_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'تم تغيير كلمة المرور بنجاح!')
                return redirect('profile')
            else:
                messages.error(request, 'يرجى التأكد من صحة كلمة المرور.')
    
    u_form = UserUpdateForm(instance=request.user)
    p_form = ProfileUpdateForm(instance=request.user.profile)
    pass_form = PasswordChangeForm(request.user)

    context = {'u_form': u_form, 'p_form': p_form, 'pass_form': pass_form}
    return render(request, 'store/profile.html', context)

@login_required
def user_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/user_orders.html', {'orders': orders})

@login_required
def user_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/user_order_detail.html', {'order': order})

# --- استعادة كلمة المرور ---
def forgot_password(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email).first()
            
            if user:
                if not hasattr(user, 'profile'):
                    Profile.objects.create(user=user, phone='')

                otp = str(random.randint(100000, 999999))
                user.profile.otp_code = otp
                user.profile.save()
                
                subject = 'استعادة كلمة المرور - عشتار ستور'
                message = f'كود استعادة الحساب هو: {otp}'
                
                try:
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
                    request.session['reset_user_id'] = user.id
                    messages.info(request, f"تم إرسال رمز التحقق إلى {email}")
                    return redirect('verify_reset_code')
                except Exception as e:
                    messages.error(request, "حدث خطأ أثناء إرسال الإيميل.")
            else:
                messages.error(request, "هذا البريد غير مسجل.")
    else:
        form = PasswordResetRequestForm()
    return render(request, 'store/forgot_password.html', {'form': form})

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
                user.profile.otp_code = None
                user.profile.save()
                request.session['reset_verified'] = True
                return redirect('set_new_password')
            else:
                messages.error(request, "الرمز غير صحيح.")
    else:
        form = OTPVerificationForm()
    return render(request, 'store/verify_reset_code.html', {'form': form})

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
            if 'reset_user_id' in request.session: del request.session['reset_user_id']
            if 'reset_verified' in request.session: del request.session['reset_verified']
            messages.success(request, "تم تغيير كلمة المرور بنجاح!")
            return redirect('login')
    else:
        form = SetNewPasswordForm(user)
    return render(request, 'store/set_new_password.html', {'form': form})

# صفحات ثابتة
def about(request):
    return render(request, 'store/about.html')

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        messages.success(request, f"شكراً لك {name}، تم استلام رسالتك.")
        return redirect('contact')
    return render(request, 'store/contact.html')