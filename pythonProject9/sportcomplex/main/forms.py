from django import forms
from .models import Users, Clients, Trainers, Services, Subscriptions, Bookings
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, date


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Введите email'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label='Телефон',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 999-99-99'})
    )
    birth_date = forms.DateField(
        required=False,
        label='Дата рождения',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Users
        fields = ['userName', 'email', 'phone', 'birth_date', 'password1', 'password2']
        widgets = {
            'userName': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите имя пользователя'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Users.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует')
        return email


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = Users
        fields = ['userName', 'email', 'phone', 'birth_date']
        widgets = {
            'userName': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Clients
        fields = ['first_name', 'last_name', 'phone', 'email', 'birth_date']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class TrainerForm(forms.ModelForm):
    class Meta:
        model = Trainers
        fields = ['full_name', 'specialization', 'experience_years', 'phone', 'is_active']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Services
        fields = ['service_name', 'description', 'price', 'duration', 'is_active']
        widgets = {
            'service_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'min': '30', 'max': '180'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubscriptionForm(forms.ModelForm):
    class Meta:
        model = Subscriptions
        fields = ['client', 'service', 'start_date', 'end_date', 'price_paid', 'status']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'service': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'price_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class BookingForm(forms.ModelForm):
    """Форма для записи на занятие"""

    class Meta:
        model = Bookings
        fields = ['service', 'trainer', 'booking_date', 'start_time', 'end_time', 'room', 'notes']
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client', None)
        super().__init__(*args, **kwargs)

        # Фильтруем только активные услуги и тренеров
        self.fields['service'].queryset = Services.objects.filter(is_active=True)
        self.fields['trainer'].queryset = Trainers.objects.filter(is_active=True)

        # Настраиваем обязательные поля
        self.fields['service'].required = True
        self.fields['booking_date'].required = True
        self.fields['start_time'].required = True
        self.fields['end_time'].required = True
        self.fields['room'].required = True

        # Если есть активные абонементы, сортируем услуги
        if self.client:
            active_subscriptions = Subscriptions.objects.filter(
                client=self.client,
                status='active'
            )
            if active_subscriptions.exists():
                # Получаем ID услуг из активных абонементов
                active_services_ids = list(active_subscriptions.values_list('service', flat=True))

                # Сортируем queryset: сначала услуги из активных абонементов
                # Используем аннотацию для сортировки
                from django.db.models import Case, When, IntegerField

                # Создаем условие для сортировки
                preserved = Case(
                    *[When(pk=pk, then=pos) for pos, pk in enumerate(active_services_ids)],
                    default=len(active_services_ids),
                    output_field=IntegerField()
                )

                # Сортируем queryset
                self.fields['service'].queryset = Services.objects.filter(
                    is_active=True
                ).order_by(preserved, 'service_name')

    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        service = cleaned_data.get('service')
        room = cleaned_data.get('room')

        if not booking_date:
            self.add_error('booking_date', 'Дата занятия обязательна')
        if not start_time:
            self.add_error('start_time', 'Время начала обязательно')
        if not end_time:
            self.add_error('end_time', 'Время окончания обязательно')
        if not service:
            self.add_error('service', 'Услуга обязательна')
        if not room:
            self.add_error('room', 'Зал обязателен')

        if booking_date and start_time and end_time:
            if booking_date < date.today():
                self.add_error('booking_date', 'Нельзя записываться на прошедшие даты')

            start_datetime = datetime.combine(booking_date, start_time)
            end_datetime = datetime.combine(booking_date, end_time)
            if end_datetime <= start_datetime:
                self.add_error('end_time', 'Время окончания должно быть позже времени начала')

            duration = (end_datetime - start_datetime).total_seconds() / 60
            if duration < 30:
                self.add_error('end_time', 'Минимальная длительность занятия - 30 минут')
            if duration > 180:
                self.add_error('end_time', 'Максимальная длительность занятия - 3 часа')

            start_hour = start_time.hour
            if start_hour < 7 or start_hour > 22:
                self.add_error('start_time', 'Время работы: с 7:00 до 22:00')

            end_hour = end_time.hour
            if end_hour > 23 or (end_hour == 23 and end_time.minute > 0):
                self.add_error('end_time', 'Последнее занятие должно заканчиваться до 23:00')

            if booking_date and start_time and end_time and room:
                conflicting_bookings = Bookings.objects.filter(
                    booking_date=booking_date,
                    room=room,
                    status='scheduled'
                ).exclude(pk=self.instance.pk if self.instance else None)

                for booking in conflicting_bookings:
                    if (start_time < booking.end_time and end_time > booking.start_time):
                        self.add_error('start_time',
                                       f'Это время уже занято в {room} ({booking.start_time.strftime("%H:%M")}-{booking.end_time.strftime("%H:%M")})')
                        break

        return cleaned_data


# Создадим константы для залов если их нет в модели
ROOM_CHOICES = [
    ('hall1', 'Зал 1: Силовые тренировки'),
    ('hall2', 'Зал 2: Кардио тренировки'),
    ('hall3', 'Зал 3: Игровые развлечения'),
    ('pool', 'Бассейн: Аквааэробика'),
]


class QuickBookingForm(forms.Form):
    """Форма для быстрой записи на занятие"""
    service = forms.ModelChoiceField(
        queryset=Services.objects.filter(is_active=True),
        label='Услуга *',
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Выберите услугу"
    )
    booking_date = forms.DateField(
        label='Дата занятия *',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%Y-%m-%d', '%d.%m.%Y']
    )
    time_slot = forms.ChoiceField(
        label='Время занятия *',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False  # Сделаем необязательным при инициализации
    )
    trainer = forms.ModelChoiceField(
        queryset=Trainers.objects.filter(is_active=True),
        label='Тренер',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Любой тренер"
    )
    room = forms.ChoiceField(
        label='Зал *',
        choices=ROOM_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='hall1'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Устанавливаем доступные временные слоты
        time_slots = self.get_time_slots()
        self.fields['time_slot'].choices = [('', 'Выберите время')] + time_slots

        # Если передан service_id, устанавливаем его
        if 'initial' in kwargs and 'service' in kwargs['initial']:
            self.fields['service'].initial = kwargs['initial']['service']

    def clean_time_slot(self):
        """Кастомная валидация для time_slot"""
        time_slot = self.cleaned_data.get('time_slot')
        if not time_slot:
            raise forms.ValidationError('Время занятия обязательно для выбора')
        return time_slot

    def get_time_slots(self):
        """Генерирует список временных слотов"""
        time_slots = []
        start_hour = 7  # Начало рабочего дня
        end_hour = 22  # Конец рабочего дня
        duration = 90  # Длительность занятия в минутах

        for hour in range(start_hour, end_hour):
            for minute in [0, 30]:
                if hour == end_hour - 1 and minute == 30:
                    continue

                start_time = f"{hour:02d}:{minute:02d}"
                end_hour_calc = hour + (duration // 60)
                end_minute = minute + (duration % 60)
                if end_minute >= 60:
                    end_hour_calc += 1
                    end_minute -= 60

                if end_hour_calc > end_hour or (end_hour_calc == end_hour and end_minute > 0):
                    continue

                end_time = f"{end_hour_calc:02d}:{end_minute:02d}"
                time_slots.append((f"{start_time}-{end_time}", f"{start_time} - {end_time}"))

        return time_slots

    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        time_slot = cleaned_data.get('time_slot')
        service = cleaned_data.get('service')
        room = cleaned_data.get('room')

        if not booking_date:
            self.add_error('booking_date', 'Дата занятия обязательна')
        if not time_slot:
            self.add_error('time_slot', 'Время занятия обязательно')
        if not service:
            self.add_error('service', 'Услуга обязательна')
        if not room:
            self.add_error('room', 'Зал обязателен')

        if booking_date and time_slot:
            if booking_date < date.today():
                self.add_error('booking_date', 'Нельзя записываться на прошедшие даты')

            try:
                start_time_str, end_time_str = time_slot.split('-')
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()

                if room:
                    conflicting_bookings = Bookings.objects.filter(
                        booking_date=booking_date,
                        room=room,
                        status='scheduled'
                    )

                    for booking in conflicting_bookings:
                        if (start_time < booking.end_time and end_time > booking.start_time):
                            self.add_error('time_slot',
                                           f'Это время уже занято в {room} ({booking.start_time.strftime("%H:%M")}-{booking.end_time.strftime("%H:%M")})')
                            break
            except ValueError:
                self.add_error('time_slot', 'Неверный формат времени')

        return cleaned_data

    def save(self, client):
        """Сохраняет запись на занятие"""
        booking_date = self.cleaned_data['booking_date']
        time_slot = self.cleaned_data['time_slot']
        service = self.cleaned_data['service']
        trainer = self.cleaned_data.get('trainer')
        room = self.cleaned_data['room']

        start_time_str, end_time_str = time_slot.split('-')
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        booking = Bookings.objects.create(
            client=client,
            service=service,
            trainer=trainer,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            room=room,
            status='scheduled'
        )

        return booking