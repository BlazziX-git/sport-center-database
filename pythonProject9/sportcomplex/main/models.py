from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import hashlib


# ============== МЕНЕДЖЕР ПОЛЬЗОВАТЕЛЕЙ ==============
class CustomUserManager(BaseUserManager):
    def create_user(self, userName, email=None, password=None, **extra_fields):
        if not userName:
            raise ValueError('Требуется имя пользователя')

        user = self.model(
            userName=userName,
            email=email,
            **extra_fields
        )

        if password:
            user.userPass = password
            user.passHash = hashlib.sha256(password.encode()).hexdigest()

        user.save(using=self._db)
        return user

    def create_superuser(self, userName, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')

        return self.create_user(userName, email, password, **extra_fields)


# ============== ТАБЛИЦА Clients (нужно объявить ДО Users) ==============
class Clients(models.Model):
    client_id = models.AutoField(primary_key=True, verbose_name='ID клиента')
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, verbose_name='Фамилия')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name='Email')
    birth_date = models.DateField(blank=True, null=True, verbose_name='Дата рождения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')

    class Meta:
        db_table = 'Clients'
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        """Вычисляем возраст"""
        if self.birth_date:
            from datetime import date
            today = date.today()
            return today.year - self.birth_date.year - (
                    (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None


# ============== ТАБЛИЦА Users ==============
class Users(AbstractUser):
    # Убираем стандартные поля Django, чтобы не конфликтовали
    username = None
    first_name = None
    last_name = None
    last_login = None
    date_joined = None

    # Поля из твоей существующей таблицы Users
    id = models.AutoField(primary_key=True, verbose_name='ID')
    userName = models.CharField(max_length=100, unique=True, verbose_name='Логин')
    userPass = models.CharField(max_length=100, verbose_name='Пароль (открытый)')
    passHash = models.CharField(max_length=64, verbose_name='Хэш пароля')

    # Доп поля для аутентификации Django (добавляем к существующим)
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_staff = models.BooleanField(default=False, verbose_name='Персонал')
    is_superuser = models.BooleanField(default=False, verbose_name='Суперпользователь')

    # Поля для ролей
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('manager', 'Менеджер'),
        ('trainer', 'Тренер'),
        ('client', 'Клиент'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='client',
        verbose_name='Роль'
    )

    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Телефон')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')

    # ВАЖНО: Связь с таблицей Clients (новое поле)
    client_profile = models.OneToOneField(
        Clients,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_account',
        verbose_name='Профиль клиента'
    )

    # Настройки для Django auth
    USERNAME_FIELD = 'userName'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Meta:
        db_table = 'Users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.userName} ({self.role})"

    def save(self, *args, **kwargs):
        # Автоматически считаем хэш если пароль изменился
        if self.userPass and not self.passHash:
            self.passHash = hashlib.sha256(self.userPass.encode()).hexdigest()

        # Автоматически определяем is_staff по роли
        if self.role in ['admin', 'manager']:
            self.is_staff = True
        else:
            self.is_staff = False

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        """Проверка пароля (через хэш SHA-256)"""
        return self.passHash == hashlib.sha256(raw_password.encode()).hexdigest()

    def has_perm(self, perm, obj=None):
        """Права доступа"""
        return self.is_superuser

    def has_module_perms(self, app_label):
        """Права на модуль"""
        return self.is_superuser or self.is_staff

    @property
    def full_name(self):
        """Полное имя пользователя"""
        if self.role == 'client' and self.client_profile:
            return self.client_profile.full_name
        return self.userName

    @property
    def is_client_user(self):
        """Проверяет, является ли пользователь клиентом с привязанным профилем"""
        return self.role == 'client' and self.client_profile is not None

    def get_client_subscriptions(self):
        """Получает абонементы клиента"""
        if self.is_client_user:
            from .models import Subscriptions
            return Subscriptions.objects.filter(client=self.client_profile)
        return Subscriptions.objects.none()


# ============== ТАБЛИЦА Trainers ==============
class Trainers(models.Model):
    trainer_id = models.AutoField(primary_key=True, verbose_name='ID тренера')
    full_name = models.CharField(max_length=150, verbose_name='ФИО')
    specialization = models.CharField(max_length=100, verbose_name='Специализация')
    experience_years = models.IntegerField(verbose_name='Стаж (лет)')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата найма')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        db_table = 'Trainers'
        verbose_name = 'Тренер'
        verbose_name_plural = 'Тренеры'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name}"


# ============== ТАБЛИЦА Services ==============
class Services(models.Model):
    service_id = models.AutoField(primary_key=True, verbose_name='ID услуги')
    service_name = models.CharField(max_length=100, verbose_name='Название услуги')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    duration = models.IntegerField(verbose_name='Длительность (минут)')
    description = models.TextField(blank=True, verbose_name='Описание')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        db_table = 'Services'
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['service_name']

    def __str__(self):
        return f"{self.service_name} - {self.price} руб."


# ============== ТАБЛИЦА Subscriptions ==============
class Subscriptions(models.Model):
    subscription_id = models.AutoField(primary_key=True, verbose_name='ID абонемента')
    client = models.ForeignKey(
        Clients,
        on_delete=models.CASCADE,
        db_column='client_id',
        verbose_name='Клиент'
    )
    service = models.ForeignKey(
        Services,
        on_delete=models.CASCADE,
        db_column='service_id',
        verbose_name='Услуга'
    )
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')
    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Оплаченная сумма'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    # Дополнительные поля для удобства
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('expired', 'Истёк'),
        ('cancelled', 'Отменён'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус'
    )

    class Meta:
        db_table = 'Subscriptions'
        verbose_name = 'Абонемент'
        verbose_name_plural = 'Абонементы'
        ordering = ['-created_at']

    def __str__(self):
        return f"Абонемент #{self.subscription_id} - {self.client.full_name}"

    @property
    def is_active(self):
        """Проверяем, активен ли абонемент"""
        from datetime import date
        today = date.today()
        return self.start_date <= today <= self.end_date and self.status == 'active'

    def save(self, *args, **kwargs):
        """Автоматически обновляем статус при сохранении"""
        from datetime import date
        today = date.today()

        if self.status != 'cancelled':
            if self.end_date < today:
                self.status = 'expired'
            else:
                self.status = 'active'

        super().save(*args, **kwargs)


# ============== ТАБЛИЦА Bookings (Записи на занятия) ==============
class Bookings(models.Model):
    # Константы для выбора зала
    ROOM_CHOICES = [
        ('hall1', 'Зал 1: Силовые тренировки'),
        ('hall2', 'Зал 2: Кардио тренировки'),
        ('hall3', 'Зал 3: Игровые развлечения'),
        ('pool', 'Бассейн: Аквааэробика'),
    ]

    # Константы для статуса
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
        ('no_show', 'Не явился'),
    ]

    booking_id = models.AutoField(primary_key=True, verbose_name='ID записи')
    client = models.ForeignKey(
        Clients,
        on_delete=models.CASCADE,
        db_column='client_id',
        verbose_name='Клиент'
    )
    service = models.ForeignKey(
        Services,
        on_delete=models.CASCADE,
        db_column='service_id',
        verbose_name='Услуга'
    )
    trainer = models.ForeignKey(
        Trainers,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='trainer_id',
        verbose_name='Тренер'
    )
    booking_date = models.DateField(verbose_name='Дата занятия')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')

    # Дополнительные поля
    room = models.CharField(
        max_length=50,
        choices=ROOM_CHOICES,
        default='hall1',
        verbose_name='Зал'
    )
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    # Статус записи
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name='Статус'
    )

    class Meta:
        db_table = 'Bookings'
        verbose_name = 'Запись на занятие'
        verbose_name_plural = 'Записи на занятия'
        ordering = ['booking_date', 'start_time']

    def __str__(self):
        return f"Запись #{self.booking_id} - {self.client.full_name} - {self.booking_date}"

    @property
    def duration(self):
        """Вычисляем длительность занятия в минутах"""
        from datetime import datetime
        start = datetime.combine(self.booking_date, self.start_time)
        end = datetime.combine(self.booking_date, self.end_time)
        return (end - start).seconds // 60

    @property
    def is_upcoming(self):
        """Проверяем, является ли занятие предстоящим"""
        from datetime import datetime, date
        today = date.today()
        now = datetime.now().time()

        if self.booking_date > today:
            return True
        elif self.booking_date == today and self.start_time > now:
            return True
        return False

    @property
    def can_be_cancelled(self):
        """Можно ли отменить запись (только если она запланирована и еще не началась)"""
        from datetime import datetime, date, timedelta
        today = date.today()
        now = datetime.now().time()

        # Можно отменить только запланированные занятия
        if self.status != 'scheduled':
            return False

        # Нельзя отменить занятия, которые уже начались
        if self.booking_date < today:
            return False
        elif self.booking_date == today and self.start_time <= now:
            return False

        # Можно отменить минимум за 2 часа до начала
        booking_datetime = datetime.combine(self.booking_date, self.start_time)
        current_datetime = datetime.now()

        return (booking_datetime - current_datetime).seconds // 3600 >= 2