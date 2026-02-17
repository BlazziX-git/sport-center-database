# report_generator.py
import random
import pandas as pd
from datetime import datetime, timedelta
from .models import Users, Clients, Trainers, Services, Subscriptions, Bookings
from django.utils import timezone
import io
import base64
from django.db import models


class ReportGenerator:
    """Генератор отчетов и тестовых данных"""

    @staticmethod
    def generate_test_users(count=100):
        """Генерирует тестовых пользователей (аналог UserGenerator)"""
        names = ["Иван", "Анна", "Петр", "Ольга", "Сергей", "Мария", "Дмитрий", "Елена", "Алексей", "Татьяна"]
        domains = ["gmail.com", "yahoo.com", "mail.ru", "yandex.ru", "bk.ru"]

        def random_date(start_year, end_year):
            start = datetime(start_year, 1, 1)
            end = datetime(end_year, 12, 31)
            return start + timedelta(days=random.randint(0, (end - start).days))

        def random_email(name):
            return f"{name.lower()}{random.randint(1, 9999)}@{random.choice(domains)}"

        users = []
        for i in range(1, count + 1):
            name = random.choice(names)
            age = random.randint(16, 80)
            birth_date = datetime.now() - timedelta(days=age * 365)

            user = {
                'id': i,
                'name': name,
                'age': age,
                'wallet': round(random.uniform(0, 200000), 2),
                'email': random_email(name),
                'is_subscribed': random.choice([True, False]),
                'registration_date': random_date(2015, 2024),
                'last_online': datetime.now() - timedelta(days=random.randint(0, 30)),
                'total_spent': round(random.uniform(0, 500000), 2),
                'birth_date': birth_date,
                'city': random.choice(["Москва", "СПб", "Казань", "Новосибирск", "Екатеринбург"]),
                'subscription_type': random.choice(["Базовый", "Стандарт", "Премиум", "VIP"]),
                'visits_count': random.randint(0, 200),
                'trainer_name': random.choice(["Александр", "Екатерина", "Максим", "Юлия", "Денис"])
            }
            users.append(user)

        return users

    @staticmethod
    def generate_test_bookings(count=500):
        """Генерирует тестовые записи на занятия"""
        services = ["Персональная тренировка", "Групповое занятие", "Йога", "Пилатес", "Кроссфит", "Бассейн"]
        trainers = ["Александр", "Екатерина", "Максим", "Юлия", "Денис", "Анна"]
        rooms = ["Зал 1", "Зал 2", "Зал 3", "Бассейн"]
        statuses = ["scheduled", "completed", "cancelled", "no_show"]

        bookings = []
        today = datetime.now()

        for i in range(1, count + 1):
            booking_date = today - timedelta(days=random.randint(-30, 30))
            start_hour = random.randint(8, 20)
            start_time = datetime(booking_date.year, booking_date.month, booking_date.day, start_hour, 0)
            end_time = start_time + timedelta(minutes=random.choice([60, 90, 120]))

            booking = {
                'id': i,
                'client_name': random.choice(["Иван", "Анна", "Петр", "Ольга", "Сергей", "Мария"]),
                'service': random.choice(services),
                'trainer': random.choice(trainers),
                'booking_date': booking_date,
                'start_time': start_time,
                'end_time': end_time,
                'room': random.choice(rooms),
                'status': random.choice(statuses),
                'price': round(random.uniform(1000, 5000), 2),
                'duration': (end_time - start_time).seconds // 60
            }
            bookings.append(booking)

        return bookings

    @staticmethod
    def generate_subscriptions_data(count=300):
        """Генерирует тестовые абонементы"""
        clients = ["Иван", "Анна", "Петр", "Ольга", "Сергей", "Мария"]
        services = ["Персональная тренировка", "Групповое занятие", "Йога", "Пилатес", "Кроссфит", "Бассейн"]

        subscriptions = []
        today = datetime.now()

        for i in range(1, count + 1):
            start_date = today - timedelta(days=random.randint(0, 365))
            months = random.choice([1, 3, 6, 12])
            end_date = start_date + timedelta(days=30 * months)

            sub = {
                'id': i,
                'client': random.choice(clients),
                'service': random.choice(services),
                'start_date': start_date,
                'end_date': end_date,
                'price_paid': round(random.uniform(3000, 50000), 2),
                'status': random.choice(['active', 'expired', 'cancelled']),
                'months': months,
                'visits_left': random.randint(0, 50)
            }
            subscriptions.append(sub)

        return subscriptions

    @staticmethod
    def create_report_dataframe(data_type='users', count=1000):
        """Создает DataFrame с данными"""
        if data_type == 'users':
            data = ReportGenerator.generate_test_users(count)
        elif data_type == 'bookings':
            data = ReportGenerator.generate_test_bookings(count)
        elif data_type == 'subscriptions':
            data = ReportGenerator.generate_subscriptions_data(count)
        else:
            data = []

        return pd.DataFrame(data)

    @staticmethod
    def apply_filters(df, filters):
        """Применяет фильтры к DataFrame (аналог LINQ-запросов)"""
        result_df = df.copy()

        for field, condition in filters.items():
            if field in df.columns:
                try:
                    if isinstance(condition, dict):
                        if 'gt' in condition:
                            result_df = result_df[result_df[field] > condition['gt']]
                        if 'lt' in condition:
                            result_df = result_df[result_df[field] < condition['lt']]
                        if 'gte' in condition:
                            result_df = result_df[result_df[field] >= condition['gte']]
                        if 'lte' in condition:
                            result_df = result_df[result_df[field] <= condition['lte']]
                        if 'eq' in condition:
                            result_df = result_df[result_df[field] == condition['eq']]
                        if 'contains' in condition:
                            result_df = result_df[result_df[field].str.contains(condition['contains'], na=False)]
                        if 'between' in condition:
                            result_df = result_df[
                                result_df[field].between(condition['between'][0], condition['between'][1])]
                    else:
                        result_df = result_df[result_df[field] == condition]
                except:
                    pass

        return result_df

    @staticmethod
    def get_real_data_stats():
        """Получает реальную статистику из базы данных"""
        stats = {}

        # Статистика по услугам
        services = Services.objects.all()
        active_services = Services.objects.filter(is_active=True)
        stats['services'] = {
            'total': services.count(),
            'active': active_services.count(),
            'avg_price': active_services.aggregate(avg=models.Avg('price'))['avg'] or 0,
            'avg_duration': active_services.aggregate(avg=models.Avg('duration'))['avg'] or 0,
        }

        # Статистика по тренерам
        trainers = Trainers.objects.all()
        active_trainers = Trainers.objects.filter(is_active=True)
        stats['trainers'] = {
            'total': trainers.count(),
            'active': active_trainers.count(),
            'avg_experience': active_trainers.aggregate(avg=models.Avg('experience_years'))['avg'] or 0,
        }

        # Статистика по клиентам
        clients = Clients.objects.all()
        clients_with_birthdate = clients.exclude(birth_date__isnull=True)
        stats['clients'] = {
            'total': clients.count(),
            'with_email': clients.exclude(email='').exclude(email__isnull=True).count(),
            'with_birthdate': clients_with_birthdate.count(),
        }

        # Статистика по абонементам
        subscriptions = Subscriptions.objects.all()
        stats['subscriptions'] = {
            'total': subscriptions.count(),
            'active': subscriptions.filter(status='active').count(),
            'expired': subscriptions.filter(status='expired').count(),
            'cancelled': subscriptions.filter(status='cancelled').count(),
            'total_revenue': subscriptions.aggregate(total=models.Sum('price_paid'))['total'] or 0,
        }

        # Статистика по записям
        bookings = Bookings.objects.all()
        today = datetime.now().date()
        stats['bookings'] = {
            'total': bookings.count(),
            'today': bookings.filter(booking_date=today).count(),
            'scheduled': bookings.filter(status='scheduled').count(),
            'completed': bookings.filter(status='completed').count(),
            'cancelled': bookings.filter(status='cancelled').count(),
            'no_show': bookings.filter(status='no_show').count(),
        }

        return stats

    @staticmethod
    def dataframe_to_html(df, max_rows=100):
        """Преобразует DataFrame в HTML таблицу"""
        if df.empty:
            return "<p class='text-muted'>Нет данных для отображения</p>"

        # Ограничиваем количество строк
        display_df = df.head(max_rows)

        # Форматируем числа
        for col in display_df.select_dtypes(include=['float64']).columns:
            display_df[col] = display_df[col].map(lambda x: f"{x:.2f}")

        # Генерируем HTML
        return display_df.to_html(
            classes='table table-striped table-hover table-bordered',
            escape=False,
            index=False
        )