from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


def admin_required(function=None):
    """Только для админов (role='admin' или is_superuser)"""

    def is_admin(user):
        return user.is_authenticated and (user.is_superuser or user.role == 'admin')

    actual_decorator = user_passes_test(
        is_admin,
        login_url='/login/',
        redirect_field_name=None
    )

    if function:
        return actual_decorator(function)
    return actual_decorator


def manager_required(function=None):
    """Для админов и менеджеров"""

    def is_manager(user):
        return user.is_authenticated and (user.role in ['admin', 'manager'] or user.is_superuser)

    actual_decorator = user_passes_test(
        is_manager,
        login_url='/login/',
        redirect_field_name=None
    )

    if function:
        return actual_decorator(function)
    return actual_decorator


def client_required(function=None):
    """Только для клиентов (создаст профиль если его нет)"""

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Требуется авторизация')
                return redirect('login')

            if request.user.role != 'client':
                messages.error(request, 'Эта страница только для клиентов')
                return redirect('index')

            # Импорт здесь чтобы избежать циклических импортов
            from .views import get_or_create_client_profile

            # Создаем или получаем профиль клиента
            client_profile = get_or_create_client_profile(request.user)

            if not client_profile:
                messages.error(request, 'Не удалось создать профиль клиента')
                return redirect('profile')

            return view_func(request, *args, **kwargs)

        return wrapper

    if function:
        return decorator(function)
    return decorator


def role_required(allowed_roles):
    """Для конкретных ролей"""

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.role in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            messages.error(request, 'У вас нет прав для доступа к этой странице')
            return redirect('index')

        return wrapper

    return decorator