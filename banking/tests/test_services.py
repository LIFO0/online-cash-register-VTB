"""
Расширенные тесты для сервисов приложения banking.

Проверяют бизнес-логику транзакций, включая граничные случаи,
валидацию лимитов и обработку ошибок.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from banking.models import Account, ClientProfile, Transaction
from banking.services import (
    cancel_transaction,
    create_and_process_transaction,
    create_and_process_transfer,
    finalize_transaction,
    toggle_account_block,
)


User = get_user_model()


class TransactionServiceEdgeCasesTests(TestCase):
    """Тесты граничных случаев для транзакций."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        cls.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True,
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Иван Клиент',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_deposit_minimum_amount(self, mock_sleep):
        """Проверка пополнения минимальной суммы."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('10.00'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(self.account.balance, Decimal('1010.00'))

    @patch('banking.services.time.sleep', return_value=None)
    def test_deposit_maximum_amount(self, mock_sleep):
        """Проверка пополнения максимальной суммы."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100000.00'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(self.account.balance, Decimal('101000.00'))

    @patch('banking.services.time.sleep', return_value=None)
    def test_withdrawal_exact_balance(self, mock_sleep):
        """Проверка снятия точной суммы баланса."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('1000.00'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(self.account.balance, Decimal('0.00'))

    @patch('banking.services.time.sleep', return_value=None)
    def test_withdrawal_exceeds_balance(self, mock_sleep):
        """Проверка снятия суммы, превышающей баланс."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('1000.01'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertFalse(result.completed)
        self.assertEqual(
            result.transaction.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(self.account.balance, Decimal('1000.00'))

    @patch('banking.services.time.sleep', return_value=None)
    def test_withdrawal_limit_exceeded(self, mock_sleep):
        """Проверка превышения лимита снятия."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('100001.00'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertFalse(result.completed)
        self.assertEqual(
            result.transaction.status,
            Transaction.Status.CANCELLED
        )
        self.assertIn('лимит снятия', result.message)

    @patch('banking.services.time.sleep', return_value=None)
    def test_transaction_with_empty_note(self, mock_sleep):
        """Проверка транзакции с пустой заметкой."""
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            note='',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.transaction.note, '')

    @patch('banking.services.time.sleep', return_value=None)
    def test_transaction_with_mojibake_note(self, mock_sleep):
        """Проверка транзакции с mojibake в заметке."""
        mojibake = 'Привет'.encode('utf-8').decode('latin1')
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            note=mojibake,
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.transaction.note, 'Привет')

    @patch('banking.services.time.sleep', return_value=None)
    def test_transaction_cancelled_when_client_blocked(self, mock_sleep):
        """Проверка отмены при блокировке клиента."""
        self.client_profile.is_blocked = True
        self.client_profile.save()

        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.assertFalse(result.completed)
        self.assertEqual(
            result.transaction.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(result.message, 'Счёт заблокирован.')


class TransferServiceEdgeCasesTests(TestCase):
    """Тесты граничных случаев для переводов."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='sender',
            password='testpass123',
        )
        cls.target_user = User.objects.create_user(
            username='receiver',
            password='testpass123',
        )
        cls.staff_user = User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True,
        )
        cls.sender_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Отправитель',
        )
        cls.receiver_profile = ClientProfile.objects.create(
            user=cls.target_user,
            full_name='Получатель',
        )
        cls.sender_account = Account.objects.create(
            client=cls.sender_profile,
            account_number='40817810000000000001',
            balance=Decimal('150000.00'),
        )
        cls.receiver_account = Account.objects.create(
            client=cls.receiver_profile,
            account_number='40817810000000000002',
            balance=Decimal('1000.00'),
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_minimum_amount(self, mock_sleep):
        """Проверка перевода минимальной суммы."""
        initial_sender_balance = self.sender_account.balance
        initial_receiver_balance = self.receiver_account.balance
        transfer_amount = Decimal('10.00')
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=transfer_amount,
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.sender_account.refresh_from_db()
        self.receiver_account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(
            self.sender_account.balance,
            initial_sender_balance - transfer_amount
        )
        self.assertEqual(
            self.receiver_account.balance,
            initial_receiver_balance + transfer_amount
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_maximum_amount(self, mock_sleep):
        """Проверка перевода максимальной суммы."""
        initial_sender_balance = self.sender_account.balance
        initial_receiver_balance = self.receiver_account.balance
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=Decimal('100000.00'),
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.sender_account.refresh_from_db()
        self.receiver_account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(
            self.sender_account.balance,
            initial_sender_balance - Decimal('100000.00')
        )
        self.assertEqual(
            self.receiver_account.balance,
            initial_receiver_balance + Decimal('100000.00')
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_limit_exceeded(self, mock_sleep):
        """Проверка превышения лимита перевода."""
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=Decimal('100001.00'),
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.assertFalse(result.completed)
        self.assertIn('лимит перевода', result.message)

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_exact_balance(self, mock_sleep):
        """Проверка перевода точной суммы баланса."""
        transfer_amount = Decimal('5000.00')
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=transfer_amount,
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.sender_account.refresh_from_db()
        self.receiver_account.refresh_from_db()
        self.assertTrue(result.completed)
        self.assertEqual(
            self.sender_account.balance,
            Decimal('150000.00') - transfer_amount
        )
        self.assertEqual(
            self.receiver_account.balance,
            Decimal('1000.00') + transfer_amount
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_exceeds_balance(self, mock_sleep):
        """Проверка перевода суммы, превышающей баланс."""
        initial_sender_balance = self.sender_account.balance
        initial_receiver_balance = self.receiver_account.balance
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=initial_sender_balance + Decimal('0.01'),
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.sender_account.refresh_from_db()
        self.receiver_account.refresh_from_db()
        self.assertFalse(result.completed)
        outgoing = result.transaction
        incoming = outgoing.related_transaction
        self.assertEqual(
            outgoing.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(
            incoming.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(
            self.sender_account.balance,
            initial_sender_balance
        )
        self.assertEqual(
            self.receiver_account.balance,
            initial_receiver_balance
        )

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_when_source_blocked(self, mock_sleep):
        """Проверка перевода при блокировке счета отправителя."""
        self.sender_account.is_blocked = True
        self.sender_account.save()

        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=Decimal('100.00'),
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.assertFalse(result.completed)
        self.assertIn('заблокирован', result.message)

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_when_target_blocked(self, mock_sleep):
        """Проверка перевода при блокировке счета получателя."""
        self.receiver_account.is_blocked = True
        self.receiver_account.save()

        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=Decimal('100.00'),
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        self.assertFalse(result.completed)
        self.assertIn('заблокирован', result.message)

    @patch('banking.services.time.sleep', return_value=None)
    def test_transfer_creates_related_transactions(self, mock_sleep):
        """Проверка создания связанных транзакций."""
        result = create_and_process_transfer(
            source_account=self.sender_account,
            target_account=self.receiver_account,
            amount=Decimal('200.00'),
            note='Тестовый перевод',
            performed_by=self.sender_profile,
            processed_by=self.staff_user,
        )
        outgoing = result.transaction
        incoming = outgoing.related_transaction

        self.assertIsNotNone(incoming)
        self.assertEqual(outgoing.related_transaction, incoming)
        self.assertEqual(incoming.related_transaction, outgoing)
        self.assertEqual(
            outgoing.transaction_type,
            Transaction.TransactionType.TRANSFER_OUT
        )
        self.assertEqual(
            incoming.transaction_type,
            Transaction.TransactionType.TRANSFER_IN
        )


class CancelTransactionTests(TestCase):
    """Тесты для отмены транзакций."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        cls.staff_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Иван Клиент',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

    def test_cancel_pending_deposit(self):
        """Проверка отмены ожидающего пополнения."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.PENDING,
        )
        cancelled = cancel_transaction(
            transaction.id,
            cancelled_by=self.staff_user,
            reason='Тестовая отмена',
        )
        cancelled.refresh_from_db()
        self.assertEqual(
            cancelled.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(cancelled.cancelled_by, self.staff_user)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal('1000.00'))

    def test_cancel_completed_deposit(self):
        """Проверка отмены завершенного пополнения."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.COMPLETED,
        )
        self.account.balance += transaction.amount
        self.account.save()

        cancelled = cancel_transaction(
            transaction.id,
            cancelled_by=self.staff_user,
            reason='Отмена пополнения',
        )
        cancelled.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(
            cancelled.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(self.account.balance, Decimal('1000.00'))

    def test_cancel_completed_withdrawal(self):
        """Проверка отмены завершенного снятия."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('200.00'),
            status=Transaction.Status.COMPLETED,
        )
        self.account.balance -= transaction.amount
        self.account.save()

        cancelled = cancel_transaction(
            transaction.id,
            cancelled_by=self.staff_user,
            reason='Отмена снятия',
        )
        cancelled.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(
            cancelled.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(self.account.balance, Decimal('1000.00'))

    def test_cancel_already_cancelled(self):
        """Проверка повторной отмены уже отмененной транзакции."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.CANCELLED,
        )
        cancelled = cancel_transaction(
            transaction.id,
            cancelled_by=self.staff_user,
        )
        self.assertEqual(cancelled.id, transaction.id)
        self.assertEqual(
            cancelled.status,
            Transaction.Status.CANCELLED
        )

    def test_cancel_transfer_cancels_both(self):
        """Проверка отмены перевода (обе транзакции)."""
        target_user = User.objects.create_user(
            username='target',
            password='testpass123',
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
            amount=Decimal('300.00'),
            status=Transaction.Status.COMPLETED,
        )
        incoming = Transaction.objects.create(
            account=target_account,
            transaction_type=Transaction.TransactionType.TRANSFER_IN,
            amount=Decimal('300.00'),
            status=Transaction.Status.COMPLETED,
        )
        outgoing.related_transaction = incoming
        incoming.related_transaction = outgoing
        Transaction.objects.bulk_update(
            [outgoing, incoming],
            fields=['related_transaction']
        )

        self.account.balance -= outgoing.amount
        target_account.balance += incoming.amount
        self.account.save()
        target_account.save()

        cancel_transaction(
            outgoing.id,
            cancelled_by=self.staff_user,
            reason='Отмена перевода',
        )

        outgoing.refresh_from_db()
        incoming.refresh_from_db()
        self.account.refresh_from_db()
        target_account.refresh_from_db()

        self.assertEqual(outgoing.status, Transaction.Status.CANCELLED)
        self.assertEqual(incoming.status, Transaction.Status.CANCELLED)
        self.assertEqual(self.account.balance, Decimal('1000.00'))
        self.assertEqual(target_account.balance, Decimal('500.00'))


class ToggleAccountBlockTests(TestCase):
    """Тесты для блокировки/разблокировки счетов."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Иван Клиент',
        )
        cls.account1 = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
            is_blocked=False,
        )
        cls.account2 = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000002',
            balance=Decimal('500.00'),
            is_blocked=False,
        )

    def test_block_account(self):
        """Проверка блокировки счета."""
        result = toggle_account_block(self.account1, blocked=True)
        result.refresh_from_db()
        self.assertTrue(result.is_blocked)

    def test_unblock_account(self):
        """Проверка разблокировки счета."""
        self.account1.is_blocked = True
        self.account1.save()
        result = toggle_account_block(self.account1, blocked=False)
        result.refresh_from_db()
        self.assertFalse(result.is_blocked)

    def test_blocking_account_updates_client_status(self):
        """Проверка обновления статуса клиента при блокировке."""
        toggle_account_block(self.account1, blocked=True)
        self.client_profile.refresh_from_db()
        self.assertTrue(self.client_profile.is_blocked)

    def test_unblocking_last_account_updates_client_status(self):
        """Проверка обновления статуса при разблокировке последнего."""
        self.account1.is_blocked = True
        self.account1.save()
        self.client_profile.is_blocked = True
        self.client_profile.save()

        toggle_account_block(self.account1, blocked=False)
        self.client_profile.refresh_from_db()
        self.assertFalse(self.client_profile.is_blocked)

    def test_unblocking_one_account_keeps_client_blocked(self):
        """Проверка статуса при разблокировке одного из счетов."""
        self.account1.is_blocked = True
        self.account1.save()
        self.account2.is_blocked = True
        self.account2.save()
        self.client_profile.is_blocked = True
        self.client_profile.save()

        toggle_account_block(self.account1, blocked=False)
        self.client_profile.refresh_from_db()
        self.assertTrue(self.client_profile.is_blocked)


class FinalizeTransactionTests(TestCase):
    """Тесты для финализации транзакций."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        cls.staff_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Иван Клиент',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

    def test_finalize_pending_deposit(self):
        """Проверка финализации ожидающего пополнения."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('150.00'),
            status=Transaction.Status.PENDING,
        )
        finalized = finalize_transaction(
            transaction.id,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertEqual(
            finalized.status,
            Transaction.Status.COMPLETED
        )
        self.assertEqual(self.account.balance, Decimal('1150.00'))
        self.assertIsNotNone(finalized.processed_at)

    def test_finalize_pending_withdrawal_sufficient_funds(self):
        """Проверка финализации снятия при достаточных средствах."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('300.00'),
            status=Transaction.Status.PENDING,
        )
        finalized = finalize_transaction(
            transaction.id,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertEqual(
            finalized.status,
            Transaction.Status.COMPLETED
        )
        self.assertEqual(self.account.balance, Decimal('700.00'))

    def test_finalize_pending_withdrawal_insufficient_funds(self):
        """Проверка финализации снятия при недостаточных средствах."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('1500.00'),
            status=Transaction.Status.PENDING,
        )
        finalized = finalize_transaction(
            transaction.id,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.assertEqual(
            finalized.status,
            Transaction.Status.CANCELLED
        )
        self.assertEqual(self.account.balance, Decimal('1000.00'))
        self.assertIn('Недостаточно средств', finalized.note)

    def test_finalize_already_completed(self):
        """Проверка финализации уже завершенной транзакции."""
        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.COMPLETED,
        )
        finalized = finalize_transaction(
            transaction.id,
            processed_by=self.staff_user,
        )
        self.assertEqual(finalized.status, Transaction.Status.COMPLETED)

    def test_finalize_when_account_blocked(self):
        """Проверка финализации при заблокированном счете."""
        self.account.is_blocked = True
        self.account.save()

        transaction = Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            status=Transaction.Status.PENDING,
        )
        finalized = finalize_transaction(
            transaction.id,
            processed_by=self.staff_user,
        )
        self.assertEqual(
            finalized.status,
            Transaction.Status.CANCELLED
        )
        self.assertIn('заблокирован', finalized.note)
