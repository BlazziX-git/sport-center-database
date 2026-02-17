from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Users, Clients, Trainers, Services, Subscriptions


@admin.register(Users)
class CustomUserAdmin(UserAdmin):
    list_display = ('userName', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('userName', 'email', 'phone')
    ordering = ('userName',)

    fieldsets = (
        (None, {'fields': ('userName', 'password')}),
        ('Персональная информация', {'fields': ('email', 'phone', 'birth_date')}),
        ('Права доступа', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Важные даты', {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('userName', 'email', 'phone', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Clients)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'email', 'birth_date', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone', 'email')
    list_filter = ('created_at',)


@admin.register(Trainers)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'specialization', 'experience_years', 'phone', 'is_active')
    list_filter = ('is_active', 'specialization')
    search_fields = ('full_name', 'phone')


@admin.register(Services)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'price', 'duration', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('service_name',)


@admin.register(Subscriptions)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscription_id', 'client', 'service', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('client__first_name', 'client__last_name', 'service__service_name')