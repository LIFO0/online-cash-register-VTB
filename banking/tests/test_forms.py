"""
Расширенные тесты для форм приложения banking.

Проверяют валидацию форм, граничные случаи и обработку ошибок.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from banking.forms import (
    AmountField,
    ClientFilterForm,
    DepositForm,
    TransactionFilterForm,
    TransferForm,
    WithdrawalForm,
)
from banking.models import Account, ClientProfile, Transaction


User = get_user_model()


class AmountFieldTests(TestCase):
    """Тесты для поля AmountField."""

    def test_default_min_value(self):
        """Проверка минимального значения по умолчанию."""
        field = AmountField()
        self.assertEqual(field.min_value, Decimal('10'))

    def test_default_max_value(self):
        """Проверка максимального значения по умолчанию."""
        field = AmountField()
        self.assertEqual(field.max_value, Decimal('100000'))

    def test_default_decimal_places(self):
        """Проверка количества знаков после запятой."""
        field = AmountField()
        self.assertEqual(field.decimal_places, 2)

    def test_custom_min_max_values(self):
        """Проверка кастомных минимального и максимального значений."""
        field = AmountField(
            min_value=Decimal('50'),
            max_value=Decimal('500')
        )
        self.assertEqual(field.min_value, Decimal('50'))
        self.assertEqual(field.max_value, Decimal('500'))


class DepositFormTests(TestCase):
    """Тесты для формы пополнения."""

    def test_valid_deposit_form(self):
        """Проверка валидной формы пополнения."""
        form = DepositForm(data={
            'amount': '1000.00',
            'comment': 'Зарплата',
        })
        self.assertTrue(form.is_valid())

    def test_deposit_form_with_empty_comment(self):
        """Проверка формы с пустым комментарием."""
        form = DepositForm(data={
            'amount': '500.00',
            'comment': '',
        })
        self.assertTrue(form.is_valid())

    def test_deposit_form_minimum_amount(self):
        """Проверка минимальной суммы пополнения."""
        form = DepositForm(data={
            'amount': '10.00',
            'comment': '',
        })
        self.assertTrue(form.is_valid())

    def test_deposit_form_below_minimum(self):
        """Проверка суммы ниже минимальной."""
        form = DepositForm(data={
            'amount': '9.99',
            'comment': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_deposit_form_maximum_amount(self):
        """Проверка максимальной суммы пополнения."""
        form = DepositForm(data={
            'amount': '100000.00',
            'comment': '',
        })
        self.assertTrue(form.is_valid())

    def test_deposit_form_above_maximum(self):
        """Проверка суммы выше максимальной."""
        form = DepositForm(data={
            'amount': '100001.00',
            'comment': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_deposit_form_execute_returns_correct_payload(self):
        """Проверка execute метода формы."""
        form = DepositForm(data={
            'amount': '250.00',
            'comment': 'Тестовое пополнение',
        })
        self.assertTrue(form.is_valid())

        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        profile = ClientProfile.objects.create(
            user=user,
            full_name='Тестовый Клиент',
        )
        account = Account.objects.create(
            client=profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

        payload = form.execute(account, profile)
        self.assertEqual(payload['account'], account)
        self.assertEqual(
            payload['transaction_type'],
            Transaction.TransactionType.DEPOSIT
        )
        self.assertEqual(payload['amount'], Decimal('250.00'))
        self.assertEqual(payload['note'], 'Тестовое пополнение')
        self.assertEqual(payload['performed_by'], profile)

    def test_deposit_form_normalizes_comment(self):
        """Проверка нормализации комментария."""
        mojibake = 'Привет'.encode('utf-8').decode('latin1')
        form = DepositForm(data={
            'amount': '100.00',
            'comment': mojibake,
        })
        self.assertTrue(form.is_valid())

        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        profile = ClientProfile.objects.create(
            user=user,
            full_name='Тестовый Клиент',
        )
        account = Account.objects.create(
            client=profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

        payload = form.execute(account, profile)
        self.assertEqual(payload['note'], 'Привет')


class WithdrawalFormTests(TestCase):
    """Тесты для формы снятия."""

    @classmethod
    def setUpTestData(cls):
        """Создание тестовых данных."""
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        cls.profile = ClientProfile.objects.create(
            user=cls.user,
            full_name='Тестовый Клиент',
        )
        cls.account = Account.objects.create(
            client=cls.profile,
            account_number='40817810000000000001',
            balance=Decimal('1000.00'),
        )

    def test_valid_withdrawal_form(self):
        """Проверка валидной формы снятия."""
        form = WithdrawalForm(
            data={
                'amount': '500.00',
                'comment': 'Личные расходы',
            },
            account=self.account,
        )
        self.assertTrue(form.is_valid())

    def test_withdrawal_form_rejects_amount_above_balance(self):
        """Проверка отклонения суммы выше баланса."""
        form = WithdrawalForm(
            data={
                'amount': '1500.00',
                'comment': '',
            },
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Недостаточно средств', form.errors['amount'][0])

    def test_withdrawal_form_allows_exact_balance(self):
        """Проверка разрешения снятия точной суммы баланса."""
        form = WithdrawalForm(
            data={
                'amount': '1000.00',
                'comment': '',
            },
            account=self.account,
        )
        self.assertTrue(form.is_valid())

    def test_withdrawal_form_rejects_above_limit(self):
        """Проверка отклонения суммы выше лимита."""
        form = WithdrawalForm(
            data={
                'amount': '100001.00',
                'comment': '',
            },
            account=self.account,
        )
        self.assertFalse(form.is_valid())
        error_msg = form.errors['amount'][0].lower()
        self.assertTrue(
            '100000' in error_msg or 'максимум' in error_msg
        )

    def test_withdrawal_form_execute_returns_correct_payload(self):
        """Проверка execute метода формы."""
        form = WithdrawalForm(
            data={
                'amount': '300.00',
                'comment': 'Покупка',
            },
            account=self.account,
        )
        self.assertTrue(form.is_valid())

        payload = form.execute(self.profile)
        self.assertEqual(payload['account'], self.account)
        self.assertEqual(
            payload['transaction_type'],
            Transaction.TransactionType.WITHDRAWAL
        )
        self.assertEqual(payload['amount'], Decimal('300.00'))
        self.assertEqual(payload['note'], 'Покупка')
        self.assertEqual(payload['performed_by'], self.profile)


class TransferFormTests(TestCase):
    """Тесты для формы перевода."""

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
            balance=Decimal('5000.00'),
        )
        cls.receiver_account = Account.objects.create(
            client=cls.receiver_profile,
            account_number='40817810000000000002',
            balance=Decimal('1000.00'),
        )

    def test_valid_transfer_form(self):
        """Проверка валидной формы перевода."""
        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '500.00',
                'comment': 'Перевод другу',
            },
            account=self.sender_account,
        )
        self.assertTrue(form.is_valid())

    def test_transfer_form_rejects_nonexistent_account(self):
        """Проверка отклонения несуществующего счета."""
        form = TransferForm(
            data={
                'target_account_number': '99999999999999999999',
                'amount': '100.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'не найден',
            form.errors['target_account_number'][0]
        )

    def test_transfer_form_rejects_same_account(self):
        """Проверка отклонения перевода на тот же счет."""
        form = TransferForm(
            data={
                'target_account_number': (
                    self.sender_account.account_number
                ),
                'amount': '100.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'тот же счёт',
            form.errors['target_account_number'][0]
        )

    def test_transfer_form_rejects_blocked_target_account(self):
        """Проверка отклонения заблокированного счета получателя."""
        self.receiver_account.is_blocked = True
        self.receiver_account.save()

        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '100.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'заблокирован',
            form.errors['target_account_number'][0]
        )

    def test_transfer_form_rejects_blocked_target_client(self):
        """Проверка отклонения при заблокированном клиенте."""
        self.receiver_profile.is_blocked = True
        self.receiver_profile.save()

        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '100.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'заблокирован',
            form.errors['target_account_number'][0]
        )

    def test_transfer_form_rejects_amount_above_balance(self):
        """Проверка отклонения суммы выше баланса."""
        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '6000.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Недостаточно средств', form.errors['amount'][0])

    def test_transfer_form_rejects_above_limit(self):
        """Проверка отклонения суммы выше лимита."""
        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '100001.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertFalse(form.is_valid())
        error_msg = form.errors['amount'][0].lower()
        self.assertTrue(
            '100000' in error_msg or 'максимум' in error_msg
        )

    def test_transfer_form_execute_returns_correct_payload(self):
        """Проверка execute метода формы."""
        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '750.00',
                'comment': 'Оплата услуг',
            },
            account=self.sender_account,
        )
        self.assertTrue(form.is_valid())

        payload = form.execute(self.sender_profile)
        self.assertEqual(payload['source_account'], self.sender_account)
        self.assertEqual(
            payload['target_account'],
            self.receiver_account
        )
        self.assertEqual(payload['amount'], Decimal('750.00'))
        self.assertEqual(payload['note'], 'Оплата услуг')
        self.assertEqual(payload['performed_by'], self.sender_profile)

    def test_transfer_form_normalizes_comment(self):
        """Проверка нормализации комментария."""
        mojibake = 'Привет'.encode('utf-8').decode('latin1')
        form = TransferForm(
            data={
                'target_account_number': (
                    self.receiver_account.account_number
                ),
                'amount': '100.00',
                'comment': mojibake,
            },
            account=self.sender_account,
        )
        self.assertTrue(form.is_valid())

        payload = form.execute(self.sender_profile)
        self.assertEqual(payload['note'], 'Привет')

    def test_transfer_form_strips_account_number(self):
        """Проверка обрезки пробелов в номере счета."""
        form = TransferForm(
            data={
                'target_account_number': (
                    '  ' + self.receiver_account.account_number + '  '
                ),
                'amount': '100.00',
                'comment': '',
            },
            account=self.sender_account,
        )
        self.assertTrue(form.is_valid())


class TransactionFilterFormTests(TestCase):
    """Тесты для формы фильтрации транзакций."""

    def test_empty_form_is_valid(self):
        """Проверка валидности пустой формы."""
        form = TransactionFilterForm(data={})
        self.assertTrue(form.is_valid())

    def test_form_with_date_from(self):
        """Проверка формы с датой начала."""
        form = TransactionFilterForm(data={
            'date_from': '2025-01-01',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['date_from'].strftime('%Y-%m-%d'),
            '2025-01-01'
        )

    def test_form_with_date_to(self):
        """Проверка формы с датой окончания."""
        form = TransactionFilterForm(data={
            'date_to': '2025-12-31',
        })
        self.assertTrue(form.is_valid())

    def test_form_with_transaction_type(self):
        """Проверка формы с типом транзакции."""
        form = TransactionFilterForm(data={
            'transaction_type': Transaction.TransactionType.DEPOSIT,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['transaction_type'],
            Transaction.TransactionType.DEPOSIT
        )

    def test_form_with_status(self):
        """Проверка формы со статусом."""
        form = TransactionFilterForm(data={
            'status': Transaction.Status.COMPLETED,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data['status'],
            Transaction.Status.COMPLETED
        )

    def test_form_with_client(self):
        """Проверка формы с клиентом."""
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )
        profile = ClientProfile.objects.create(
            user=user,
            full_name='Тестовый Клиент',
        )

        form = TransactionFilterForm(data={
            'client': profile.id,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['client'], profile)


class ClientFilterFormTests(TestCase):
    """Тесты для формы фильтрации клиентов."""

    def test_empty_form_is_valid(self):
        """Проверка валидности пустой формы."""
        form = ClientFilterForm(data={})
        self.assertTrue(form.is_valid())

    def test_form_with_search(self):
        """Проверка формы с поисковым запросом."""
        form = ClientFilterForm(data={
            'search': 'Иван',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['search'], 'Иван')

    def test_form_with_is_blocked_true(self):
        """Проверка формы с фильтром заблокированных."""
        form = ClientFilterForm(data={
            'is_blocked': 'true',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['is_blocked'], 'true')

    def test_form_with_is_blocked_false(self):
        """Проверка формы с фильтром активных."""
        form = ClientFilterForm(data={
            'is_blocked': 'false',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['is_blocked'], 'false')

    def test_form_with_all_filters(self):
        """Проверка формы со всеми фильтрами."""
        form = ClientFilterForm(data={
            'search': 'Петр',
            'is_blocked': 'false',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['search'], 'Петр')
        self.assertEqual(form.cleaned_data['is_blocked'], 'false')
