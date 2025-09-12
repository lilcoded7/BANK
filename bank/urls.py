from django.urls import path
from . import views

urlpatterns = [
   
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("", views.dashboard, name="dashboard"),


    path("transfer/", views.transfer_funds, name="transfer_funds"),
    path("transfer/bank/", views.bank_transfer, name="bank_transfer"),
    path("transfer/mobile-money/", views.mobile_money, name="mobile_money"),
    path("transfer/bill-payment/", views.bill_payment, name="bill_payment"),


    path("security/settings/", views.security_settings, name="security_settings"),

    path("verify-account/", views.verify_account, name="verify_account"),
]
