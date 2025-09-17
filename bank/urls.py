from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.customer_profile, name="customer_profile"),
    path("security/", views.security_settings, name="security_settings"),
    path("transfer/", views.transfer_funds, name="transfer_funds"),
    path("transfer/bank/", views.bank_transfer, name="bank_transfer"),
    path("transfer/mobile-money/", views.mobile_money, name="mobile_money"),
    path("transfer/deposit/", views.deposit, name="deposit"),
    path("transfer/withdrawal/", views.withdrawal, name="withdrawal"),
    path("transfer/bill-payment/", views.bill_payment, name="bill_payment"),
    path('veryfy/transaction', views.verify_transaction, name='verifying_payment')
]
