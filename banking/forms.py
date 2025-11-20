from decimal import Decimal

from django import forms

from .models import Account, ClientProfile, Transaction
from .utils import normalize_text


class AmountField(forms.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("min_value", Decimal("10"))
        kwargs.setdefault("max_value", Decimal("100000"))
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("label", "Сумма, ₽")
        widget = kwargs.pop(
            "widget",
            forms.NumberInput(
                attrs={
                    "class": "input-field",
                }
            ),
        )
        super().__init__(*args, widget=widget, **kwargs)


class DepositForm(forms.Form):
    amount = AmountField()
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Например: Заработная плата",
                "class": "input-field",
            }
        ),
    )

    def execute(
        self, account: Account, performer: ClientProfile | None
    ) -> dict:
        amount = self.cleaned_data["amount"]
        comment = normalize_text(self.cleaned_data.get("comment", ""))
        return {
            "account": account,
            "transaction_type": Transaction.TransactionType.DEPOSIT,
            "amount": amount,
            "note": comment,
            "performed_by": performer,
        }


class WithdrawalForm(forms.Form):
    amount = AmountField()
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Например: Личные расходы",
                "class": "input-field",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.account: Account = kwargs.pop("account")
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount: Decimal = self.cleaned_data["amount"]
        max_withdrawal = Decimal("100000")
        if amount > max_withdrawal:
            raise forms.ValidationError(
                f"Максимальная сумма снятия: {max_withdrawal:,.2f} ₽"
            )
        if amount > self.account.balance:
            raise forms.ValidationError("Недостаточно средств на счёте.")
        return amount

    def execute(self, performer: ClientProfile | None) -> dict:
        amount = self.cleaned_data["amount"]
        comment = normalize_text(self.cleaned_data.get("comment", ""))
        return {
            "account": self.account,
            "transaction_type": Transaction.TransactionType.WITHDRAWAL,
            "amount": amount,
            "note": comment,
            "performed_by": performer,
        }


class TransferForm(forms.Form):
    target_account_number = forms.CharField(
        label="Счёт получателя",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Например: 40817810000000000002",
                "class": "input-field",
            }
        ),
    )
    amount = AmountField()
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Например: Перевод другу",
                "class": "input-field",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.account: Account = kwargs.pop("account")
        super().__init__(*args, **kwargs)
        self.target_account: Account | None = None

    def clean_target_account_number(self):
        number = self.cleaned_data["target_account_number"].strip()
        try:
            target = Account.objects.get(account_number=number)
        except Account.DoesNotExist as exc:
            raise forms.ValidationError("Счёт получателя не найден.") from exc
        if target == self.account:
            raise forms.ValidationError("Нельзя переводить на тот же счёт.")
        if target.is_blocked:
            raise forms.ValidationError("Счёт получателя заблокирован.")
        if target.client.is_blocked:
            raise forms.ValidationError("Клиент-получатель заблокирован.")
        self.target_account = target
        return number

    def clean_amount(self):
        amount: Decimal = self.cleaned_data["amount"]
        max_transfer = Decimal("100000")
        if amount > max_transfer:
            raise forms.ValidationError(
                f"Максимальная сумма перевода: {max_transfer:,.2f} ₽"
            )
        if amount > self.account.balance:
            raise forms.ValidationError(
                "Недостаточно средств на счёте для перевода."
            )
        return amount

    def execute(self, performer: ClientProfile | None) -> dict:
        if not self.target_account:
            raise forms.ValidationError("Не выбран счёт получателя.")
        amount = self.cleaned_data["amount"]
        comment = normalize_text(self.cleaned_data.get("comment", ""))
        return {
            "source_account": self.account,
            "target_account": self.target_account,
            "amount": amount,
            "note": comment,
            "performed_by": performer,
        }


class TransactionFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        label="Дата с",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="Дата по",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    transaction_type = forms.ChoiceField(
        required=False,
        label="Тип операции",
        choices=[("", "Все")] + list(Transaction.TransactionType.choices),
    )
    status = forms.ChoiceField(
        required=False,
        label="Статус",
        choices=[("", "Все")] + list(Transaction.Status.choices),
    )
    client = forms.ModelChoiceField(
        required=False,
        label="Клиент",
        queryset=ClientProfile.objects.all(),
    )


class ClientFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        label="Поиск",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Имя, ID, логин или номер счёта",
                "class": "input-field",
            }
        ),
    )
    is_blocked = forms.ChoiceField(
        required=False,
        label="Статус",
        choices=[
            ("", "Все"),
            ("false", "Активные"),
            ("true", "Заблокированные"),
        ],
        widget=forms.Select(attrs={"class": "input-field"}),
    )
