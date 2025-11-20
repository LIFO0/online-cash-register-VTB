from django.contrib import admin

from .models import Account, ClientProfile, Transaction


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "is_blocked")
    search_fields = ("full_name", "user__username")
    list_filter = ("is_blocked",)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "account_number",
        "client",
        "balance",
        "is_blocked",
        "created_at",
    )
    search_fields = ("account_number", "client__full_name")
    list_filter = ("is_blocked",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "account",
        "transaction_type",
        "amount",
        "status",
        "created_at",
        "processed_at",
        "performed_by",
        "counterparty_display",
    )
    search_fields = (
        "reference",
        "account__account_number",
        "performed_by__full_name",
    )
    list_filter = ("transaction_type", "status", "created_at")
    list_select_related = (
        "account",
        "account__client",
        "performed_by",
        "related_transaction",
        "related_transaction__account",
    )

    @admin.display(description="Счет получателя")
    def counterparty_display(self, obj: Transaction) -> str:
        counterparty = obj.counterparty_account
        return counterparty.account_number if counterparty else "—"
