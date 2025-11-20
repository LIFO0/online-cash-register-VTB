import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from banking.models import Account, Transaction


class Command(BaseCommand):
    help = (
        "Рандомизирует даты существующих транзакций, распределяя их в прошлом"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months-back",
            type=int,
            default=12,
            help=(
                "Количество месяцев назад для распределения транзакций "
                "(по умолчанию: 12)"
            ),
        )

    def handle(self, *args, **options):
        months_back = options["months_back"]
        now = timezone.now()
        start_date = now - timedelta(days=months_back * 30)

        if start_date >= now:
            start_date = now - timedelta(days=1)

        self.stdout.write("Начинаю рандомизацию дат транзакций...")

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
                f"Успешно обновлено {total_updated} транзакций. "
                f"Даты распределены за последние {months_back} месяцев."
            )
        )
