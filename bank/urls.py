from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("accounts/login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.customer_profile, name="customer_profile"),
    path("security/", views.security_settings, name="security_settings"),
    path("transfer/", views.transfer_funds, name="transfer_funds"),
    path("transfer/bank/", views.bank_transfer, name="bank_transfer"),
    path("transfer/mobile-money/", views.mobile_money, name="mobile_money"),
    path("transfer/deposit/", views.deposit, name="deposit"),
    path("transfer/withdrawal/", views.withdrawal, name="withdrawal"),
    path("transfer/bill-payment/", views.bill_payment, name="bill_payment"),
    path('verify/transaction', views.verify_transaction, name='verifying_payment'),
    path('toggle_2fa', views.toggle_2fa, name='toggle_2fa'),

    path('get_user_email_address/', views.get_user_email_address, name='get_user_email_address'),
    path("chat/", views.chat_page, name="chat_page"),
    path("chat/send/", views.send_message, name="send_message"),
    path("chat/messages/", views.get_messages, name="get_messages"),
    path("chat/reply/<int:user_id>/", views.support_reply, name="support_reply"),

    path('support/dashboard/', views.support_dashboard, name='support_dashboard'),
    path('transactions/dashboard/', views.transactions_dashboard, name='transactions_dashboard'),

    path("support/chat/", views.support_chat_dashboard, name="support_chat_dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("support/chat/<int:customer_id>/", views.support_chat_dashboard, name="support_chat_dashboard"),
    path('two/factor/auth/<int:user_id>', views.two_factor_auth, name='two_factor_auth'),
    path('reset_password/', views.reset_password, name='reset_password')

]
