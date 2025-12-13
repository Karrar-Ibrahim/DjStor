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
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'تم إنشاء الحساب بنجاح للعضو {username}')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'store/register.html', {'form': form})

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



