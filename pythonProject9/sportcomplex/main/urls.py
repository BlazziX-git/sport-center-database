from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
urlpatterns = [
    # ============== АУТЕНТИФИКАЦИЯ ==============
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('link-profile/', views.link_client_profile, name='link_client_profile'),

    # ============== ГЛАВНАЯ ==============
    path('', views.index, name='index'),

    # ============== КЛИЕНТЫ ==============
    path('clients/', views.client_list, name='client_list'),
    path('clients/create/', views.client_create, name='client_create'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('clients/<int:pk>/edit/', views.client_edit, name='client_edit'),
    path('clients/<int:pk>/delete/', views.client_delete, name='client_delete'),

    # ============== ТРЕНЕРЫ ==============
    path('trainers/', views.trainer_list, name='trainer_list'),
    path('trainers/create/', views.trainer_create, name='trainer_create'),
    path('trainers/<int:pk>/', views.trainer_detail, name='trainer_detail'),
    path('trainers/<int:pk>/edit/', views.trainer_edit, name='trainer_edit'),
    path('trainers/<int:pk>/delete/', views.trainer_delete, name='trainer_delete'),

    # ============== УСЛУГИ ==============
    path('services/', views.service_list, name='service_list'),
    path('services/admin/', views.service_list_admin, name='service_list_admin'),
    path('services/create/', views.service_create, name='service_create'),
    path('services/<int:pk>/', views.service_detail, name='service_detail'),
    path('services/<int:pk>/admin/', views.service_detail_admin, name='service_detail_admin'),
    path('services/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),

    # ============== АБОНЕМЕНТЫ ==============
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/create/', views.subscription_create, name='subscription_create'),
    path('subscriptions/<int:pk>/', views.subscription_detail, name='subscription_detail'),
    path('subscriptions/<int:pk>/edit/', views.subscription_edit, name='subscription_edit'),
    path('subscriptions/<int:pk>/delete/', views.subscription_delete, name='subscription_delete'),

    # ============== ДЛЯ КЛИЕНТОВ ==============
    path('my-subscriptions/', views.my_subscriptions, name='my_subscriptions'),
    path('my-schedule/', views.my_schedule, name='my_schedule'),
    path('buy-subscription/', views.buy_subscription, name='buy_subscription'),
    path('cancel-subscription/<int:pk>/', views.cancel_subscription, name='cancel_subscription'),

    # ============== ЗАПИСЬ НА ЗАНЯТИЯ ==============
    path('book-training/', views.book_training, name='book_training'),
    path('quick-book/', views.quick_book, name='quick_book'),
    path('quick-book/<int:service_id>/', views.quick_book, name='quick_book_with_service'),
    path('cancel-booking/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    path('manage-bookings/', views.manage_bookings, name='manage_bookings'),
    path('update-booking-status/<int:pk>/<str:status>/', views.update_booking_status, name='update_booking_status'),

    # ============== ДОПОЛНИТЕЛЬНЫЕ СТРАНИЦЫ ==============
    path('schedule/', views.schedule, name='schedule'),
    path('settings/', views.settings, name='settings'),

    # ============== ОТЧЕТЫ (НОВЫЕ) ==============
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/filter/', views.reports_filter, name='reports_filter'),
    path('reports/statistics/', views.reports_statistics, name='reports_statistics'),
    path('reports/comparison/', views.reports_comparison, name='reports_comparison'),
    path('reports/export-csv/', views.export_filter_to_csv, name='export_filter_to_csv'),

    # ============== API для AJAX ==============
    path('api/update-profile/', views.update_profile, name='update_profile'),
    path('api/get-service-price/<int:service_id>/', views.get_service_price, name='get_service_price'),
    path('api/get-available-times/', views.get_available_times, name='get_available_times'),
    path('api/create-booking-ajax/', views.create_booking_ajax, name='create_booking_ajax'),
    path('api/get-client-info/<int:client_id>/', views.get_client_info, name='get_client_info'),

    # ============== ВСПОМОГАТЕЛЬНЫЕ ==============
    path('admin/link-client/<int:user_id>/', views.link_client_to_user, name='link_client_to_user'),
    # Аутентификация
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]