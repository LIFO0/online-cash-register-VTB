from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Account, Transaction
from .utils import normalize_text

PROCESSING_DELAY_SECONDS = 2


@dataclass
class TransactionResult:
    transaction: Transaction
    completed: bool
    message: str


def create_and_process_transaction(
    *,
    account: Account,
    transaction_type: str,
    amount,
    note: str = "",
    performed_by=None,
    processed_by=None,
) -> TransactionResult:
    note = normalize_text(note)

    # Проверка лимита для операций снятия
    if transaction_type == Transaction.TransactionType.WITHDRAWAL:
        max_withdrawal = Decimal("100000")
        if amount > max_withdrawal:
            limit_message = (
                f"Превышен лимит снятия: максимум {max_withdrawal:,.2f} ₽"
            )
            # Создаём транзакцию, но сразу отменяем её
            with db_transaction.atomic():
                transaction = Transaction.objects.create(
                    account=account,
                    transaction_type=transaction_type,
                    amount=amount,
                    note=note or limit_message,
                    performed_by=performed_by,
                )
            transaction = cancel_transaction(
                transaction.id,
                cancelled_by=processed_by,
                reason=limit_message,
            )
            return TransactionResult(
                transaction=transaction,
                completed=False,
                message=limit_message,
            )

    with db_transaction.atomic():
        transaction = Transaction.objects.create(
            account=account,
            transaction_type=transaction_type,
            amount=amount,
            note=note,
            performed_by=performed_by,
        )

    if account.is_blocked or account.client.is_blocked:
        transaction = cancel_transaction(
            transaction.id,
            cancelled_by=processed_by,
            reason="Счёт заблокирован.",
        )
        return TransactionResult(
            transaction=transaction,
            completed=False,
            message="Счёт заблокирован.",
        )

    time.sleep(PROCESSING_DELAY_SECONDS)
    transaction = finalize_transaction(
        transaction.id, processed_by=processed_by
    )
    if transaction.is_completed:
        return TransactionResult(
            transaction=transaction,
            completed=True,
            message="Операция успешно выполнена.",
        )

    return TransactionResult(
        transaction=transaction,
        completed=False,
        message=transaction.note or "Операция отменена.",
    )


def create_and_process_transfer(
    *,
    source_account: Account,
    target_account: Account,
    amount,
    note: str = "",
    performed_by=None,
    processed_by=None,
) -> TransactionResult:
    normalized_note = normalize_text(note)

    # Проверка лимита для переводов
    max_transfer = Decimal("100000")
    if amount > max_transfer:
        limit_message = (
            f"Превышен лимит перевода: максимум {max_transfer:,.2f} ₽"
        )
        # Создаём транзакции, но сразу отменяем их
        with db_transaction.atomic():
            outgoing = Transaction.objects.create(
                account=source_account,
                transaction_type=Transaction.TransactionType.TRANSFER_OUT,
                amount=amount,
                note=normalized_note or limit_message,
                performed_by=performed_by,
                metadata={
                    "counterparty_account_number": (
                        target_account.account_number
                    )
                },
            )
            incoming = Transaction.objects.create(
                account=target_account,
                transaction_type=Transaction.TransactionType.TRANSFER_IN,
                amount=amount,
                note=normalized_note or limit_message,
                performed_by=performed_by,
                metadata={
                    "counterparty_account_number": (
                        source_account.account_number
                    )
                },
            )
            outgoing.related_transaction = incoming
            incoming.related_transaction = outgoing
            Transaction.objects.bulk_update(
                (outgoing, incoming),
                fields=["related_transaction"],
            )
        outgoing = cancel_transaction(
            outgoing.id, cancelled_by=processed_by, reason=limit_message
        )
        return TransactionResult(
            transaction=outgoing, completed=False, message=limit_message
        )

    with db_transaction.atomic():
        outgoing = Transaction.objects.create(
            account=source_account,
            transaction_type=Transaction.TransactionType.TRANSFER_OUT,
            amount=amount,
            note=(
                normalized_note
                or f"Перевод на счёт {target_account.account_number}"
            ),
            performed_by=performed_by,
            metadata={
                "counterparty_account_number": target_account.account_number
            },
        )
        incoming = Transaction.objects.create(
            account=target_account,
            transaction_type=Transaction.TransactionType.TRANSFER_IN,
            amount=amount,
            note=(
                normalized_note
                or f"Перевод от счёта {source_account.account_number}"
            ),
            performed_by=performed_by,
            metadata={
                "counterparty_account_number": source_account.account_number
            },
        )
        outgoing.related_transaction = incoming
        incoming.related_transaction = outgoing
        Transaction.objects.bulk_update(
            (outgoing, incoming),
            fields=["related_transaction"],
        )

    if (
        source_account.is_blocked
        or source_account.client.is_blocked
        or target_account.is_blocked
        or target_account.client.is_blocked
    ):
        outgoing = cancel_transaction(
            outgoing.id,
            cancelled_by=processed_by,
            reason="Один из счетов заблокирован.",
        )
        message = "Перевод недоступен — один из счетов заблокирован."
        return TransactionResult(
            transaction=outgoing, completed=False, message=message
        )

    time.sleep(PROCESSING_DELAY_SECONDS)
    outgoing, incoming = finalize_transfer(
        outgoing.id, incoming.id, processed_by=processed_by
    )
    if outgoing.is_completed and incoming.is_completed:
        message = (
            f"Перевод выполнен. Получатель: {target_account.account_number}"
        )
        return TransactionResult(
            transaction=outgoing, completed=True, message=message
        )

    return TransactionResult(
        transaction=outgoing,
        completed=False,
        message=outgoing.note or "Перевод отменён.",
    )


def finalize_transaction(
    transaction_id: int, *, processed_by=None
) -> Transaction:
    with db_transaction.atomic():
        transaction = (
            Transaction.objects.select_for_update()
            .select_related("account", "account__client")
            .get(id=transaction_id)
        )
        if not transaction.is_pending:
            return transaction

        account = transaction.account
        if account.is_blocked or account.client.is_blocked:
            transaction.status = Transaction.Status.CANCELLED
            transaction.note = transaction.note or "Счёт заблокирован."
        else:
            if transaction.transaction_type in (
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.TRANSFER_IN,
            ):
                account.balance += transaction.amount
            elif transaction.transaction_type in (
                Transaction.TransactionType.WITHDRAWAL,
                Transaction.TransactionType.TRANSFER_OUT,
            ):
                if transaction.amount > account.balance:
                    transaction.status = Transaction.Status.CANCELLED
                    transaction.note = (
                        transaction.note or "Недостаточно средств."
                    )
                else:
                    account.balance -= transaction.amount
            else:
                transaction.status = Transaction.Status.CANCELLED
                transaction.note = (
                    transaction.note or "Неизвестный тип операции."
                )

            if transaction.status != Transaction.Status.CANCELLED:
                account.save(update_fields=["balance"])
                transaction.status = Transaction.Status.COMPLETED

        transaction.processed_at = timezone.now()
        transaction.processed_by = processed_by
        transaction.save(
            update_fields=["status", "processed_at", "processed_by", "note"]
        )
        return transaction


def finalize_transfer(
    outgoing_id: int, incoming_id: int, *, processed_by=None
) -> tuple[Transaction, Transaction]:
    with db_transaction.atomic():
        outgoing = (
            Transaction.objects.select_for_update()
            .select_related("account", "account__client")
            .get(id=outgoing_id)
        )
        incoming = (
            Transaction.objects.select_for_update()
            .select_related("account", "account__client")
            .get(id=incoming_id)
        )

        if not outgoing.is_pending and not incoming.is_pending:
            return outgoing, incoming

        now = timezone.now()
        if (
            outgoing.account.is_blocked
            or outgoing.account.client.is_blocked
            or incoming.account.is_blocked
            or incoming.account.client.is_blocked
        ):
            outgoing.status = Transaction.Status.CANCELLED
            incoming.status = Transaction.Status.CANCELLED
            outgoing.note = outgoing.note or "Счёт отправителя заблокирован."
            incoming.note = incoming.note or "Счёт получателя заблокирован."
        elif outgoing.amount > outgoing.account.balance:
            outgoing.status = Transaction.Status.CANCELLED
            incoming.status = Transaction.Status.CANCELLED
            msg = "Недостаточно средств для перевода."
            outgoing.note = outgoing.note or msg
            incoming.note = incoming.note or msg
        else:
            outgoing.account.balance -= outgoing.amount
            incoming.account.balance += incoming.amount
            outgoing.account.save(update_fields=["balance"])
            incoming.account.save(update_fields=["balance"])
            outgoing.status = Transaction.Status.COMPLETED
            incoming.status = Transaction.Status.COMPLETED

        outgoing.processed_at = now
        incoming.processed_at = now
        outgoing.processed_by = processed_by
        incoming.processed_by = processed_by
        outgoing.save(
            update_fields=["status", "processed_at", "processed_by", "note"]
        )
        incoming.save(
            update_fields=["status", "processed_at", "processed_by", "note"]
        )
        return outgoing, incoming


def cancel_transaction(
    transaction_id: int, *, cancelled_by=None, reason: str = ""
) -> Transaction:
    with db_transaction.atomic():
        transaction = (
            Transaction.objects.select_for_update()
            .select_related(
                "account",
                "related_transaction",
                "related_transaction__account",
            )
            .get(id=transaction_id)
        )
        if transaction.is_cancelled:
            return transaction

        account = transaction.account
        if transaction.is_completed:
            if transaction.transaction_type in (
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.TRANSFER_IN,
            ):
                account.balance -= transaction.amount
            elif transaction.transaction_type in (
                Transaction.TransactionType.WITHDRAWAL,
                Transaction.TransactionType.TRANSFER_OUT,
            ):
                account.balance += transaction.amount
            account.save(update_fields=["balance"])

        transaction.status = Transaction.Status.CANCELLED
        transaction.processed_at = timezone.now()
        transaction.cancelled_by = cancelled_by
        note_parts = [
            transaction.note or "",
            reason or "Отменено администратором.",
        ]
        transaction.note = normalize_text(
            " ".join(part for part in note_parts if part).strip()
        )
        transaction.save(
            update_fields=["status", "processed_at", "cancelled_by", "note"]
        )

        mirror = transaction.related_transaction
        if mirror and not mirror.is_cancelled:
            mirror_account = mirror.account
            if mirror.is_completed:
                if mirror.transaction_type in (
                    Transaction.TransactionType.DEPOSIT,
                    Transaction.TransactionType.TRANSFER_IN,
                ):
                    mirror_account.balance -= mirror.amount
                elif mirror.transaction_type in (
                    Transaction.TransactionType.WITHDRAWAL,
                    Transaction.TransactionType.TRANSFER_OUT,
                ):
                    mirror_account.balance += mirror.amount
                mirror_account.save(update_fields=["balance"])

            mirror.status = Transaction.Status.CANCELLED
            mirror.processed_at = timezone.now()
            mirror.cancelled_by = cancelled_by
            mirror_note_parts = [
                mirror.note or "",
                "Связанная операция отменена.",
            ]
            if reason:
                mirror_note_parts.append(reason)
            mirror.note = normalize_text(
                " ".join(part for part in mirror_note_parts if part).strip()
            )
            mirror.save(
                update_fields=[
                    "status",
                    "processed_at",
                    "cancelled_by",
                    "note",
                ]
            )
        return transaction


def toggle_account_block(account: Account, *, blocked: bool) -> Account:
    account.is_blocked = blocked
    account.save(update_fields=["is_blocked"])

    client = account.client
    has_blocked_accounts = client.accounts.filter(is_blocked=True).exists()
    if client.is_blocked != has_blocked_accounts:
        client.is_blocked = has_blocked_accounts
        client.save(update_fields=["is_blocked"])

    return account
