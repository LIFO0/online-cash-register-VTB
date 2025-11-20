from functools import wraps

from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, TemplateView

from .forms import (
    ClientFilterForm,
    DepositForm,
    TransactionFilterForm,
    TransferForm,
    WithdrawalForm,
)
from .models import Account, ClientProfile, Transaction
from .services import (
    TransactionResult,
    cancel_transaction,
    create_and_process_transaction,
    create_and_process_transfer,
    toggle_account_block,
)

SECURITY_MESSAGE = _(
    "Вы вошли в защищённую зону. Никому не сообщайте свой пароль."
)


def landing(request):
    if request.user.is_authenticated:
        return redirect("banking:post_login_redirect")
    return redirect("login")


def _ensure_client_profile(user):
    try:
        return user.client_profile
    except ClientProfile.DoesNotExist:
        return None


@login_required
def post_login_redirect(request):
    messages.info(request, SECURITY_MESSAGE)
    if request.user.is_staff:
        return redirect("banking:admin_dashboard")
    return redirect("banking:client_dashboard")


class ClientDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "banking/client_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_staff:
            return redirect("banking:admin_dashboard")
        self.client_profile = _ensure_client_profile(request.user)
        if not self.client_profile:
            messages.error(
                request, "Для пользователя не настроен клиентский профиль."
            )
            return redirect("logout")
        self.account = self.client_profile.accounts.first()
        if not self.account:
            messages.error(request, "Для клиента не создан счёт.")
            return redirect("logout")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["client"] = self.client_profile
        context["account"] = self.account
        context["deposit_form"] = kwargs.get("deposit_form") or DepositForm()
        context["withdrawal_form"] = kwargs.get(
            "withdrawal_form"
        ) or WithdrawalForm(account=self.account)
        context["transfer_form"] = kwargs.get("transfer_form") or TransferForm(
            account=self.account
        )
        transactions_queryset = self.account.transactions.select_related(
            "performed_by",
            "related_transaction",
            "related_transaction__account",
        ).order_by("-created_at")
        context["total_transactions_count"] = transactions_queryset.count()
        context["transactions"] = transactions_queryset[:10]
        context["security_message"] = SECURITY_MESSAGE
        return context

    def post(self, request, *args, **kwargs):
        form_type = request.POST.get("form_type")
        if form_type == "deposit":
            form = DepositForm(request.POST)
            if form.is_valid():
                return self._process_client_transaction(
                    form.execute(self.account, self.client_profile)
                )
            return self.render_to_response(
                self.get_context_data(deposit_form=form)
            )

        if form_type == "withdrawal":
            form = WithdrawalForm(request.POST, account=self.account)
            if form.is_valid():
                return self._process_client_transaction(
                    form.execute(self.client_profile)
                )
            return self.render_to_response(
                self.get_context_data(withdrawal_form=form)
            )

        if form_type == "transfer":
            form = TransferForm(request.POST, account=self.account)
            if form.is_valid():
                return self._process_transfer(
                    form.execute(self.client_profile)
                )
            return self.render_to_response(
                self.get_context_data(transfer_form=form)
            )

        messages.error(request, "Неизвестный тип операции.")
        return redirect("banking:client_dashboard")

    def _process_client_transaction(self, payload: dict):
        result: TransactionResult = create_and_process_transaction(**payload)
        if result.completed:
            message = (
                f"Операция {result.transaction.reference} завершена. "
                f"Текущий баланс: {result.transaction.account.balance:.2f} ₽"
            )
            messages.success(
                self.request,
                message,
            )
        else:
            messages.error(self.request, result.message)
        return redirect(
            "banking:transaction_receipt", pk=result.transaction.pk
        )

    def _process_transfer(self, payload: dict):
        result: TransactionResult = create_and_process_transfer(**payload)
        counterparty = (
            payload["target_account"].account_number
            if "target_account" in payload
            else ""
        )
        if result.completed:
            message = (
                f"Перевод {result.transaction.reference} завершён. "
                f"Получатель: {counterparty}. "
                f"Баланс: {result.transaction.account.balance:.2f} ₽"
            )
            messages.success(
                self.request,
                message,
            )
        else:
            messages.error(self.request, result.message)
        return redirect(
            "banking:transaction_receipt", pk=result.transaction.pk
        )


class TransactionReceiptView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = "banking/transaction_receipt.html"
    context_object_name = "transaction"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related(
                "account__client",
                "performed_by",
                "related_transaction",
                "related_transaction__account",
            )
        )
        if self.request.user.is_staff:
            return qs
        client = _ensure_client_profile(self.request.user)
        if not client:
            return qs.none()
        return qs.filter(account__client=client)


class AdminDashboardView(
    LoginRequiredMixin, UserPassesTestMixin, TemplateView
):
    template_name = "banking/admin/dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.warning(
                self.request,
                "Доступ к админ-панели разрешён только сотрудникам банка.",
            )
            return redirect("banking:client_dashboard")
        login_url = f"{reverse('login')}?next={self.request.path}"
        return redirect(login_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clients = ClientProfile.objects.select_related(
            "user"
        ).prefetch_related("accounts")
        accounts = Account.objects.select_related("client")
        transactions = Transaction.objects.select_related(
            "account__client",
            "performed_by",
            "related_transaction",
            "related_transaction__account",
        ).all()

        client_filter_form = ClientFilterForm(self.request.GET or None)
        if client_filter_form.is_valid():
            data = client_filter_form.cleaned_data
            search = data.get("search", "").strip()
            if search:
                search_filters = (
                    Q(full_name__icontains=search)
                    | Q(user__username__icontains=search)
                    | Q(accounts__account_number__icontains=search)
                )
                try:
                    search_id = int(search)
                    search_filters |= Q(id=search_id)
                except ValueError:
                    pass
                clients = clients.filter(search_filters).distinct()

            is_blocked = data.get("is_blocked")
            if is_blocked == "true":
                clients = clients.filter(is_blocked=True)
            elif is_blocked == "false":
                clients = clients.filter(is_blocked=False)

        clients = clients.order_by("id")
        paginator = Paginator(clients, 12)
        page_number = self.request.GET.get("client_page", 1)
        clients_page = paginator.get_page(page_number)

        filter_form = TransactionFilterForm(self.request.GET or None)
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("date_from"):
                transactions = transactions.filter(
                    created_at__date__gte=data["date_from"]
                )
            if data.get("date_to"):
                transactions = transactions.filter(
                    created_at__date__lte=data["date_to"]
                )
            if data.get("transaction_type"):
                transactions = transactions.filter(
                    transaction_type=data["transaction_type"]
                )
            if data.get("status"):
                transactions = transactions.filter(status=data["status"])
            if data.get("client"):
                transactions = transactions.filter(
                    account__client=data["client"]
                )

        total_balance = sum(account.balance for account in accounts)
        total_clients_count = ClientProfile.objects.count()
        total_transactions_count = transactions.count()
        context["clients"] = clients_page
        context["client_filter_form"] = client_filter_form
        context["accounts"] = accounts
        context["transactions"] = transactions.order_by("-created_at")[:25]
        context["filter_form"] = filter_form
        context["total_balance"] = total_balance
        context["total_clients_count"] = total_clients_count
        context["total_transactions_count"] = total_transactions_count
        return context


def staff_required(function):
    @wraps(function)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = f"{reverse('login')}?next={request.path}"
            return redirect(login_url)
        if not request.user.is_staff:
            messages.warning(
                request, "Эта операция доступна только сотрудникам банка."
            )
            return redirect("banking:client_dashboard")
        return function(request, *args, **kwargs)

    return wrapper


@staff_required
def admin_toggle_account_block(request, pk):
    if request.method != "POST":
        return redirect("banking:admin_dashboard")
    account = get_object_or_404(Account, pk=pk)
    new_state = not account.is_blocked
    toggle_account_block(account, blocked=new_state)
    if new_state:
        messages.warning(
            request,
            f"Счёт {account.account_number} заблокирован.",
        )
    else:
        messages.success(
            request,
            f"Счёт {account.account_number} разблокирован.",
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        state_text = "заблокирован" if new_state else "разблокирован"
        return JsonResponse(
            {
                "success": True,
                "section": "clients",
                "message": (
                    f"Счёт {account.account_number} {state_text}."
                ),
            }
        )

    return redirect("banking:admin_dashboard")


@staff_required
def admin_cancel_transaction(request, pk):
    if request.method != "POST":
        return redirect("banking:admin_dashboard")
    transaction = get_object_or_404(Transaction, pk=pk)
    cancel_transaction(
        transaction.id,
        cancelled_by=request.user,
        reason="Отмена администратором.",
    )
    messages.info(
        request,
        f"Транзакция {transaction.reference} помечена как отменённая.",
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "section": "transactions",
                "message": (
                    f"Транзакция {transaction.reference} "
                    f"помечена как отменённая."
                ),
            }
        )

    return redirect("banking:admin_dashboard")
