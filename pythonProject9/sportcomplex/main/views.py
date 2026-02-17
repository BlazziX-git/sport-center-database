from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Avg, Count, Q, Min, Max
from .models import Users, Clients, Trainers, Services, Subscriptions, Bookings
from .forms import UserRegisterForm, ClientForm, TrainerForm, ServiceForm, SubscriptionForm, UserProfileForm, \
    BookingForm, QuickBookingForm
from .decorators import admin_required, manager_required, client_required, role_required
from datetime import date, datetime, timedelta
from django.http import JsonResponse, HttpResponse
import json
import random  # Импортируем random для генерации данных графиков
from django.urls import reverse
from django.utils import timezone
from .report_generator import ReportGenerator
import pandas as pd


# ============== АУТЕНТИФИКАЦИЯ ==============
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешна!')
            return redirect('index')
    else:
        form = UserRegisterForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile(request):
    user = request.user

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user)

    # Получаем статистику в зависимости от роли
    if user.role == 'client':
        # Для клиентов ищем или создаем профиль
        client_profile = get_or_create_client_profile(user)
        if client_profile:
            subscriptions = Subscriptions.objects.filter(client=client_profile)
            active_subscriptions = subscriptions.filter(status='active')
            bookings = Bookings.objects.filter(client=client_profile).order_by('-booking_date', '-start_time')[:5]

            context = {
                'user': user,
                'form': form,
                'client': client_profile,
                'subscriptions': subscriptions,
                'bookings': bookings,
                'active_subscriptions_count': active_subscriptions.count(),
                'total_spent': subscriptions.aggregate(total=Sum('price_paid'))['total'] or 0,
            }
        else:
            context = {
                'user': user,
                'form': form,
                'client': None,
            }
    else:
        context = {
            'user': user,
            'form': form,
        }

    return render(request, 'registration/profile.html', context)


# Вспомогательная функция для получения или создания профиля клиента
def get_or_create_client_profile(user):
    """Получает или создает профиль клиента для пользователя"""
    if user.role != 'client':
        return None

    # Если профиль уже привязан, возвращаем его
    if hasattr(user, 'client_profile') and user.client_profile:
        return user.client_profile

    try:
        # Ищем клиента по email или телефону
        client = None

        if user.email:
            client = Clients.objects.filter(email=user.email).first()

        if not client and user.phone:
            client = Clients.objects.filter(phone=user.phone).first()

        # Если клиент не найден, создаем нового
        if not client:
            # Обработка имени пользователя
            if ' ' in user.userName:
                first_name = user.userName.split()[0]
                last_name = user.userName.split()[-1]
            else:
                first_name = user.userName
                last_name = ""

            # Создаем клиента с обязательными полями
            client = Clients.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone=user.phone or '+7 (000) 000-00-00',
                email=user.email or '',
                birth_date=user.birth_date
            )

        # Привязываем клиента к пользователю
        user.client_profile = client
        user.save(update_fields=['client_profile'])

        return client

    except Exception as e:
        print(f"Ошибка создания профиля клиента: {e}")
        return None


# ============== ГЛАВНАЯ СТРАНИЦА ==============
@login_required
def index(request):
    user = request.user

    # Для разных ролей разная статистика
    if user.role in ['admin', 'manager']:
        # Базовая статистика
        clients_count = Clients.objects.count()
        trainers_count = Trainers.objects.count()
        services_count = Services.objects.count()
        subscriptions_count = Subscriptions.objects.count()

        # Расширенная статистика для услуг
        active_services = Services.objects.filter(is_active=True)
        avg_price = active_services.aggregate(avg=Avg('price'))['avg'] or 0
        avg_duration = active_services.aggregate(avg=Avg('duration'))['avg'] or 0
        active_services_count = active_services.count()

        # Статистика для тренеров
        active_trainers = Trainers.objects.filter(is_active=True)
        avg_experience = active_trainers.aggregate(avg=Avg('experience_years'))['avg'] or 0
        active_trainers_count = active_trainers.count()

        # Популярные специализации тренеров
        specializations = Trainers.objects.values('specialization').annotate(
            count=Count('specialization')
        ).order_by('-count')[:5]

        # Статистика для клиентов
        clients_with_email = Clients.objects.exclude(email='').exclude(email__isnull=True).count()
        email_percentage = (clients_with_email / clients_count * 100) if clients_count > 0 else 0

        # Средний возраст клиентов
        today = date.today()
        clients_with_birthdate = Clients.objects.exclude(birth_date__isnull=True)

        total_age = 0
        count_age = 0
        for client in clients_with_birthdate:
            if client.birth_date:
                age = today.year - client.birth_date.year - (
                        (today.month, today.day) < (client.birth_date.month, client.birth_date.day)
                )
                total_age += age
                count_age += 1

        avg_age = round(total_age / count_age, 1) if count_age > 0 else 0

        # Статистика для записей на занятия
        today_bookings = Bookings.objects.filter(booking_date=today, status='scheduled').count()
        upcoming_bookings = Bookings.objects.filter(
            booking_date__gte=today,
            status='scheduled'
        ).count()
        completed_bookings = Bookings.objects.filter(status='completed').count()
        cancelled_bookings = Bookings.objects.filter(status='cancelled').count()
        total_bookings = Bookings.objects.count()

        # Общая выручка
        total_revenue = Subscriptions.objects.aggregate(total=Sum('price_paid'))['total'] or 0

        # Популярные услуги
        popular_services = Services.objects.annotate(
            sub_count=Count('subscriptions')
        ).order_by('-sub_count')[:3]

        # Последние записи
        recent_bookings = Bookings.objects.select_related('client', 'service', 'trainer').order_by('-created_at')[:5]

        stats = {
            'clients_count': clients_count,
            'trainers_count': trainers_count,
            'services_count': services_count,
            'subscriptions_count': subscriptions_count,
            'recent_clients': Clients.objects.order_by('-created_at')[:5],
            'active_subscriptions': Subscriptions.objects.filter(status='active')[:5],
            'total_revenue': total_revenue,
            'today_bookings': today_bookings,

            # Расширенная статистика
            'active_services_count': active_services_count,
            'avg_price': avg_price,
            'avg_duration': avg_duration,
            'active_trainers_count': active_trainers_count,
            'avg_experience': avg_experience,
            'specializations': list(specializations),
            'clients_with_email': clients_with_email,
            'email_percentage': round(email_percentage, 1),
            'avg_age': avg_age,
            'upcoming_bookings': upcoming_bookings,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'total_bookings': total_bookings,
            'popular_services': popular_services,
            'recent_bookings': recent_bookings,
        }
    elif user.role == 'client':
        client_profile = get_or_create_client_profile(user)
        if client_profile:
            subscriptions = Subscriptions.objects.filter(client=client_profile)
            active_subscriptions = subscriptions.filter(status='active')
            today_bookings = Bookings.objects.filter(
                client=client_profile,
                booking_date=date.today(),
                status='scheduled'
            ).count()
            upcoming_bookings = Bookings.objects.filter(
                client=client_profile,
                booking_date__gte=date.today(),
                status='scheduled'
            ).count()

            stats = {
                'active_subscriptions_count': active_subscriptions.count(),
                'total_subscriptions': subscriptions.count(),
                'next_subscription': active_subscriptions.order_by('end_date').first(),
                'total_spent': subscriptions.aggregate(total=Sum('price_paid'))['total'] or 0,
                'client': client_profile,
                'today_bookings': today_bookings,
                'upcoming_bookings': upcoming_bookings,
            }
        else:
            stats = {
                'active_subscriptions_count': 0,
                'total_subscriptions': 0,
                'total_spent': 0,
                'client': None,
                'today_bookings': 0,
                'upcoming_bookings': 0,
            }
    else:
        stats = {}

    context = {
        'stats': stats,
        'user': user,
    }
    return render(request, 'index.html', context)


# ============== КЛИЕНТЫ (для менеджеров и админов) ==============
@login_required
@role_required(['admin', 'manager'])
def client_list(request):
    clients = Clients.objects.all()

    search = request.GET.get('search', '')
    if search:
        clients = clients.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )

    paginator = Paginator(clients, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика для клиентов
    total_clients = clients.count()
    clients_with_email = Clients.objects.exclude(email='').exclude(email__isnull=True).count()
    email_percentage = (clients_with_email / total_clients * 100) if total_clients > 0 else 0

    # Средний возраст клиентов
    today = date.today()
    clients_with_birthdate = Clients.objects.exclude(birth_date__isnull=True)

    total_age = 0
    count_age = 0
    for client in clients_with_birthdate:
        if client.birth_date:
            age = today.year - client.birth_date.year - (
                    (today.month, today.day) < (client.birth_date.month, client.birth_date.day)
            )
            total_age += age
            count_age += 1

    avg_age = round(total_age / count_age, 1) if count_age > 0 else 0

    # Статистика по регистрации
    week_ago = timezone.now() - timedelta(days=7)
    new_clients_week = Clients.objects.filter(created_at__gte=week_ago).count()

    context = {
        'clients': page_obj,
        'search_query': search,
        'total_clients': total_clients,
        'clients_with_email': clients_with_email,
        'email_percentage': round(email_percentage, 1),
        'avg_age': avg_age,
        'count_age': count_age,
        'new_clients_week': new_clients_week,
    }
    return render(request, 'clients/list.html', context)


@login_required
@role_required(['admin', 'manager'])
def client_create(request):
    """Создание нового клиента (для админов/менеджеров)"""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Клиент {client.full_name} успешно создан!')
            return redirect('client_list')
    else:
        form = ClientForm()

    context = {
        'form': form,
        'title': 'Добавление клиента'
    }
    return render(request, 'clients/create.html', context)


@login_required
@role_required(['admin', 'manager'])
def client_detail(request, pk):
    """Просмотр информации о клиенте (для админов/менеджеров)"""
    client = get_object_or_404(Clients, pk=pk)

    # Получаем абонементы клиента
    subscriptions = Subscriptions.objects.filter(client=client)
    # Получаем записи на занятия клиента
    bookings = Bookings.objects.filter(client=client).order_by('-booking_date', '-start_time')

    context = {
        'client': client,
        'subscriptions': subscriptions,
        'bookings': bookings,
    }
    return render(request, 'clients/detail.html', context)


@login_required
@role_required(['admin', 'manager'])
def client_edit(request, pk):
    """Редактирование клиента (для админов/менеджеров)"""
    client = get_object_or_404(Clients, pk=pk)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Клиент {client.full_name} успешно обновлён!')
            return redirect('client_detail', pk=client.pk)
    else:
        form = ClientForm(instance=client)

    context = {
        'form': form,
        'client': client,
        'title': f'Редактирование клиента: {client.full_name}'
    }
    return render(request, 'clients/edit.html', context)


@login_required
@admin_required
def client_delete(request, pk):
    """Удаление клиента (только для админов)"""
    client = get_object_or_404(Clients, pk=pk)

    if request.method == 'POST':
        client_name = client.full_name
        client.delete()
        messages.success(request, f'Клиент {client_name} успешно удалён!')
        return redirect('client_list')

    context = {
        'client': client,
    }
    return render(request, 'clients/delete.html', context)


# ============== ТРЕНЕРЫ (для менеджеров и админов) ==============
@login_required
@role_required(['admin', 'manager'])
def trainer_list(request):
    """Список тренеров (для админов/менеджеров)"""
    trainers = Trainers.objects.all()

    search = request.GET.get('search', '')
    if search:
        trainers = trainers.filter(
            Q(full_name__icontains=search) |
            Q(specialization__icontains=search) |
            Q(phone__icontains=search)
        )

    paginator = Paginator(trainers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика для тренеров
    total_trainers = trainers.count()
    active_trainers = Trainers.objects.filter(is_active=True)
    active_count = active_trainers.count()

    # Средний стаж
    avg_experience = active_trainers.aggregate(avg=Avg('experience_years'))['avg'] or 0

    # Специализации
    specializations = Trainers.objects.values('specialization').annotate(
        count=Count('specialization')
    ).order_by('-count')

    # Популярные специализации (топ-3)
    top_specializations = specializations[:3]

    # Тренеры, нанятые за последнюю неделю
    week_ago = timezone.now() - timedelta(days=7)
    new_trainers_week = Trainers.objects.filter(created_at__gte=week_ago).count()

    context = {
        'trainers': page_obj,
        'search_query': search,
        'total_trainers': total_trainers,
        'active_count': active_count,
        'avg_experience': round(avg_experience, 1),
        'specializations': list(specializations),
        'top_specializations': list(top_specializations),
        'new_trainers_week': new_trainers_week,
    }
    return render(request, 'trainers/list.html', context)


@login_required
@role_required(['admin', 'manager'])
def trainer_create(request):
    """Создание нового тренера (для админов/менеджеров)"""
    if request.method == 'POST':
        form = TrainerForm(request.POST)
        if form.is_valid():
            trainer = form.save()
            messages.success(request, f'Тренер {trainer.full_name} успешно создан!')
            return redirect('trainer_list')
    else:
        form = TrainerForm()

    context = {
        'form': form,
        'title': 'Добавление тренера'
    }
    return render(request, 'trainers/create.html', context)


@login_required
@role_required(['admin', 'manager'])
def trainer_detail(request, pk):
    """Просмотр информации о тренере (для админов/менеджеров)"""
    trainer = get_object_or_404(Trainers, pk=pk)

    # Получаем записи на занятия с этим тренером
    bookings = Bookings.objects.filter(trainer=trainer).order_by('-booking_date', '-start_time')

    context = {
        'trainer': trainer,
        'bookings': bookings,
    }
    return render(request, 'trainers/detail.html', context)


@login_required
@role_required(['admin', 'manager'])
def trainer_edit(request, pk):
    """Редактирование тренера (для админов/менеджеров)"""
    trainer = get_object_or_404(Trainers, pk=pk)

    if request.method == 'POST':
        form = TrainerForm(request.POST, instance=trainer)
        if form.is_valid():
            trainer = form.save()
            messages.success(request, f'Тренер {trainer.full_name} успешно обновлён!')
            return redirect('trainer_detail', pk=trainer.pk)
    else:
        form = TrainerForm(instance=trainer)

    context = {
        'form': form,
        'trainer': trainer,
        'title': f'Редактирование тренера: {trainer.full_name}'
    }
    return render(request, 'trainers/edit.html', context)


@login_required
@admin_required
def trainer_delete(request, pk):
    """Удаление тренера (только для админов)"""
    trainer = get_object_or_404(Trainers, pk=pk)

    if request.method == 'POST':
        trainer_name = trainer.full_name
        trainer.delete()
        messages.success(request, f'Тренер {trainer_name} успешно удалён!')
        return redirect('trainer_list')

    context = {
        'trainer': trainer,
    }
    return render(request, 'trainers/delete.html', context)


# ============== УСЛУГИ (для менеджеров и админов) ==============
@login_required
@role_required(['admin', 'manager'])
def service_list_admin(request):
    """Список услуг для админов/менеджеров (с неактивными тоже)"""
    services = Services.objects.all()

    search = request.GET.get('search', '')
    if search:
        services = services.filter(
            Q(service_name__icontains=search) |
            Q(description__icontains=search)
        )

    # Статистика для услуг
    total_services = services.count()
    active_services = Services.objects.filter(is_active=True)
    active_count = active_services.count()

    # Средняя цена и длительность (только активные услуги)
    avg_price = active_services.aggregate(avg=Avg('price'))['avg'] or 0
    avg_duration = active_services.aggregate(avg=Avg('duration'))['avg'] or 0

    # Самая дорогая и самая дешевая услуга
    most_expensive = active_services.order_by('-price').first()
    cheapest = active_services.order_by('price').first()

    # Услуги, добавленные за последнюю неделю
    week_ago = timezone.now() - timedelta(days=7)
    new_services_week = Services.objects.filter(created_at__gte=week_ago).count()

    context = {
        'services': services,
        'search_query': search,
        'total_services': total_services,
        'active_count': active_count,
        'avg_price': round(avg_price, 2),
        'avg_duration': round(avg_duration, 1),
        'most_expensive': most_expensive,
        'cheapest': cheapest,
        'new_services_week': new_services_week,
        'is_admin': True,
    }
    return render(request, 'services/list.html', context)


@login_required
@role_required(['admin', 'manager'])
def service_create(request):
    """Создание новой услуги (для админов/менеджеров)"""
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Услуга "{service.service_name}" успешно создана!')
            return redirect('service_list_admin')
    else:
        form = ServiceForm()

    context = {
        'form': form,
        'title': 'Добавление услуги'
    }
    return render(request, 'services/create.html', context)


@login_required
@role_required(['admin', 'manager'])
def service_detail_admin(request, pk):
    """Просмотр информации об услуге (для админов/менеджеров)"""
    service = get_object_or_404(Services, pk=pk)

    # Получаем абонементы по этой услуге
    subscriptions = Subscriptions.objects.filter(service=service)
    # Получаем записи на занятия по этой услуге
    bookings = Bookings.objects.filter(service=service).order_by('-booking_date', '-start_time')

    context = {
        'service': service,
        'subscriptions': subscriptions,
        'bookings': bookings,
        'is_admin': True,
    }
    return render(request, 'services/detail.html', context)


@login_required
@role_required(['admin', 'manager'])
def service_edit(request, pk):
    """Редактирование услуги (для админов/менеджеров)"""
    service = get_object_or_404(Services, pk=pk)

    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Услуга "{service.service_name}" успешно обновлена!')
            return redirect('service_list_admin')
    else:
        form = ServiceForm(instance=service)

    context = {
        'form': form,
        'service': service,
        'title': f'Редактирование услуги: {service.service_name}'
    }
    return render(request, 'services/edit.html', context)


@login_required
@admin_required
def service_delete(request, pk):
    """Удаление услуги (только для админов)"""
    service = get_object_or_404(Services, pk=pk)

    if request.method == 'POST':
        service_name = service.service_name
        service.delete()
        messages.success(request, f'Услуга "{service_name}" успешно удалена!')
        return redirect('service_list_admin')

    context = {
        'service': service,
    }
    return render(request, 'services/delete.html', context)


# ============== АБОНЕМЕНТЫ ==============
@login_required
def subscription_list(request):
    user = request.user

    if user.role == 'client':
        # Клиент видит только свои абонементы
        client_profile = get_or_create_client_profile(user)
        if client_profile:
            subscriptions = Subscriptions.objects.filter(client=client_profile)
        else:
            subscriptions = Subscriptions.objects.none()
    else:
        # Админы и менеджеры видят все абонементы
        subscriptions = Subscriptions.objects.all()

    # Фильтрация
    status_filter = request.GET.get('status', '')
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)

    # Поиск (только для админов/менеджеров)
    search = request.GET.get('search', '')
    if search and user.role != 'client':
        subscriptions = subscriptions.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(service__service_name__icontains=search)
        )

    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    subscriptions = subscriptions.order_by(sort_by)

    # Статистика
    total_count = subscriptions.count()
    active_count = subscriptions.filter(status='active').count()
    expired_count = subscriptions.filter(status='expired').count()
    cancelled_count = subscriptions.filter(status='cancelled').count()
    total_revenue = subscriptions.aggregate(total=Sum('price_paid'))['total'] or 0

    # Пагинация
    paginator = Paginator(subscriptions, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'subscriptions': page_obj,
        'page_obj': page_obj,
        'search_query': search,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'STATUS_CHOICES': Subscriptions.STATUS_CHOICES,
        'active_count': active_count,
        'expired_count': expired_count,
        'cancelled_count': cancelled_count,
        'total_revenue': total_revenue,
        'total_count': total_count,
        'is_client': user.role == 'client',
    }
    return render(request, 'subscriptions/list.html', context)


@login_required
@role_required(['admin', 'manager'])
def subscription_create(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            subscription = form.save()
            messages.success(request, f'Абонемент #{subscription.subscription_id} создан!')
            return redirect('subscription_detail', pk=subscription.pk)
    else:
        form = SubscriptionForm()

    context = {'form': form}
    return render(request, 'subscriptions/create.html', context)


@login_required
def subscription_detail(request, pk):
    subscription = get_object_or_404(Subscriptions, pk=pk)
    user = request.user

    # Проверка прав доступа для клиентов
    if user.role == 'client':
        client_profile = get_or_create_client_profile(user)
        if not client_profile or client_profile != subscription.client:
            messages.error(request, 'У вас нет прав для просмотра этого абонемента')
            return redirect('my_subscriptions')

    # Рассчитываем оставшиеся дни
    today = date.today()
    days_left = (subscription.end_date - today).days if subscription.end_date > today else 0

    context = {
        'subscription': subscription,
        'days_left': days_left,
        'is_expired': days_left < 0,
        'can_edit': user.role in ['admin', 'manager'],
    }
    return render(request, 'subscriptions/detail.html', context)


@login_required
@role_required(['admin', 'manager'])
def subscription_edit(request, pk):
    subscription = get_object_or_404(Subscriptions, pk=pk)

    if request.method == 'POST':
        form = SubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            subscription = form.save()
            messages.success(request, f'Абонемент #{subscription.subscription_id} обновлён!')
            return redirect('subscription_detail', pk=subscription.pk)
    else:
        form = SubscriptionForm(instance=subscription)

    context = {'form': form, 'subscription': subscription}
    return render(request, 'subscriptions/edit.html', context)


@login_required
@admin_required
def subscription_delete(request, pk):
    subscription = get_object_or_404(Subscriptions, pk=pk)

    if request.method == 'POST':
        sub_id = subscription.subscription_id
        subscription.delete()
        messages.success(request, f'Абонемент #{sub_id} удалён!')
        return redirect('subscription_list')

    return render(request, 'subscriptions/delete.html', {'subscription': subscription})


# ============== ДЛЯ КЛИЕНТОВ ==============
@login_required
@client_required
def my_subscriptions(request):
    """Показывает абонементы текущего клиента"""
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    subscriptions = Subscriptions.objects.filter(client=client_profile).order_by('-created_at')

    # Рассчитываем оставшиеся дни для активных абонементов
    today = date.today()
    for sub in subscriptions:
        if sub.status == 'active':
            sub.days_left = (sub.end_date - today).days if sub.end_date > today else 0

    context = {
        'subscriptions': subscriptions,
        'client': client_profile,
        'active_count': subscriptions.filter(status='active').count(),
        'total_count': subscriptions.count(),
        'expired_count': subscriptions.filter(status='expired').count(),
        'cancelled_count': subscriptions.filter(status='cancelled').count(),
    }
    return render(request, 'clients/my_subscriptions.html', context)


@login_required
@client_required
def my_schedule(request):
    """Показывает расписание занятий клиента"""
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    # Получаем активные абонементы клиента
    active_subscriptions = Subscriptions.objects.filter(
        client=client_profile,
        status='active'
    )

    # Получаем предстоящие записи клиента
    upcoming_bookings = Bookings.objects.filter(
        client=client_profile,
        booking_date__gte=date.today(),
        status='scheduled'
    ).order_by('booking_date', 'start_time')

    # Получаем прошедшие записи клиента
    past_bookings = Bookings.objects.filter(
        client=client_profile,
        booking_date__lt=date.today(),
        status__in=['scheduled', 'completed', 'no_show']
    ).order_by('-booking_date', '-start_time')[:10]

    # Получаем записи на сегодня
    today_bookings = Bookings.objects.filter(
        client=client_profile,
        booking_date=date.today(),
        status='scheduled'
    ).count()

    # Получаем активные услуги для быстрой записи
    active_services = Services.objects.filter(is_active=True)[:4]

    context = {
        'active_subscriptions': active_subscriptions,
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        'today_bookings': today_bookings,
        'active_services': active_services,
        'client': client_profile,
        'has_active_subscriptions': active_subscriptions.exists(),
        'has_upcoming_bookings': upcoming_bookings.exists(),
    }
    return render(request, 'clients/my_schedule.html', context)


@login_required
@client_required
def buy_subscription(request):
    """Покупка нового абонемента"""
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    if request.method == 'POST':
        service_id = request.POST.get('service')
        months = int(request.POST.get('months', 1))

        try:
            service = Services.objects.get(pk=service_id, is_active=True)

            # Создаем абонемент
            start_date = date.today()
            end_date = start_date + timedelta(days=30 * months)
            price_paid = service.price * months

            subscription = Subscriptions.objects.create(
                client=client_profile,
                service=service,
                start_date=start_date,
                end_date=end_date,
                price_paid=price_paid,
                status='active'
            )

            messages.success(request, f'Абонемент #{subscription.subscription_id} успешно приобретен!')
            return redirect('my_subscriptions')

        except Services.DoesNotExist:
            messages.error(request, 'Услуга не найдена или неактивна')
        except Exception as e:
            messages.error(request, f'Ошибка при покупке: {str(e)}')
            return redirect('buy_subscription')

    # GET запрос - показываем форму
    services = Services.objects.filter(is_active=True)

    # Получаем активные абонементы клиента
    active_subscriptions = Subscriptions.objects.filter(
        client=client_profile,
        status='active'
    )

    context = {
        'services': services,
        'client': client_profile,
        'active_subscriptions': active_subscriptions,
    }
    return render(request, 'clients/buy_subscription.html', context)


@login_required
@client_required
def cancel_subscription(request, pk):
    """Отмена абонемента клиентом"""
    subscription = get_object_or_404(Subscriptions, pk=pk)
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    # Проверяем, что абонемент принадлежит клиенту
    if client_profile != subscription.client:
        messages.error(request, 'У вас нет прав для отмены этого абонемента')
        return redirect('my_subscriptions')

    if subscription.status == 'cancelled':
        messages.warning(request, 'Этот абонемент уже отменен')
        return redirect('my_subscriptions')

    if request.method == 'POST':
        subscription.status = 'cancelled'
        subscription.save()
        messages.success(request, f'Абонемент #{subscription.subscription_id} отменен')
        return redirect('my_subscriptions')

    context = {'subscription': subscription}
    return render(request, 'clients/cancel_subscription.html', context)


# ============== УСЛУГИ (доступны всем) ==============
@login_required
def service_list(request):
    """Список услуг для всех пользователей (только активные)"""
    services = Services.objects.filter(is_active=True)

    search = request.GET.get('search', '')
    if search:
        services = services.filter(
            Q(service_name__icontains=search) |
            Q(description__icontains=search)
        )

    # Статистика для услуг (публичная версия)
    total_services = services.count()

    # Средняя цена и длительность
    avg_price = services.aggregate(avg=Avg('price'))['avg'] or 0
    avg_duration = services.aggregate(avg=Avg('duration'))['avg'] or 0

    # Ценовой диапазон
    price_range = services.aggregate(
        min_price=Min('price'),
        max_price=Max('price')
    )

    # Самые популярные услуги (по количеству абонементов)
    popular_services = Services.objects.annotate(
        sub_count=Count('subscriptions')
    ).order_by('-sub_count')[:3]

    context = {
        'services': services,
        'search_query': search,
        'total_services': total_services,
        'avg_price': round(avg_price, 2),
        'avg_duration': round(avg_duration, 1),
        'min_price': price_range['min_price'] or 0,
        'max_price': price_range['max_price'] or 0,
        'popular_services': popular_services,
        'is_admin': False,
    }
    return render(request, 'services/list.html', context)


@login_required
def service_detail(request, pk):
    service = get_object_or_404(Services, pk=pk)

    # Для клиентов показываем только их абонементы по этой услуге
    client_subscriptions = None
    if request.user.role == 'client':
        client_profile = get_or_create_client_profile(request.user)
        if client_profile:
            client_subscriptions = Subscriptions.objects.filter(
                client=client_profile,
                service=service
            )

    context = {
        'service': service,
        'client_subscriptions': client_subscriptions,
        'is_client': request.user.role == 'client',
        'is_admin': False,
    }
    return render(request, 'services/detail.html', context)


# ============== ЗАПИСЬ НА ЗАНЯТИЯ ==============
@login_required
@client_required
def book_training(request):
    """Запись на занятие"""
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    if request.method == 'POST':
        form = BookingForm(request.POST, client=client_profile)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.client = client_profile

            # Устанавливаем значение по умолчанию для room, если оно не указано
            if not booking.room:
                booking.room = 'hall1'

            booking.status = 'scheduled'
            booking.save()

            messages.success(request,
                             f'Вы успешно записались на занятие "{booking.service.service_name}" '
                             f'{booking.booking_date.strftime("%d.%m.%Y")} в {booking.start_time.strftime("%H:%M")}!'
                             )
            return redirect('my_schedule')
        else:
            # Показываем ошибки формы
            for field, errors in form.errors.items():
                # Получаем красивое имя поля
                if field in form.fields:
                    field_label = form.fields[field].label
                else:
                    field_label = field.replace('_', ' ').capitalize()

                for error in errors:
                    messages.error(request, f'{field_label}: {error}')
    else:
        form = BookingForm(client=client_profile)

    # Получаем все активные услуги для отображения в информационной панели
    active_services = Services.objects.filter(is_active=True)

    # Сортируем услуги для информационной панели
    active_subscriptions = Subscriptions.objects.filter(
        client=client_profile,
        status='active'
    )

    # Если есть активные абонементы, помечаем соответствующие услуги
    if active_subscriptions.exists():
        active_services_ids = active_subscriptions.values_list('service', flat=True)

    context = {
        'form': form,
        'client': client_profile,
        'active_subscriptions': active_subscriptions,
        'active_services': active_services,
        'title': 'Запись на занятие',
        'room_choices': Bookings.ROOM_CHOICES,
    }
    return render(request, 'clients/book_training.html', context)


@login_required
@client_required
def quick_book(request, service_id=None):
    """Быстрая запись на занятие"""
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    if request.method == 'POST':
        form = QuickBookingForm(request.POST)
        if form.is_valid():
            try:
                booking = form.save(client_profile)

                messages.success(request,
                                 f'Вы успешно записались на занятие "{booking.service.service_name}" '
                                 f'{booking.booking_date.strftime("%d.%m.%Y")} в {booking.start_time.strftime("%H:%M")}!'
                                 )
                return redirect('my_schedule')
            except Exception as e:
                messages.error(request, f'Ошибка при создании записи: {str(e)}')
        else:
            # Показываем все ошибки формы
            for field, errors in form.errors.items():
                # Получаем красивое имя поля
                if field in form.fields:
                    field_label = form.fields[field].label
                else:
                    field_label = field.replace('_', ' ').capitalize()

                for error in errors:
                    messages.error(request, f'{field_label}: {error}')
    else:
        initial_data = {}
        if service_id:
            try:
                service = Services.objects.get(pk=service_id, is_active=True)
                initial_data['service'] = service
            except Services.DoesNotExist:
                pass

        form = QuickBookingForm(initial=initial_data)

    # Получаем все активные услуги
    active_services = Services.objects.filter(is_active=True)

    active_subscriptions = Subscriptions.objects.filter(
        client=client_profile,
        status='active'
    )

    today_bookings = Bookings.objects.filter(
        client=client_profile,
        booking_date=date.today(),
        status='scheduled'
    )

    # Получаем выбор залов из формы
    from .forms import ROOM_CHOICES

    context = {
        'form': form,
        'client': client_profile,
        'active_subscriptions': active_subscriptions,
        'today_bookings': today_bookings,
        'room_choices': ROOM_CHOICES,
        'active_services': active_services,
        'title': 'Быстрая запись на занятие'
    }
    return render(request, 'clients/quick_book.html', context)


@login_required
@client_required
def cancel_booking(request, pk):
    """Отмена записи на занятие"""
    booking = get_object_or_404(Bookings, pk=pk)
    user = request.user
    client_profile = get_or_create_client_profile(user)

    if not client_profile:
        messages.error(request, 'Профиль клиента не найден')
        return redirect('profile')

    # Проверяем, что запись принадлежит клиенту
    if client_profile != booking.client:
        messages.error(request, 'У вас нет прав для отмены этой записи')
        return redirect('my_schedule')

    if booking.status == 'cancelled':
        messages.warning(request, 'Эта запись уже отменена')
        return redirect('my_schedule')

    # Проверяем, можно ли отменить запись
    if not booking.can_be_cancelled:
        messages.error(request, 'Эту запись нельзя отменить. Пожалуйста, свяжитесь с администратором.')
        return redirect('my_schedule')

    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()

        messages.success(request,
                         f'Запись на занятие "{booking.service.service_name}" '
                         f'{booking.booking_date} в {booking.start_time.strftime("%H:%M")} отменена.'
                         )
        return redirect('my_schedule')

    context = {
        'booking': booking,
        'client': client_profile,
    }
    return render(request, 'clients/cancel_booking.html', context)


@login_required
@role_required(['admin', 'manager'])
def manage_bookings(request):
    """Управление записями для админов/менеджеров"""
    bookings = Bookings.objects.all().order_by('-booking_date', '-start_time')

    # Фильтрация
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')

    if status_filter:
        bookings = bookings.filter(status=status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_date=filter_date)
        except ValueError:
            pass

    # Поиск
    search = request.GET.get('search', '')
    if search:
        bookings = bookings.filter(
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search) |
            Q(service__service_name__icontains=search) |
            Q(trainer__full_name__icontains=search)
        )

    paginator = Paginator(bookings, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика для записей
    total_bookings = Bookings.objects.count()

    # Статистика по статусам
    scheduled_count = Bookings.objects.filter(status='scheduled').count()
    completed_count = Bookings.objects.filter(status='completed').count()
    cancelled_count = Bookings.objects.filter(status='cancelled').count()
    no_show_count = Bookings.objects.filter(status='no_show').count()

    # Записи на сегодня
    today = date.today()
    today_bookings = Bookings.objects.filter(booking_date=today).count()

    # Записи на завтра
    tomorrow = today + timedelta(days=1)
    tomorrow_bookings = Bookings.objects.filter(booking_date=tomorrow).count()

    # Статистика по залам
    room_stats = Bookings.objects.values('room').annotate(
        count=Count('room')
    ).order_by('-count')

    # Популярные услуги для записи
    popular_services_booking = Services.objects.annotate(
        booking_count=Count('bookings')
    ).order_by('-booking_count')[:3]

    context = {
        'bookings': page_obj,
        'page_obj': page_obj,
        'search_query': search,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'STATUS_CHOICES': Bookings.STATUS_CHOICES,

        # Статистика
        'total_bookings': total_bookings,
        'scheduled_count': scheduled_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'no_show_count': no_show_count,
        'today_bookings': today_bookings,
        'tomorrow_bookings': tomorrow_bookings,
        'room_stats': list(room_stats),
        'popular_services_booking': popular_services_booking,
    }
    return render(request, 'bookings/list.html', context)


@login_required
@role_required(['admin', 'manager'])
def update_booking_status(request, pk, status):
    """Обновление статуса записи (для админов/менеджеров)"""
    booking = get_object_or_404(Bookings, pk=pk)

    if status in dict(Bookings.STATUS_CHOICES):
        old_status = booking.get_status_display()
        booking.status = status
        booking.save()

        messages.success(request,
                         f'Статус записи #{booking.booking_id} изменен с "{old_status}" на "{booking.get_status_display()}"'
                         )

    return redirect('manage_bookings')


# ============== ДОПОЛНИТЕЛЬНЫЕ СТРАНИЦЫ ==============
@login_required
@role_required(['admin', 'manager'])
def schedule(request):
    """Расписание для менеджеров"""
    # Получаем записи на сегодня и ближайшие дни
    today = date.today()
    week_later = today + timedelta(days=7)

    bookings = Bookings.objects.filter(
        booking_date__range=[today, week_later],
        status='scheduled'
    ).order_by('booking_date', 'start_time')

    # Группируем по дням
    schedule_data = {}
    for booking in bookings:
        day = booking.booking_date.strftime('%d.%m.%Y')
        if day not in schedule_data:
            schedule_data[day] = []

        schedule_data[day].append({
            'time': f'{booking.start_time.strftime("%H:%M")} - {booking.end_time.strftime("%H:%M")}',
            'service': booking.service.service_name,
            'trainer': booking.trainer.full_name if booking.trainer else 'Не назначен',
            'clients': [booking.client.full_name],
            'room': booking.room,
            'booking': booking,
        })

    # Преобразуем в список для шаблона
    schedule_list = []
    for day, items in schedule_data.items():
        schedule_list.append({
            'date': day,
            'items': items
        })

    # Сортируем по дате
    schedule_list.sort(key=lambda x: datetime.strptime(x['date'], '%d.%m.%Y'))

    context = {
        'schedule': schedule_list,
        'today': today.strftime('%d.%m.%Y'),
        'week_later': week_later.strftime('%d.%m.%Y'),
    }
    return render(request, 'schedule.html', context)


@login_required
def settings(request):
    """Настройки системы"""
    user = request.user

    if request.method == 'POST':
        # Здесь будет сохранение настроек
        messages.success(request, 'Настройки сохранены!')
        return redirect('settings')

    context = {
        'user': user,
        'can_manage_settings': user.role in ['admin', 'manager'],
    }
    return render(request, 'settings.html', context)


# ============== API для AJAX ==============
@login_required
def update_profile(request):
    """Обновление профиля через AJAX"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user = request.user
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)

        birth_date = request.POST.get('birth_date')
        if birth_date:
            try:
                user.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except ValueError:
                pass

        user.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def get_service_price(request, service_id):
    """Получение цены услуги для AJAX"""
    try:
        service = Services.objects.get(pk=service_id, is_active=True)
        return JsonResponse({'price': float(service.price)})
    except Services.DoesNotExist:
        return JsonResponse({'error': 'Service not found'}, status=404)


@login_required
def get_available_times(request):
    """Получение доступного времени для записи"""
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        date_str = request.GET.get('date')
        service_id = request.GET.get('service_id')

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Определяем рабочие часы
            work_hours = [
                ('10:00', '11:30'),
                ('12:00', '13:30'),
                ('16:00', '17:30'),
                ('18:00', '19:30'),
                ('20:00', '21:30'),
            ]

            # Проверяем занятые слоты
            booked_slots = Bookings.objects.filter(
                booking_date=booking_date,
                status='scheduled'
            )

            # Если указана услуга, учитываем длительность
            if service_id:
                try:
                    service = Services.objects.get(pk=service_id)
                    # Здесь можно добавить логику проверки доступности тренеров и залов
                    pass
                except Services.DoesNotExist:
                    pass

            # Формируем список доступных слотов
            available_slots = []
            for start_str, end_str in work_hours:
                start_time = datetime.strptime(start_str, '%H:%M').time()
                end_time = datetime.strptime(end_str, '%H:%M').time()

                # Проверяем, не занят ли этот слот
                is_available = True
                for booking in booked_slots:
                    if (start_time < booking.end_time and end_time > booking.start_time):
                        is_available = False
                        break

                if is_available:
                    available_slots.append({
                        'start': start_str,
                        'end': end_str,
                        'display': f'{start_str} - {end_str}'
                    })

            return JsonResponse({
                'success': True,
                'available_slots': available_slots,
                'date': date_str
            })

        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)

    return JsonResponse({'error': 'Invalid request'}, status=400)


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
@login_required
@role_required(['admin', 'manager'])
def link_client_to_user(request, user_id):
    """Привязывает профиль клиента к пользователю (для админов)"""
    user = get_object_or_404(Users, pk=user_id)

    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        if client_id:
            try:
                client = Clients.objects.get(pk=client_id)
                user.client_profile = client
                user.save()
                messages.success(request, f'Профиль клиента {client.full_name} привязан к пользователю {user.userName}')
                return redirect('profile')
            except Clients.DoesNotExist:
                messages.error(request, 'Клиент не найден')

    # Показываем форму выбора клиента
    clients = Clients.objects.all()

    context = {
        'user': user,
        'clients': clients,
    }
    return render(request, 'admin/link_client.html', context)


# Новая функция для привязки профиля клиента
@login_required
def link_client_profile(request):
    """Страница для привязки профиля клиента"""
    user = request.user

    if user.role != 'client':
        messages.error(request, 'Эта страница только для клиентов')
        return redirect('index')

    if user.client_profile:
        return redirect('my_subscriptions')

    if request.method == 'POST':
        client_profile = get_or_create_client_profile(user)
        if client_profile:
            messages.success(request, 'Профиль успешно создан! Теперь вы можете использовать все функции клиента.')
            return redirect('my_subscriptions')
        else:
            messages.error(request, 'Ошибка при создании профиля. Обратитесь к администратору.')

    return render(request, 'clients/link_profile.html', {'user': user})


# ============== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==============
@login_required
def get_client_info(request, client_id):
    """Получение информации о клиенте для AJAX"""
    try:
        client = Clients.objects.get(pk=client_id)
        return JsonResponse({
            'success': True,
            'client': {
                'id': client.client_id,
                'full_name': client.full_name,
                'phone': client.phone,
                'email': client.email,
                'birth_date': client.birth_date.strftime('%Y-%m-%d') if client.birth_date else None,
            }
        })
    except Clients.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Client not found'})


@login_required
@client_required
def create_booking_ajax(request):
    """Создание записи на занятие через AJAX"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user = request.user
        client_profile = get_or_create_client_profile(user)

        if not client_profile:
            return JsonResponse({'success': False, 'error': 'Профиль клиента не найден'})

        try:
            # Получаем данные из POST запроса
            service_id = request.POST.get('service_id')
            booking_date = request.POST.get('booking_date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            trainer_id = request.POST.get('trainer_id')

            # Валидация данных
            if not all([service_id, booking_date, start_time, end_time]):
                return JsonResponse({'success': False, 'error': 'Не все обязательные поля заполнены'})

            # Получаем объекты
            service = Services.objects.get(pk=service_id, is_active=True)
            booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            start_time_obj = datetime.strptime(start_time, '%H:%M').time()
            end_time_obj = datetime.strptime(end_time, '%H:%M').time()

            trainer = None
            if trainer_id:
                trainer = Trainers.objects.get(pk=trainer_id, is_active=True)

            # Проверяем, нет ли уже записи на это время
            existing_bookings = Bookings.objects.filter(
                client=client_profile,
                booking_date=booking_date_obj,
                status='scheduled'
            )

            for booking in existing_bookings:
                if (start_time_obj < booking.end_time and end_time_obj > booking.start_time):
                    return JsonResponse({
                        'success': False,
                        'error': f'У вас уже есть запись на это время: {booking.start_time.strftime("%H:%M")} - {booking.end_time.strftime("%H:%M")}'
                    })

            # Создаем запись
            booking = Bookings.objects.create(
                client=client_profile,
                service=service,
                trainer=trainer,
                booking_date=booking_date_obj,
                start_time=start_time_obj,
                end_time=end_time_obj,
                room='Зал 1',
                status='scheduled',
                notes='Запись создана через форму на сайте'
            )

            return JsonResponse({
                'success': True,
                'booking_id': booking.booking_id,
                'message': f'Вы успешно записались на занятие "{service.service_name}" {booking_date_obj.strftime("%d.%m.%Y")} в {start_time_obj.strftime("%H:%M")}!',
                'redirect_url': reverse('my_schedule')
            })

        except Services.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Услуга не найдена или неактивна'})
        except Trainers.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Тренер не найден или неактивен'})
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Ошибка формата данных: {str(e)}'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Ошибка при создании записи: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


# ============== ОТЧЕТЫ (Практическая работа №8) ==============
@login_required
@role_required(['admin', 'manager'])
def reports_dashboard(request):
    """Главная страница отчетов"""
    # Получаем реальную статистику
    real_stats = ReportGenerator.get_real_data_stats()

    # Статистика за последний месяц
    month_ago = date.today() - timedelta(days=30)
    new_clients_month = Clients.objects.filter(created_at__gte=month_ago).count()
    new_subscriptions_month = Subscriptions.objects.filter(created_at__gte=month_ago).count()

    # Популярная услуга
    popular_service = Services.objects.annotate(
        sub_count=Count('subscriptions')
    ).order_by('-sub_count').first()

    # Выручка за месяц
    month_revenue = Subscriptions.objects.filter(
        created_at__gte=month_ago
    ).aggregate(total=Sum('price_paid'))['total'] or 0

    # Генерируем тестовые данные для демонстрации
    test_users = ReportGenerator.generate_test_users(20)
    test_users_df = pd.DataFrame(test_users)

    context = {
        'real_stats': real_stats,
        'new_clients_month': new_clients_month,
        'new_subscriptions_month': new_subscriptions_month,
        'month_revenue': month_revenue,
        'popular_service': popular_service,
        'test_users': test_users_df.head(10).to_html(classes='table table-striped', index=False, escape=False),
        'title': 'Отчёты',
    }
    return render(request, 'reports/dashboard.html', context)


@login_required
@role_required(['admin', 'manager'])
def reports_filter(request):
    """Страница с фильтрацией данных"""
    context = {
        'title': 'Фильтрация данных',
        'filter_results': None,
        'filter_name': None,
    }

    if request.method == 'POST':
        filter_type = request.POST.get('filter_type')
        data_type = request.POST.get('data_type', 'users')
        count = int(request.POST.get('count', 1000))

        # Генерируем данные
        df = ReportGenerator.create_report_dataframe(data_type, count)

        # Применяем выбранный фильтр
        filter_name = ""
        df_filtered = None

        if filter_type == '1':  # Фильтр 1: wallet > 100000
            df_filtered = df[df['wallet'] > 100000]
            filter_name = "Кошелек > 100000"
        elif filter_type == '2':  # Фильтр 2: age 18-25 AND wallet > 125000
            df_filtered = df[(df['age'] >= 18) & (df['age'] <= 25) & (df['wallet'] > 125000)]
            filter_name = "Возраст 18-25 и кошелек > 125000"
        elif filter_type == '3':  # Фильтр 3: age > 50 AND registration_date 2018-2023
            df['registration_date'] = pd.to_datetime(df['registration_date'])
            df_filtered = df[(df['age'] > 50) &
                             (df['registration_date'].between('2018-01-01', '2023-01-01'))]
            filter_name = "Возраст > 50 и регистрация 2018-2023"
        elif filter_type == '4':  # Фильтр 4: email contains gmail AND wallet > 50000 AND is_subscribed
            df_filtered = df[df['email'].str.contains('gmail', na=False) &
                             (df['wallet'] > 50000) &
                             (df['is_subscribed'] == True)]
            filter_name = "Gmail, кошелек > 50000, с подпиской"
        elif filter_type == '5':  # Фильтр 5: age = 18 AND email contains yahoo AND wallet < 25000
            df_filtered = df[(df['age'] == 18) &
                             (df['email'].str.contains('yahoo', na=False)) &
                             (df['wallet'] < 25000)]
            filter_name = "Возраст 18, Yahoo, кошелек < 25000"
        elif filter_type == '6':  # Фильтр 6: age > 100 AND last_online = today
            today = datetime.now().date()
            df['last_online'] = pd.to_datetime(df['last_online'])
            df['last_online_date'] = df['last_online'].dt.date
            df_filtered = df[(df['age'] > 100) & (df['last_online_date'] == today)]
            filter_name = "Возраст > 100 и был сегодня"
        elif filter_type == '7':  # Фильтр 7: wallet > 100000, сортировка по registration_date
            df['registration_date'] = pd.to_datetime(df['registration_date'])
            df_filtered = df[df['wallet'] > 100000].sort_values('registration_date').head(50)
            filter_name = "Кошелек > 100000 (первые 50 по дате регистрации)"
        elif filter_type == '8':  # Фильтр 8: день рождения сегодня, age > 21
            today = datetime.now()
            df['birth_date'] = pd.to_datetime(df['birth_date'])
            df_filtered = df[(df['birth_date'].dt.day == today.day) &
                             (df['birth_date'].dt.month == today.month) &
                             (df['age'] > 21)]
            filter_name = "День рождения сегодня, возраст > 21"
        elif filter_type == '9':  # Фильтр 9: is_subscribed AND total_spent > 400000 AND age > 25
            df_filtered = df[(df['is_subscribed'] == True) &
                             (df['total_spent'] > 400000) &
                             (df['age'] > 25)].sort_values('registration_date').head(10)
            filter_name = "С подпиской, потратил > 400000, возраст > 25"
        else:
            df_filtered = df.head(100)
            filter_name = "Первые 100 записей"

        # Сохраняем в CSV
        if df_filtered is not None:
            # Для отображения в HTML
            html_table = ReportGenerator.dataframe_to_html(df_filtered)

            # Сохраняем в сессию для экспорта
            request.session['last_filter_df'] = df_filtered.to_json()
            request.session['last_filter_name'] = filter_name

            context.update({
                'filter_results': html_table,
                'filter_name': filter_name,
                'filtered_count': len(df_filtered),
                'total_count': len(df),
                'filter_type': filter_type,
                'data_type': data_type,
            })

    return render(request, 'reports/filter.html', context)


@login_required
@role_required(['admin', 'manager'])
def export_filter_to_csv(request):
    """Экспорт отфильтрованных данных в CSV"""
    if 'last_filter_df' in request.session:
        df_json = request.session.get('last_filter_df')
        filter_name = request.session.get('last_filter_name', 'filter')

        # Восстанавливаем DataFrame
        df = pd.read_json(df_json)

        # Создаем HTTP ответ с CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filter_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        # ИСПРАВЛЕНИЕ: добавляем sep=';' для разделителя точкой с запятой
        df.to_csv(path_or_buf=response, index=False, encoding='utf-8-sig', sep=';')
        return response

    messages.error(request, 'Нет данных для экспорта')
    return redirect('reports_filter')


@login_required
@role_required(['admin', 'manager'])
def reports_statistics(request):
    """Статистика из реальной базы данных"""
    stats = ReportGenerator.get_real_data_stats()

    # Генерируем тестовые данные для графиков
    chart_data = {
        'revenue': {
            'labels': ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
            'data': [random.randint(100000, 500000) for _ in range(12)]
        }
    }

    context = {
        'stats': stats,
        'chart_data': json.dumps(chart_data),
        'title': 'Статистика системы',
    }
    return render(request, 'reports/statistics.html', context)


@login_required
@role_required(['admin', 'manager'])
def reports_comparison(request):
    """Сравнение реальных и тестовых данных"""
    real_stats = ReportGenerator.get_real_data_stats()

    # Генерируем тестовые данные
    test_users = ReportGenerator.generate_test_users(1000)
    test_users_df = pd.DataFrame(test_users)

    test_stats = {
        'avg_age': round(test_users_df['age'].mean(), 1),
        'avg_wallet': round(test_users_df['wallet'].mean(), 2),
        'subscribed_percent': round((test_users_df['is_subscribed'].sum() / len(test_users_df) * 100), 1),
        'total_count': len(test_users_df),
    }

    context = {
        'real_stats': real_stats,
        'test_stats': test_stats,
        'title': 'Сравнение данных',
    }
    return render(request, 'reports/comparison.html', context)