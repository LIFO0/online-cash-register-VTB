from django.urls import path

from . import views

app_name = "banking"

urlpatterns = [
    path("", views.landing, name="landing"),
    path(
        "dashboard/",
        views.ClientDashboardView.as_view(),
        name="client_dashboard",
    ),
    path(
        "admin-dashboard/",
        views.AdminDashboardView.as_view(),
        name="admin_dashboard",
    ),
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),
    path(
        "transactions/<int:pk>/receipt/",
        views.TransactionReceiptView.as_view(),
        name="transaction_receipt",
    ),
    path(
        "admin-dashboard/accounts/<int:pk>/toggle-block/",
        views.admin_toggle_account_block,
        name="toggle_account_block",
    ),
    path(
        "admin-dashboard/transactions/<int:pk>/cancel/",
        views.admin_cancel_transaction,
        name="admin_cancel_transaction",
    ),
]
