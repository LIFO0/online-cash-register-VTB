import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from banking.models import Account, ClientProfile, Transaction
from banking.utils import normalize_text, biased_random_amount
from django.utils.crypto import get_random_string

RUSSIAN_MALE_FIRST_NAMES = [
    'Александр',
    'Алексей',
    'Андрей',
    'Антон',
    'Артем',
    'Борис',
    'Вадим',
    'Василий',
    'Виктор',
    'Владимир',
    'Дмитрий',
    'Евгений',
    'Иван',
    'Игорь',
    'Константин',
    'Максим',
    'Михаил',
    'Николай',
    'Олег',
    'Павел',
    'Роман',
    'Сергей',
    'Юрий',
    'Ярослав',
]

RUSSIAN_FEMALE_FIRST_NAMES = [
    'Анна',
    'Елена',
    'Ирина',
    'Мария',
    'Наталья',
    'Ольга',
    'Светлана',
    'Татьяна',
    'Екатерина',
    'Юлия',
    'Анастасия',
    'Дарья',
    'Виктория',
    'Александра',
    'Валентина',
    'Галина',
    'Людмила',
    'Лариса',
    'Марина',
    'Надежда',
    'Тамара',
    'Валерия',
    'Полина',
]

RUSSIAN_MALE_LAST_NAMES = [
    'Иванов',
    'Петров',
    'Смирнов',
    'Кузнецов',
    'Попов',
    'Соколов',
    'Лебедев',
    'Козлов',
    'Новиков',
    'Морозов',
    'Петухов',
    'Волков',
    'Соловьев',
    'Васильев',
    'Зайцев',
    'Павлов',
    'Семенов',
    'Голубев',
    'Виноградов',
    'Богданов',
    'Воробьев',
    'Федоров',
    'Михайлов',
    'Белов',
    'Тарасов',
    'Беляев',
    'Комаров',
    'Орлов',
    'Киселев',
    'Макаров',
    'Андреев',
    'Ковалев',
    'Ильин',
    'Гусев',
    'Титов',
    'Кузьмин',
    'Кудрявцев',
    'Баранов',
    'Куликов',
    'Алексеев',
    'Степанов',
    'Яковлев',
    'Сорокин',
    'Сергеев',
    'Романов',
    'Захаров',
    'Борисов',
    'Королев',
    'Герасимов',
    'Пономарев',
    'Григорьев',
    'Лазарев',
    'Медведев',
    'Ершов',
    'Никитин',
    'Соболев',
    'Рябов',
    'Поляков',
    'Цветков',
    'Данилов',
    'Жуков',
    'Фролов',
]

RUSSIAN_FEMALE_LAST_NAMES = [
    'Иванова',
    'Петрова',
    'Смирнова',
    'Кузнецова',
    'Попова',
    'Соколова',
    'Лебедева',
    'Козлова',
    'Новикова',
    'Морозова',
    'Петухова',
    'Волкова',
    'Соловьева',
    'Васильева',
    'Зайцева',
    'Павлова',
    'Семенова',
    'Голубева',
    'Виноградова',
    'Богданова',
    'Воробьева',
    'Федорова',
    'Михайлова',
    'Белова',
    'Тарасова',
    'Беляева',
    'Комарова',
    'Орлова',
    'Киселева',
    'Макарова',
    'Андреева',
    'Ковалева',
    'Ильина',
    'Гусева',
    'Титова',
    'Кузьмина',
    'Кудрявцева',
    'Баранова',
    'Куликова',
    'Алексеева',
    'Степанова',
    'Яковлева',
    'Сорокина',
    'Сергеева',
    'Романова',
    'Захарова',
    'Борисова',
    'Королева',
    'Герасимова',
    'Пономарева',
    'Григорьева',
    'Лазарева',
    'Медведева',
    'Ершова',
    'Никитина',
    'Соболева',
    'Рябова',
    'Полякова',
    'Цветкова',
    'Данилова',
    'Жукова',
    'Фролова',
]

RUSSIAN_JOB_TITLES = [
    'Инженер',
    'Менеджер',
    'Бухгалтер',
    'Врач',
    'Учитель',
    'Программист',
    'Дизайнер',
    'Юрист',
    'Экономист',
    'Маркетолог',
    'Продавец',
    'Повар',
    'Водитель',
    'Строитель',
    'Архитектор',
    'Журналист',
    'Переводчик',
    'Фармацевт',
    'Психолог',
    'Социальный работник',
    'Ведущий инженер',
    'Старший менеджер',
    'Главный бухгалтер',
    'Врач-терапевт',
    'Учитель математики',
    'Ведущий программист',
    'Графический дизайнер',
    'Юрист-консультант',
    'Финансовый аналитик',
    'Менеджер по продажам',
    'Шеф-повар',
    'Инженер-конструктор',
]

TRANSACTION_NOTES = {
    Transaction.TransactionType.DEPOSIT: [
        'Зарплатное поступление',
        'Бонус по проекту',
        'Возврат средств',
        'Пополнение с карты',
        'Перевод от друга',
        'Премия',
        'Дивиденды',
        'Возврат налога',
        'Подарок',
        'Компенсация',
    ],
    Transaction.TransactionType.WITHDRAWAL: [
        'Снятие наличных в банкомате',
        'Оплата покупок',
        'Оплата услуг',
        'Перевод на карту',
        'Оплата коммунальных услуг',
        'Покупка продуктов',
        'Оплата интернета',
        'Оплата мобильной связи',
        'Покупка билетов',
        'Оплата ресторана',
    ],
    Transaction.TransactionType.TRANSFER_OUT: [
        'Перевод другу',
        'Перевод родственнику',
        'Оплата займа',
        'Перевод на другой счет',
        'Оплата услуг',
        'Перевод за товар',
    ],
    Transaction.TransactionType.TRANSFER_IN: [
        'Перевод от друга',
        'Перевод от родственника',
        'Возврат займа',
        'Перевод с другого счета',
        'Оплата за услуги',
        'Перевод за товар',
    ],
}


class Command(BaseCommand):
    help = (
        'Генерирует 50 учетных записей с русскими именами '
        'и историей транзакций'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Количество учетных записей для генерации (по умолчанию: 50)',
        )

    def handle(self, *args, **options):
        count = options['count']
        User = get_user_model()

        self.stdout.write(f'Начинаю генерацию {count} учетных записей...')

        existing_account_numbers = set(
            Account.objects.values_list('account_number', flat=True)
        )

        created_count = 0
        for i in range(count):
            is_male = random.choice([True, False])
            if is_male:
                first_name = random.choice(RUSSIAN_MALE_FIRST_NAMES)
                last_name = random.choice(RUSSIAN_MALE_LAST_NAMES)
            else:
                first_name = random.choice(RUSSIAN_FEMALE_FIRST_NAMES)
                last_name = random.choice(RUSSIAN_FEMALE_LAST_NAMES)

            full_name = f'{first_name} {last_name}'
            job_title = random.choice(RUSSIAN_JOB_TITLES)

            username = f'client_{i + 1:03d}'
            while User.objects.filter(username=username).exists():
                username = f'client_{i + 1:03d}_{random.randint(1000, 9999)}'

            account_number = f'4081781000000000{i + 1:04d}'
            while account_number in existing_account_numbers:
                account_number = (
                    f'4081781000000{random.randint(100000, 999999)}'
                )
            existing_account_numbers.add(account_number)

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@vtb.test',
                    'first_name': first_name,
                    'last_name': last_name,
                },
            )
            if not created:
                self.stdout.write(
                    self.style.WARNING(
                        f'Пользователь {username} уже существует, '
                        f'пропускаю...'
                    )
                )
                continue

            user.set_password('Client@1234')
            user.is_staff = False
            user.is_superuser = False
            user.save()

            account_blocked = random.random() < 0.01

            # Создаем профиль клиента
            profile, _ = ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': full_name,
                    'job_title': job_title,
                    'is_blocked': account_blocked,
                },
            )
            profile.full_name = full_name
            profile.job_title = job_title
            if profile.is_blocked != account_blocked:
                profile.is_blocked = account_blocked
            profile.save()

            account, _ = Account.objects.get_or_create(
                account_number=account_number,
                defaults={
                    'client': profile,
                    'balance': Decimal('0.00'),
                    'is_blocked': account_blocked,
                },
            )
            if account.client_id != profile.id:
                account.client = profile
                account.save(update_fields=['client'])
            if account.is_blocked != account_blocked:
                account.is_blocked = account_blocked
                account.save(update_fields=['is_blocked'])

            self._generate_transaction_history(account, profile, i)

            created_count += 1
            if (i + 1) % 10 == 0:
                self.stdout.write(
                    f'Создано {i + 1}/{count} учетных записей...'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано {created_count} учетных записей '
                f'с историей транзакций.'
            )
        )

    def _generate_transaction_history(
        self, account: Account, profile: ClientProfile, seed: int
    ) -> None:
        Transaction.objects.filter(account=account).delete()
        account.balance = Decimal('0.00')

        now = timezone.now()
        months_back = random.randint(6, 12)
        start_date = now - timedelta(days=months_back * 30)
        if start_date >= now:
            start_date = now - timedelta(days=1)

        num_transactions = random.randint(10, 30)

        all_accounts = list(Account.objects.exclude(id=account.id))
        if not all_accounts:
            transfer_probability = 0
        else:
            transfer_probability = 0.2  # 20% вероятность перевода

        # Лимиты: минимум 10 ₽, максимум 100000 ₽
        MIN_AMOUNT = Decimal('10')
        MAX_AMOUNT = Decimal('100000')

        transactions = []
        transfer_pairs = []
        balance = Decimal('0.00')

        transaction_dates = []
        total_days = (now - start_date).days
        if total_days < 1:
            total_days = 1

        for i in range(num_transactions):
            days_offset = random.randint(0, total_days - 1)
            hours = random.randint(0, 23)
            minutes = random.randint(0, 59)
            seconds = random.randint(0, 59)
            created_at = start_date + timedelta(
                days=days_offset,
                hours=hours,
                minutes=minutes,
                seconds=seconds
            )
            if created_at >= now:
                created_at = now - timedelta(
                    seconds=random.randint(1, 3600)
                )
            transaction_dates.append(created_at)

        transaction_dates.sort()

        for i in range(num_transactions):
            created_at = transaction_dates[i]

            rand = random.random()
            if (
                rand < transfer_probability
                and all_accounts
                and balance >= MIN_AMOUNT
            ):
                target_account = random.choice(all_accounts)
                max_transfer = min(MAX_AMOUNT, balance)
                if max_transfer >= MIN_AMOUNT:
                    amount = biased_random_amount(MIN_AMOUNT, max_transfer)
                else:
                    amount = None

                if amount and balance >= amount:
                    base_reference = self._generate_reference(created_at)
                    outgoing_reference = base_reference
                    incoming_reference = base_reference.replace(
                        'TRX-', 'TRX-IN-'
                    )

                    outgoing = Transaction(
                        account=account,
                        transaction_type=(
                            Transaction.TransactionType.TRANSFER_OUT
                        ),
                        amount=amount,
                        status=Transaction.Status.COMPLETED,
                        reference=outgoing_reference,
                        note=normalize_text(
                            random.choice(
                                TRANSACTION_NOTES[
                                    Transaction.TransactionType.TRANSFER_OUT
                                ]
                            )
                        ),
                        performed_by=profile,
                        created_at=created_at,
                        processed_at=created_at
                        + timedelta(minutes=random.randint(1, 10)),
                        metadata={
                            'counterparty_account_number': (
                                target_account.account_number
                            )
                        },
                    )

                    incoming = Transaction(
                        account=target_account,
                        transaction_type=(
                            Transaction.TransactionType.TRANSFER_IN
                        ),
                        amount=amount,
                        status=Transaction.Status.COMPLETED,
                        reference=incoming_reference,
                        note=normalize_text(
                            random.choice(
                                TRANSACTION_NOTES[
                                    Transaction.TransactionType.TRANSFER_IN
                                ]
                            )
                        ),
                        performed_by=target_account.client,
                        created_at=created_at,
                        processed_at=created_at
                        + timedelta(minutes=random.randint(1, 10)),
                        metadata={
                            'counterparty_account_number': (
                                account.account_number
                            )
                        },
                    )

                    transfer_pairs.append((outgoing, incoming, target_account))
                    balance -= amount
            elif balance < Decimal('10000') or random.random() < 0.6:
                amount = biased_random_amount(MIN_AMOUNT, MAX_AMOUNT)
                reference = self._generate_reference(created_at)
                transaction = Transaction(
                    account=account,
                    transaction_type=Transaction.TransactionType.DEPOSIT,
                    amount=amount,
                    status=Transaction.Status.COMPLETED,
                    reference=reference,
                    note=normalize_text(
                        random.choice(
                            TRANSACTION_NOTES[
                                Transaction.TransactionType.DEPOSIT
                            ]
                        )
                    ),
                    performed_by=profile,
                    created_at=created_at,
                    processed_at=created_at
                    + timedelta(minutes=random.randint(1, 10)),
                )
                transactions.append(transaction)
                balance += amount
            else:
                max_withdrawal = min(balance, MAX_AMOUNT)
                if max_withdrawal >= MIN_AMOUNT:
                    amount = biased_random_amount(MIN_AMOUNT, max_withdrawal)
                    reference = self._generate_reference(created_at)
                    transaction = Transaction(
                        account=account,
                        transaction_type=(
                            Transaction.TransactionType.WITHDRAWAL
                        ),
                        amount=amount,
                        status=Transaction.Status.COMPLETED,
                        reference=reference,
                        note=normalize_text(
                            random.choice(
                                TRANSACTION_NOTES[
                                    Transaction.TransactionType.WITHDRAWAL
                                ]
                            )
                        ),
                        performed_by=profile,
                        created_at=created_at,
                        processed_at=created_at
                        + timedelta(minutes=random.randint(1, 10)),
                    )
                    transactions.append(transaction)
                    balance -= amount

        saved_transactions = Transaction.objects.bulk_create(transactions)

        for saved, original in zip(saved_transactions, transactions):
            Transaction.objects.filter(pk=saved.pk).update(
                created_at=original.created_at,
                processed_at=original.processed_at
            )

        for outgoing, incoming, target_account in transfer_pairs:
            outgoing.save()
            incoming.save()
            Transaction.objects.filter(pk=outgoing.pk).update(
                created_at=outgoing.created_at,
                processed_at=outgoing.processed_at
            )
            Transaction.objects.filter(pk=incoming.pk).update(
                created_at=incoming.created_at,
                processed_at=incoming.processed_at
            )
            outgoing.related_transaction = incoming
            incoming.related_transaction = outgoing
            outgoing.save()
            incoming.save()

            target_account.balance += incoming.amount
            target_account.save(update_fields=['balance'])

        account.balance = balance

        all_transaction_dates = [t.created_at for t in transactions]
        if transfer_pairs:
            all_transaction_dates.extend(
                [outgoing.created_at for outgoing, _, _ in transfer_pairs]
            )

        if all_transaction_dates:
            earliest_date = min(all_transaction_dates)
            account.created_at = earliest_date - timedelta(days=1)
        else:
            account.created_at = start_date
        account.save(update_fields=['balance', 'created_at'])

    def _generate_reference(self, created_at) -> str:
        timestamp = created_at.strftime('%Y%m%d%H%M%S')
        random_suffix = get_random_string(6, allowed_chars='0123456789ABCDEF')
        reference = f'TRX-{timestamp}-{random_suffix}'

        while Transaction.objects.filter(reference=reference).exists():
            random_suffix = get_random_string(
                6, allowed_chars='0123456789ABCDEF'
            )
            reference = f'TRX-{timestamp}-{random_suffix}'

        return reference
