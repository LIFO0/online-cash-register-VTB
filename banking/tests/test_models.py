"""
Тесты для моделей приложения banking.

Проверяют работу моделей ClientProfile, Account и Transaction,
включая их свойства, методы и бизнес-логику.
"""
from decimal import Decimal
from itertools import count
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from banking.models import Account, ClientProfile, Transaction


User = get_user_model()


class ClientProfileModelTests(TestCase):
    """Тесты для модели ClientProfile."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных для всех тестов класса."""
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Иван Иванов',
            job_title='Инженер',
        )

    def test_str_representation(self):
        """Проверка строкового представления профиля."""
        self.assertEqual(str(self.client_profile), 'Иван Иванов')

    def test_has_blocked_accounts_with_no_accounts(self):
        """Проверка has_blocked_accounts при отсутствии счетов."""
        self.assertFalse(self.client_profile.has_blocked_accounts)

    def test_has_blocked_accounts_with_active_accounts(self):
        """Проверка has_blocked_accounts при активных счетах."""
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=False,
        )
        self.assertFalse(self.client_profile.has_blocked_accounts)

    def test_has_blocked_accounts_with_blocked_account(self):
        """Проверка has_blocked_accounts при заблокированном счете."""
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=True,
        )
        self.assertTrue(self.client_profile.has_blocked_accounts)

    def test_is_effectively_blocked_when_profile_blocked(self):
        """Проверка is_effectively_blocked при блокировке профиля."""
        self.client_profile.is_blocked = True
        self.client_profile.save()
        self.assertTrue(self.client_profile.is_effectively_blocked)

    def test_is_effectively_blocked_when_account_blocked(self):
        """Проверка is_effectively_blocked при блокировке счета."""
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=True,
        )
        refreshed = ClientProfile.objects.get(pk=self.client_profile.pk)
        self.assertTrue(refreshed.is_effectively_blocked)

    def test_is_effectively_blocked_when_not_blocked(self):
        """Проверка is_effectively_blocked при отсутствии блокировок."""
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=False,
        )
        self.assertFalse(self.client_profile.is_effectively_blocked)

    def test_has_blocked_accounts_with_prefetched_accounts(self):
        """Проверка has_blocked_accounts с предзагруженными счетами."""
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=True,
        )
        Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000002',
            balance=Decimal('500.00'),
            is_blocked=False,
        )
        profile = ClientProfile.objects.prefetch_related(
            'accounts'
        ).get(pk=self.client_profile.pk)
        self.assertTrue(profile.has_blocked_accounts)


class AccountModelTests(TestCase):
    """Тесты для модели Account."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных для всех тестов класса."""
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Петр Петров',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('5000.00'),
        )

    def test_str_representation(self):
        """Проверка строкового представления счета."""
        expected = '40817810000000000001 (Петр Петров)'
        self.assertEqual(str(self.account), expected)

    def test_account_number_unique(self):
        """Проверка уникальности номера счета."""
        with self.assertRaises(Exception):
            Account.objects.create(
                client=self.client_profile,
                account_number='40817810000000000001',
                balance=Decimal('100.00'),
            )

    def test_default_balance(self):
        """Проверка баланса по умолчанию."""
        new_account = Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000002',
        )
        self.assertEqual(new_account.balance, Decimal('0.00'))

    def test_default_is_blocked(self):
        """Проверка статуса блокировки по умолчанию."""
        new_account = Account.objects.create(
            client=self.client_profile,
            account_number='40817810000000000003',
        )
        self.assertFalse(new_account.is_blocked)

    def test_created_at_auto_set(self):
        """Проверка автоматической установки created_at."""
        self.assertIsNotNone(self.account.created_at)
        self.assertLessEqual(
            self.account.created_at,
            timezone.now()
        )


class TransactionModelTests(TestCase):
    """Тесты для модели Transaction."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных для всех тестов класса."""
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Сергей Сергеев',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

    def test_reference_auto_generation(self):
        """Проверка автоматической генерации reference."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        self.assertTrue(transaction.reference.startswith('TRX-'))
        self.assertGreater(len(transaction.reference), 10)

    @patch('django.utils.timezone.now')
    def test_reference_unique(self, mock_now):
        """Проверка уникальности reference."""
        # Мокаем timezone.now для разных значений
        from datetime import datetime, timedelta, timezone as dt_timezone
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
        counter = count()

        def time_generator():
            """Генератор времени, который возвращает разные значения."""
            return base_time + timedelta(seconds=next(counter))

        mock_now.side_effect = time_generator
        t1 = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        t2 = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('200.00'),
        )
        # Reference должны быть уникальными
        self.assertNotEqual(t1.reference, t2.reference)
        self.assertTrue(t1.reference.startswith('TRX-'))
        self.assertTrue(t2.reference.startswith('TRX-'))

    def test_note_normalization_on_save(self):
        """Проверка нормализации заметки при сохранении."""
        mojibake = 'Привет'.encode('utf-8').decode('latin1')
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            note=mojibake,
        )
        self.assertEqual(transaction.note, 'Привет')

    def test_str_representation(self):
        """Проверка строкового представления транзакции."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        self.assertIn('TRX-', str(transaction))
        self.assertIn('Пополнение', str(transaction))

    def test_default_status(self):
        """Проверка статуса по умолчанию."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        self.assertEqual(
            transaction.status,
            Transaction.Status.PENDING
        )

    def test_is_pending_property(self):
        """Проверка свойства is_pending."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.PENDING,
        )
        self.assertTrue(transaction.is_pending)
        transaction.status = Transaction.Status.COMPLETED
        self.assertFalse(transaction.is_pending)

    def test_is_completed_property(self):
        """Проверка свойства is_completed."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.COMPLETED,
        )
        self.assertTrue(transaction.is_completed)
        transaction.status = Transaction.Status.PENDING
        self.assertFalse(transaction.is_completed)

    def test_is_cancelled_property(self):
        """Проверка свойства is_cancelled."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.CANCELLED,
        )
        self.assertTrue(transaction.is_cancelled)
        transaction.status = Transaction.Status.PENDING
        self.assertFalse(transaction.is_cancelled)

    def test_counterparty_account_from_related(self):
        """Проверка counterparty_account через related_transaction."""
        target_user = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass',
        )
        target_profile = ClientProfile.objects.create(
            user=target_user,
            full_name='Получатель',
        )
        target_account = Account.objects.create(
            client=target_profile,
            account_number='40817810000000000002',
            balance=Decimal('500.00'),
        )

        outgoing = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.TRANSFER_OUT,
            amount=Decimal('100.00'),
        )
        incoming = Transaction.objects.create(
            account=target_account,
            transaction_type=Transaction.TransactionType.TRANSFER_IN,
            amount=Decimal('100.00'),
        )
        outgoing.related_transaction = incoming
        incoming.related_transaction = outgoing
        Transaction.objects.bulk_update(
            [outgoing, incoming],
            fields=['related_transaction']
        )

        outgoing.refresh_from_db()
        self.assertEqual(
            outgoing.counterparty_account,
            target_account
        )

    def test_counterparty_account_from_metadata(self):
        """Проверка counterparty_account через metadata."""
        target_user = User.objects.create_user(
            username='target',
            email='target@example.com',
            password='pass',
        )
        target_profile = ClientProfile.objects.create(
            user=target_user,
            full_name='Получатель',
        )
        target_account = Account.objects.create(
            client=target_profile,
            account_number='40817810000000000002',
            balance=Decimal('500.00'),
        )

        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.TRANSFER_OUT,
            amount=Decimal('100.00'),
            metadata={
                'counterparty_account_number': (
                    target_account.account_number
                )
            },
        )

        self.assertEqual(
            transaction.counterparty_account,
            target_account
        )

    def test_counterparty_account_none_when_no_relation(self):
        """Проверка counterparty_account при отсутствии связи."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        self.assertIsNone(transaction.counterparty_account)

    def test_ordering(self):
        """Проверка сортировки транзакций."""
        t1 = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
        )
        t2 = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('200.00'),
        )
        transactions = list(
            Transaction.objects.filter(account=self.account)
        )
        # Новые транзакции должны быть первыми
        self.assertEqual(transactions[0].id, t2.id)
        self.assertEqual(transactions[1].id, t1.id)

    def test_transaction_type_choices(self):
        """Проверка доступных типов транзакций."""
        choices = Transaction.TransactionType.choices
        self.assertIn(('deposit', 'Пополнение'), choices)
        self.assertIn(('withdrawal', 'Снятие'), choices)
        self.assertIn(('transfer_out', 'Перевод (списание)'), choices)
        self.assertIn(('transfer_in', 'Перевод (зачисление)'), choices)

    def test_status_choices(self):
        """Проверка доступных статусов транзакций."""
        choices = Transaction.Status.choices
        self.assertIn(('pending', 'В обработке'), choices)
        self.assertIn(('completed', 'Завершена'), choices)
        self.assertIn(('cancelled', 'Отменена'), choices)
