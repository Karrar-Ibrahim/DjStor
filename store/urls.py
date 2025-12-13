from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.product_list, name='shop'),
    path('category/<slug:category_slug>/', views.product_list, name='category_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.checkout, name='checkout'),

    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='store/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),

    path('coupon/apply/', views.coupon_apply, name='coupon_apply'),
    path('coupon/remove/', views.coupon_remove, name='coupon_remove'),


    path('offers/', views.offers, name='offers'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('wishlist/', views.wishlist_view, name='wishlist_view'),

    path('my-orders/', views.user_orders, name='user_orders'), # قائمة الطلبات
    path('my-orders/<int:order_id>/', views.user_order_detail, name='user_order_detail'),

    path('profile/', views.profile_view, name='profile'), 

]