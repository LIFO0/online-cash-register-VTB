from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from .forms import DepositForm, TransferForm, WithdrawalForm
from .models import Account, ClientProfile, Transaction
from .services import (
    create_and_process_transaction,
    create_and_process_transfer,
)
from .utils import normalize_text


class BankingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.staff_user = user_model.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='pass',
            is_staff=True,
        )
        cls.client_user = user_model.objects.create_user(
            username='client',
            email='client@example.com',
            password='pass',
        )
        cls.counterparty_user = user_model.objects.create_user(
            username='counterparty',
            email='counterparty@example.com',
            password='pass',
        )
        cls.client_profile = ClientProfile.objects.create(
            user=cls.client_user,
            full_name='Иван Клиент',
            job_title='Инженер',
        )
        cls.counterparty_profile = ClientProfile.objects.create(
            user=cls.counterparty_user,
            full_name='Пётр Получатель',
            job_title='Аналитик',
        )
        cls.account = Account.objects.create(
            client=cls.client_profile,
            account_number='40817810000000000001',
            balance=Decimal('500.00'),
        )
        cls.counterparty_account = Account.objects.create(
            client=cls.counterparty_profile,
            account_number='40817810000000000002',
            balance=Decimal('200.00'),
        )

    @staticmethod
    def make_mojibake(value: str = 'Привет') -> str:
        return value.encode('utf-8').decode('latin1')


class ClientProfileStatusTests(BankingTestCase):
    def test_is_effectively_blocked_when_profile_flag_set(self):
        self.client_profile.is_blocked = True
        self.client_profile.save(update_fields=['is_blocked'])
        self.client_profile.refresh_from_db()
        self.assertTrue(self.client_profile.is_effectively_blocked)

    def test_is_effectively_blocked_when_account_blocked(self):
        self.account.is_blocked = True
        self.account.save(update_fields=['is_blocked'])
        refreshed_client = ClientProfile.objects.get(pk=self.client_profile.pk)
        self.assertTrue(refreshed_client.is_effectively_blocked)

    def test_is_effectively_blocked_when_no_blocks(self):
        self.assertFalse(self.client_profile.is_effectively_blocked)


class NormalizeTextTests(TestCase):
    def test_returns_original_when_text_is_clean(self):
        self.assertEqual(normalize_text('Привет, мир'), 'Привет, мир')

    def test_fixes_common_cp1251_mojibake(self):
        original = 'Привет'
        mojibake = original.encode('utf-8').decode('latin1')
        self.assertEqual(normalize_text(mojibake), original)


class TransactionServiceTests(BankingTestCase):
    @mock.patch('banking.services.time.sleep', return_value=None)
    def test_deposit_completes_and_updates_balance(self, mock_sleep):
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('150.00'),
            note='Зарплата',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        transaction = result.transaction
        self.assertTrue(result.completed)
        self.assertEqual(transaction.status, Transaction.Status.COMPLETED)
        self.assertEqual(self.account.balance, Decimal('650.00'))
        mock_sleep.assert_called_once()

    @mock.patch('banking.services.time.sleep', return_value=None)
    def test_withdrawal_cancelled_when_insufficient_funds(self, mock_sleep):
        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal('1000.00'),
            note='',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        transaction = result.transaction
        self.assertFalse(result.completed)
        self.assertEqual(transaction.status, Transaction.Status.CANCELLED)
        self.assertEqual(self.account.balance, Decimal('500.00'))
        self.assertEqual(transaction.note, 'Недостаточно средств.')
        self.assertEqual(result.message, 'Недостаточно средств.')
        mock_sleep.assert_called_once()

    @mock.patch('banking.services.time.sleep', return_value=None)
    def test_transaction_cancelled_when_account_blocked(self, mock_sleep):
        self.account.is_blocked = True
        self.account.save(update_fields=['is_blocked'])

        result = create_and_process_transaction(
            account=self.account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal('50.00'),
            note='Пополнение',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        transaction = result.transaction
        self.assertFalse(result.completed)
        self.assertEqual(transaction.status, Transaction.Status.CANCELLED)
        self.assertEqual(result.message, 'Счёт заблокирован.')
        mock_sleep.assert_not_called()

    @mock.patch('banking.services.time.sleep', return_value=None)
    def test_transfer_success_updates_both_accounts(self, mock_sleep):
        result = create_and_process_transfer(
            source_account=self.account,
            target_account=self.counterparty_account,
            amount=Decimal('120.00'),
            note='Оплата услуг',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        self.account.refresh_from_db()
        self.counterparty_account.refresh_from_db()
        outgoing = result.transaction
        incoming = outgoing.related_transaction

        self.assertTrue(result.completed)
        self.assertEqual(outgoing.status, Transaction.Status.COMPLETED)
        self.assertEqual(incoming.status, Transaction.Status.COMPLETED)
        self.assertEqual(self.account.balance, Decimal('380.00'))
        self.assertEqual(self.counterparty_account.balance, Decimal('320.00'))
        mock_sleep.assert_called_once()

    @mock.patch('banking.services.time.sleep', return_value=None)
    def test_transfer_cancelled_if_counterparty_blocked(self, mock_sleep):
        self.counterparty_account.is_blocked = True
        self.counterparty_account.save(update_fields=['is_blocked'])

        result = create_and_process_transfer(
            source_account=self.account,
            target_account=self.counterparty_account,
            amount=Decimal('50.00'),
            note='Подарок',
            performed_by=self.client_profile,
            processed_by=self.staff_user,
        )
        outgoing = result.transaction
        incoming = outgoing.related_transaction

        self.assertFalse(result.completed)
        self.assertEqual(outgoing.status, Transaction.Status.CANCELLED)
        self.assertEqual(incoming.status, Transaction.Status.CANCELLED)
        self.assertEqual(
            result.message,
            'Перевод недоступен — один из счетов заблокирован.',
        )
        mock_sleep.assert_not_called()


class TransactionFormsTests(BankingTestCase):
    def test_withdrawal_form_rejects_amount_above_balance(self):
        form = WithdrawalForm(
            data={'amount': '600.00', 'comment': ''},
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Недостаточно средств на счёте.', form.errors['amount'])

    def test_transfer_form_rejects_same_account(self):
        form = TransferForm(
            data={
                'target_account_number': self.account.account_number,
                'amount': '100.00',
                'comment': '',
            },
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Нельзя переводить на тот же счёт.',
            form.errors['target_account_number'],
        )

    def test_transfer_form_execute_returns_payload_with_normalized_note(self):
        mojibake_comment = self.make_mojibake('Привет, получатель')
        form = TransferForm(
            data={
                'target_account_number': (
                    self.counterparty_account.account_number
                ),
                'amount': '100.00',
                'comment': mojibake_comment,
            },
            account=self.account,
        )
        self.assertTrue(form.is_valid())
        payload = form.execute(self.client_profile)
        self.assertEqual(payload['note'], 'Привет, получатель')
        self.assertEqual(payload['source_account'], self.account)
        self.assertEqual(payload['target_account'], self.counterparty_account)

    def test_deposit_form_execute_returns_expected_payload(self):
        comment = self.make_mojibake('Зачисление')
        form = DepositForm(
            data={
                'amount': '250.00',
                'comment': comment,
            }
        )
        self.assertTrue(form.is_valid())
        payload = form.execute(self.account, self.client_profile)
        self.assertEqual(payload['note'], 'Зачисление')
        self.assertEqual(
            payload['transaction_type'],
            Transaction.TransactionType.DEPOSIT,
        )
        self.assertEqual(payload['amount'], Decimal('250.00'))
        self.assertEqual(payload['performed_by'], self.client_profile)
