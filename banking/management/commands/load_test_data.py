import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string

from banking.models import Account, ClientProfile, Transaction
from banking.utils import (
    normalize_text,
    biased_random_amount,
    random_target_balance,
)

RUSSIAN_MALE_FIRST_NAMES = [
    "Александр",
    "Алексей",
    "Андрей",
    "Антон",
    "Артем",
    "Борис",
    "Вадим",
    "Василий",
    "Виктор",
    "Владимир",
    "Дмитрий",
    "Евгений",
    "Иван",
    "Игорь",
    "Константин",
    "Максим",
    "Михаил",
    "Николай",
    "Олег",
    "Павел",
    "Роман",
    "Сергей",
    "Юрий",
    "Ярослав",
]

RUSSIAN_FEMALE_FIRST_NAMES = [
    "Анна",
    "Елена",
    "Ирина",
    "Мария",
    "Наталья",
    "Ольга",
    "Светлана",
    "Татьяна",
    "Екатерина",
    "Юлия",
    "Анастасия",
    "Дарья",
    "Виктория",
    "Александра",
    "Валентина",
    "Галина",
    "Людмила",
    "Лариса",
    "Марина",
    "Надежда",
    "Тамара",
    "Валерия",
    "Полина",
]

RUSSIAN_MALE_LAST_NAMES = [
    "Иванов",
    "Петров",
    "Смирнов",
    "Кузнецов",
    "Попов",
    "Соколов",
    "Лебедев",
    "Козлов",
    "Новиков",
    "Морозов",
    "Петухов",
    "Волков",
    "Соловьев",
    "Васильев",
    "Зайцев",
    "Павлов",
    "Семенов",
    "Голубев",
    "Виноградов",
    "Богданов",
    "Воробьев",
    "Федоров",
    "Михайлов",
    "Белов",
    "Тарасов",
    "Беляев",
    "Комаров",
    "Орлов",
    "Киселев",
    "Макаров",
    "Андреев",
    "Ковалев",
    "Ильин",
    "Гусев",
    "Титов",
    "Кузьмин",
    "Кудрявцев",
    "Баранов",
    "Куликов",
    "Алексеев",
    "Степанов",
    "Яковлев",
    "Сорокин",
    "Сергеев",
    "Романов",
    "Захаров",
    "Борисов",
    "Королев",
    "Герасимов",
    "Пономарев",
    "Григорьев",
    "Лазарев",
    "Медведев",
    "Ершов",
    "Никитин",
    "Соболев",
    "Рябов",
    "Поляков",
    "Цветков",
    "Данилов",
    "Жуков",
    "Фролов",
]

RUSSIAN_FEMALE_LAST_NAMES = [
    "Иванова",
    "Петрова",
    "Смирнова",
    "Кузнецова",
    "Попова",
    "Соколова",
    "Лебедева",
    "Козлова",
    "Новикова",
    "Морозова",
    "Петухова",
    "Волкова",
    "Соловьева",
    "Васильева",
    "Зайцева",
    "Павлова",
    "Семенова",
    "Голубева",
    "Виноградова",
    "Богданова",
    "Воробьева",
    "Федорова",
    "Михайлова",
    "Белова",
    "Тарасова",
    "Беляева",
    "Комарова",
    "Орлова",
    "Киселева",
    "Макарова",
    "Андреева",
    "Ковалева",
    "Ильина",
    "Гусева",
    "Титова",
    "Кузьмина",
    "Кудрявцева",
    "Баранова",
    "Куликова",
    "Алексеева",
    "Степанова",
    "Яковлева",
    "Сорокина",
    "Сергеева",
    "Романова",
    "Захарова",
    "Борисова",
    "Королева",
    "Герасимова",
    "Пономарева",
    "Григорьева",
    "Лазарева",
    "Медведева",
    "Ершова",
    "Никитина",
    "Соболева",
    "Рябова",
    "Полякова",
    "Цветкова",
    "Данилова",
    "Жукова",
    "Фролова",
]

RUSSIAN_JOB_TITLES = [
    "Инженер",
    "Менеджер",
    "Бухгалтер",
    "Врач",
    "Учитель",
    "Программист",
    "Дизайнер",
    "Юрист",
    "Экономист",
    "Маркетолог",
    "Продавец",
    "Повар",
    "Водитель",
    "Строитель",
    "Архитектор",
    "Журналист",
    "Переводчик",
    "Фармацевт",
    "Психолог",
    "Социальный работник",
    "Ведущий инженер",
    "Старший менеджер",
    "Главный бухгалтер",
    "Врач-терапевт",
    "Учитель математики",
    "Ведущий программист",
    "Графический дизайнер",
    "Юрист-консультант",
    "Финансовый аналитик",
    "Менеджер по продажам",
    "Шеф-повар",
    "Инженер-конструктор",
]

TRANSACTION_NOTES = {
    Transaction.TransactionType.DEPOSIT: [
        "Зарплатное поступление",
        "Бонус по проекту",
        "Возврат средств",
        "Пополнение с карты",
        "Перевод от друга",
        "Премия",
        "Дивиденды",
        "Возврат налога",
        "Подарок",
        "Компенсация",
    ],
    Transaction.TransactionType.WITHDRAWAL: [
        "Снятие наличных в банкомате",
        "Оплата покупок",
        "Оплата услуг",
        "Перевод на карту",
        "Оплата коммунальных услуг",
        "Покупка продуктов",
        "Оплата интернета",
        "Оплата мобильной связи",
        "Покупка билетов",
        "Оплата ресторана",
    ],
    Transaction.TransactionType.TRANSFER_OUT: [
        "Перевод другу",
        "Перевод родственнику",
        "Оплата займа",
        "Перевод на другой счет",
        "Оплата услуг",
        "Перевод за товар",
    ],
    Transaction.TransactionType.TRANSFER_IN: [
        "Перевод от друга",
        "Перевод от родственника",
        "Возврат займа",
        "Перевод с другого счета",
        "Оплата за услуги",
        "Перевод за товар",
    ],
}


class Command(BaseCommand):
    help = "Загружает демонстрационные данные для Онлайн-касса ВТБ."

    def handle(self, *args, **options):
        User = get_user_model()

        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@vtb.test",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("Admin@1234")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        if created:
            self.stdout.write(
                self.style.SUCCESS("Создан администратор: admin / Admin@1234")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Администратор уже существует: admin / Admin@1234."
                )
            )

        clients_data = [
            {
                "username": "client1",
                "password": "Client@1234",
                "full_name": "Иван Петров",
                "job_title": "Ведущий инженер",
                "account_number": "40817810000000000001",
            },
            {
                "username": "client2",
                "password": "Client@1234",
                "full_name": "Мария Смирнова",
                "job_title": "Менеджер по продукту",
                "account_number": "40817810000000000002",
            },
        ]

        for idx, client in enumerate(clients_data, start=1):
            account_blocked = random.random() < 0.05
            user, _ = User.objects.get_or_create(
                username=client["username"],
                defaults={
                    "email": f"{client['username']}@vtb.test",
                    "first_name": client["full_name"].split()[0],
                    "last_name": client["full_name"].split()[-1],
                },
            )
            user.set_password(client["password"])
            user.is_staff = False
            user.is_superuser = False
            user.save()

            profile, _ = ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": client["full_name"],
                    "job_title": client["job_title"],
                    "is_blocked": account_blocked,
                },
            )
            profile.full_name = client["full_name"]
            profile.job_title = client["job_title"]
            if profile.is_blocked != account_blocked:
                profile.is_blocked = account_blocked
            profile.save()

            account, _ = Account.objects.get_or_create(
                client=profile,
                account_number=client["account_number"],
                defaults={
                    "balance": Decimal("0.00"),
                    "is_blocked": account_blocked,
                },
            )
            if account.is_blocked != account_blocked:
                account.is_blocked = account_blocked
                account.save(update_fields=["is_blocked"])

            self._seed_transactions(account, profile, idx)

        self.stdout.write("Генерирую 50 дополнительных учетных записей...")
        self._generate_accounts(count=50)

        self.stdout.write("Рандомизирую даты транзакций...")
        self._randomize_all_transaction_dates()

        self.stdout.write("Корректирую балансы счетов...")
        self._adjust_account_balances()

        self.stdout.write(
            self.style.SUCCESS("Тестовые данные успешно загружены.")
        )

    def _seed_transactions(
        self, account: Account, profile: ClientProfile, seed_index: int
    ) -> None:
        Transaction.objects.filter(account=account).delete()
        account.balance = Decimal("0.00")
        account.save(update_fields=["balance"])

        now = timezone.now()
        months_back = random.randint(1, 2)
        start_date = now - timedelta(days=months_back * 30)
        if start_date >= now:
            start_date = now - timedelta(days=1)

        # Лимиты: минимум 10 ₽, максимум 100000 ₽
        MIN_AMOUNT = Decimal("10")
        MAX_AMOUNT = Decimal("100000")

        deposit_amount = Decimal("75000.00") + Decimal(seed_index * 1000)
        deposit_amount = max(MIN_AMOUNT, min(deposit_amount, MAX_AMOUNT))

        scenarios = [
            {
                "transaction_type": Transaction.TransactionType.DEPOSIT,
                "amount": deposit_amount,
                "note": "Зарплатное поступление",
            },
            {
                "transaction_type": Transaction.TransactionType.WITHDRAWAL,
                "amount": Decimal("15000.00"),
                "note": "Снятие наличных в банкомате",
            },
            {
                "transaction_type": Transaction.TransactionType.DEPOSIT,
                "amount": Decimal("20000.00"),
                "note": "Бонус по проекту",
            },
            {
                "transaction_type": Transaction.TransactionType.WITHDRAWAL,
                "amount": Decimal("5000.00"),
                "note": "Оплата путешествия",
            },
        ]

        total_days = (now - start_date).days
        if total_days < 1:
            total_days = 1

        transaction_dates = []
        for _ in range(len(scenarios)):
            days_offset = random.randint(0, total_days - 1)
            hours = random.randint(0, 23)
            minutes = random.randint(0, 59)
            seconds = random.randint(0, 59)
            created_at = start_date + timedelta(
                days=days_offset, hours=hours, minutes=minutes, seconds=seconds
            )
            if created_at >= now:
                created_at = now - timedelta(seconds=random.randint(1, 3600))
            transaction_dates.append(created_at)

        transaction_dates.sort()

        earliest_date = min(transaction_dates)
        account_created_at = earliest_date - timedelta(days=1)

        balance = Decimal("0.00")
        for scenario, created_at in zip(scenarios, transaction_dates):
            transaction = Transaction.objects.create(
                account=account,
                transaction_type=scenario["transaction_type"],
                amount=scenario["amount"],
                status=Transaction.Status.COMPLETED,
                note=normalize_text(scenario["note"]),
                performed_by=profile,
                processed_at=created_at
                + timedelta(minutes=random.randint(1, 10)),
            )
            Transaction.objects.filter(pk=transaction.pk).update(
                created_at=created_at
            )

            if (
                scenario["transaction_type"]
                == Transaction.TransactionType.DEPOSIT
            ):
                balance += scenario["amount"]
            else:
                balance -= scenario["amount"]

        account.balance = balance
        account.created_at = account_created_at
        account.save(update_fields=["balance", "created_at"])

    def _generate_accounts(self, count: int = 50) -> None:
        User = get_user_model()

        existing_account_numbers = set(
            Account.objects.values_list("account_number", flat=True)
        )

        created_count = 0
        start_index = 3

        for i in range(count):
            is_male = random.choice([True, False])
            if is_male:
                first_name = random.choice(RUSSIAN_MALE_FIRST_NAMES)
                last_name = random.choice(RUSSIAN_MALE_LAST_NAMES)
            else:
                first_name = random.choice(RUSSIAN_FEMALE_FIRST_NAMES)
                last_name = random.choice(RUSSIAN_FEMALE_LAST_NAMES)

            full_name = f"{first_name} {last_name}"
            job_title = random.choice(RUSSIAN_JOB_TITLES)

            username = f"client{start_index + i}"
            while User.objects.filter(username=username).exists():
                username = (
                    f"client{start_index + i}_{random.randint(1000, 9999)}"
                )

            account_number = f"4081781000000000{start_index + i:04d}"
            while account_number in existing_account_numbers:
                account_number = (
                    f"4081781000000{random.randint(100000, 999999)}"
                )
            existing_account_numbers.add(account_number)

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@vtb.test",
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )
            if not created:
                continue

            user.set_password("Client@1234")
            user.is_staff = False
            user.is_superuser = False
            user.save()

            account_blocked = random.random() < 0.01

            # Создаем профиль клиента
            profile, _ = ClientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": full_name,
                    "job_title": job_title,
                    "is_blocked": account_blocked,
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
                    "client": profile,
                    "balance": Decimal("0.00"),
                    "is_blocked": account_blocked,
                },
            )
            if account.client_id != profile.id:
                account.client = profile
                account.save(update_fields=["client"])
            if account.is_blocked != account_blocked:
                account.is_blocked = account_blocked
                account.save(update_fields=["is_blocked"])

            self._generate_transaction_history(
                account, profile, start_index + i
            )

            created_count += 1
            if (i + 1) % 10 == 0:
                self.stdout.write(
                    f"Создано {i + 1}/{count} учетных записей..."
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Создано {created_count} дополнительных учетных записей."
            )
        )

    def _generate_transaction_history(
        self, account: Account, profile: ClientProfile, seed: int
    ) -> None:
        Transaction.objects.filter(account=account).delete()
        account.balance = Decimal("0.00")

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
        MIN_AMOUNT = Decimal("10")
        MAX_AMOUNT = Decimal("100000")

        transactions = []
        transfer_pairs = []
        balance = Decimal("0.00")

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
                days=days_offset, hours=hours, minutes=minutes, seconds=seconds
            )
            if created_at >= now:
                created_at = now - timedelta(seconds=random.randint(1, 3600))
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
                        "TRX-", "TRX-IN-"
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
                            "counterparty_account_number": (
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
                            "counterparty_account_number": (
                                account.account_number
                            )
                        },
                    )

                    transfer_pairs.append((outgoing, incoming, target_account))
                    balance -= amount
            elif balance < Decimal("10000") or random.random() < 0.6:
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
                        processed_at=(
                            created_at
                            + timedelta(minutes=random.randint(1, 10))
                        ),
                    )
                    transactions.append(transaction)
                    balance -= amount

        saved_transactions = Transaction.objects.bulk_create(transactions)

        for saved, original in zip(saved_transactions, transactions):
            Transaction.objects.filter(pk=saved.pk).update(
                created_at=original.created_at,
                processed_at=original.processed_at,
            )

        for outgoing, incoming, target_account in transfer_pairs:
            outgoing.save()
            incoming.save()
            Transaction.objects.filter(pk=outgoing.pk).update(
                created_at=outgoing.created_at,
                processed_at=outgoing.processed_at,
            )
            Transaction.objects.filter(pk=incoming.pk).update(
                created_at=incoming.created_at,
                processed_at=incoming.processed_at,
            )
            outgoing.related_transaction = incoming
            incoming.related_transaction = outgoing
            outgoing.save()
            incoming.save()

            target_account.balance += incoming.amount
            target_account.save(update_fields=["balance"])

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
        account.save(update_fields=["balance", "created_at"])

    def _generate_reference(self, created_at) -> str:
        timestamp = created_at.strftime("%Y%m%d%H%M%S")
        random_suffix = get_random_string(6, allowed_chars="0123456789ABCDEF")
        reference = f"TRX-{timestamp}-{random_suffix}"

        while Transaction.objects.filter(reference=reference).exists():
            random_suffix = get_random_string(
                6, allowed_chars="0123456789ABCDEF"
            )
            reference = f"TRX-{timestamp}-{random_suffix}"

        return reference

    def _randomize_all_transaction_dates(self, months_back: int = 12) -> None:
        now = timezone.now()
        start_date = now - timedelta(days=months_back * 30)

        if start_date >= now:
            start_date = now - timedelta(days=1)

        accounts = Account.objects.all()
        total_updated = 0

        for account in accounts:
            transactions = Transaction.objects.filter(
                account=account
            ).order_by("id")

            if not transactions.exists():
                continue

            num_transactions = transactions.count()
            total_days = (now - start_date).days
            if total_days < 1:
                total_days = 1

            transaction_dates = []
            for _ in range(num_transactions):
                days_offset = random.randint(0, total_days - 1)
                hours = random.randint(0, 23)
                minutes = random.randint(0, 59)
                seconds = random.randint(0, 59)
                created_at = start_date + timedelta(
                    days=days_offset,
                    hours=hours,
                    minutes=minutes,
                    seconds=seconds,
                )
                if created_at >= now:
                    created_at = now - timedelta(
                        seconds=random.randint(1, 3600)
                    )
                transaction_dates.append(created_at)

            transaction_dates.sort()

            for transaction, new_date in zip(transactions, transaction_dates):
                processed_at = new_date + timedelta(
                    minutes=random.randint(1, 10)
                )

                Transaction.objects.filter(pk=transaction.pk).update(
                    created_at=new_date, processed_at=processed_at
                )
                total_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Рандомизировано {total_updated} транзакций за последние "
                f"{months_back} месяцев."
            )
        )

    def _adjust_account_balances(self) -> None:
        accounts = Account.objects.all()
        adjusted_count = 0

        for account in accounts:
            current_balance = account.balance

            target_balance = random_target_balance()

            if abs(current_balance - target_balance) < Decimal("1000"):
                continue

            difference = target_balance - current_balance

            now = timezone.now()
            transaction_date = now - timedelta(
                days=random.randint(1, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59),
            )

            # Лимиты: минимум 10 ₽, максимум 100000 ₽
            MIN_AMOUNT = Decimal("10")
            MAX_AMOUNT = Decimal("100000")

            if difference > 0:
                deposit_cap = min(difference, MAX_AMOUNT)
                if deposit_cap >= MIN_AMOUNT:
                    deposit_amount = biased_random_amount(
                        MIN_AMOUNT, deposit_cap
                    )
                    Transaction.objects.create(
                        account=account,
                        transaction_type=Transaction.TransactionType.DEPOSIT,
                        amount=deposit_amount,
                        status=Transaction.Status.COMPLETED,
                        reference=self._generate_reference(transaction_date),
                        note=normalize_text(
                            random.choice(
                                TRANSACTION_NOTES[
                                    Transaction.TransactionType.DEPOSIT
                                ]
                            )
                        ),
                        performed_by=account.client,
                        created_at=transaction_date,
                        processed_at=transaction_date
                        + timedelta(minutes=random.randint(1, 10)),
                    )
                    account.balance = current_balance + deposit_amount
            else:
                withdrawal_cap = min(
                    abs(difference), MAX_AMOUNT, current_balance
                )
                if (
                    withdrawal_cap >= MIN_AMOUNT
                    and current_balance >= withdrawal_cap
                ):
                    withdrawal_amount = biased_random_amount(
                        MIN_AMOUNT, withdrawal_cap
                    )
                    Transaction.objects.create(
                        account=account,
                        transaction_type=(
                            Transaction.TransactionType.WITHDRAWAL
                        ),
                        amount=withdrawal_amount,
                        status=Transaction.Status.COMPLETED,
                        reference=self._generate_reference(transaction_date),
                        note=normalize_text(
                            random.choice(
                                TRANSACTION_NOTES[
                                    Transaction.TransactionType.WITHDRAWAL
                                ]
                            )
                        ),
                        performed_by=account.client,
                        created_at=transaction_date,
                        processed_at=(
                            transaction_date
                            + timedelta(minutes=random.randint(1, 10))
                        ),
                    )
                    account.balance = current_balance - withdrawal_amount

            account.save(update_fields=["balance"])
            adjusted_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Скорректировано {adjusted_count} балансов счетов."
            )
        )
