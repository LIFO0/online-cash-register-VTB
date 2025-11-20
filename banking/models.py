from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from .utils import normalize_text


class ClientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile',
    )
    full_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255, blank=True)
    is_blocked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __str__(self) -> str:
        return self.full_name

    @property
    def has_blocked_accounts(self) -> bool:
        """
        Возвращает True, если среди счетов есть заблокированные.
        Использует предварительную выборку accounts, чтобы избежать
        лишних запросов.
        """
        prefetched_accounts = getattr(
            self, '_prefetched_objects_cache', {}
        ).get('accounts')
        if prefetched_accounts is not None:
            return any(account.is_blocked for account in prefetched_accounts)
        return self.accounts.filter(is_blocked=True).exists()

    @property
    def is_effectively_blocked(self) -> bool:
        """
        Клиент считается заблокированным, если заблокирован профиль
        или любой из его счетов.
        """
        return self.is_blocked or self.has_blocked_accounts


class Account(models.Model):
    client = models.ForeignKey(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='accounts',
    )
    account_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Счёт'
        verbose_name_plural = 'Счета'

    def __str__(self) -> str:
        return f'{self.account_number} ({self.client.full_name})'


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Пополнение'
        WITHDRAWAL = 'withdrawal', 'Снятие'
        TRANSFER_OUT = 'transfer_out', 'Перевод (списание)'
        TRANSFER_IN = 'transfer_in', 'Перевод (зачисление)'

    class Status(models.TextChoices):
        PENDING = 'pending', 'В обработке'
        COMPLETED = 'completed', 'Завершена'
        CANCELLED = 'cancelled', 'Отменена'

    reference = models.CharField(max_length=32, unique=True, editable=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    transaction_type = models.CharField(
        max_length=20, choices=TransactionType.choices
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    performed_by = models.ForeignKey(
        ClientProfile,
        null=True,
        blank=True,
        related_name='initiated_transactions',
        on_delete=models.SET_NULL,
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='processed_transactions',
        on_delete=models.SET_NULL,
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='cancelled_transactions',
        on_delete=models.SET_NULL,
    )
    note = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(blank=True, null=True)
    related_transaction = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='mirror_transactions',
    )

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.reference} — {self.get_transaction_type_display()}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        if self.note:
            self.note = normalize_text(self.note)
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference() -> str:
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = get_random_string(4, allowed_chars='0123456789')
        return f'TRX-{timestamp}-{random_suffix}'

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def is_completed(self) -> bool:
        return self.status == self.Status.COMPLETED

    @property
    def is_cancelled(self) -> bool:
        return self.status == self.Status.CANCELLED

    @property
    def counterparty_account(self) -> Account | None:
        if self.related_transaction_id:
            return self.related_transaction.account
        if self.metadata and self.metadata.get('counterparty_account_number'):
            return Account.objects.filter(
                account_number=self.metadata['counterparty_account_number']
            ).first()
        return None
