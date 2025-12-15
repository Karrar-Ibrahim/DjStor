from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    
    # Products
    path('products/', views.product_manage, name='dashboard_products'),
    path('products/add/', views.product_add, name='dashboard_product_add'),
    
    # Categories 
    path('categories/', views.category_list, name='dashboard_categories'),
    path('categories/add/', views.category_add, name='dashboard_category_add'),
    path('categories/delete/<int:pk>/', views.delete_category, name='dashboard_category_delete'),
    path('categories/edit/<int:pk>/', views.category_edit, name='dashboard_category_edit'),



    # Orders
    path('orders/', views.order_manage, name='dashboard_orders'),
    path('orders/<int:order_id>/', views.order_detail, name='dashboard_order_detail'),
    path('products/edit/<int:pk>/', views.product_edit, name='dashboard_product_edit'),
    path('products/delete/<int:pk>/', views.delete_product, name='dashboard_product_delete'),


    
    #reports
    path('reports/', views.dashboard_reports, name='dashboard_reports'),
    path('reports/export/', views.export_reports_excel, name='export_reports_excel'),
    path('reports/inventory/', views.dashboard_inventory, name='dashboard_inventory'),
    
    #coupon
    path('coupons/', views.coupon_list, name='dashboard_coupons'),
    path('coupons/add/', views.coupon_add, name='dashboard_coupon_add'),
    path('coupons/delete/<int:pk>/', views.coupon_delete, name='dashboard_coupon_delete'),
    path('coupons/edit/<int:pk>/', views.coupon_edit, name='dashboard_coupon_edit'),


    # إدارة المستخدمين والصلاحيات
    path('users/', views.users_list, name='dashboard_users'),
    path('users/add/', views.user_add, name='dashboard_user_add'),
    path('users/edit/<int:pk>/', views.user_edit, name='dashboard_user_edit'),
    path('users/delete/<int:pk>/', views.user_delete, name='dashboard_user_delete'),

    path('products/image/delete/<int:image_id>/', views.delete_product_image, name='dashboard_image_delete'),
    path('products/main-image/delete/<int:pk>/', views.delete_main_image, name='dashboard_main_image_delete'),


    path('home-sections/', views.home_sections_list, name='dashboard_home_sections'),
    path('home-sections/add/', views.home_section_add, name='dashboard_home_section_add'),
    path('home-sections/edit/<int:pk>/', views.home_section_edit, name='dashboard_home_section_edit'),
    path('home-sections/delete/<int:pk>/', views.home_section_delete, name='dashboard_home_section_delete'),



]