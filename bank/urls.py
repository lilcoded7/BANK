from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Trading and Investment URLs
    path('', views.trade_investment_dashboard, name='trade_investment_dashboard'),
    path('open_trade/', views.open_trade, name='open_trade'),
    path('close_trade/<int:position_id>/', views.close_trade, name='close_trade'),
    path('create_investment/', views.create_investment, name='create_investment'),
    path('market_data/<str:symbol>/', views.get_market_data, name='get_market_data'),

    # Financial Transaction URLs
    path('deposit/page/', views.deposit_page, name='deposit_page'),
    path('deposit_funds/', views.deposit_funds, name='deposit_funds'),
    path('withdraw/cash/', views.withdraw_fund, name='withdraw_fund'),

    # Support Ticket URLs
    path('support/', views.support_page, name='support_page'),
    path('support/tickets/create/', views.create_ticket, name='create_ticket'),
    path('support/tickets/<int:ticket_id>/close/', views.close_ticket, name='close_ticket'),
    path('support/tickets/<int:ticket_id>/send/', views.send_message, name='send_message'),
    path('support/tickets/<int:ticket_id>/messages/', views.get_new_messages, name='get_new_messages'),

    # General Support Chat URLs
    path('support/send/general/message/', views.send_general_message, name='send_general_message'),
    path('support/get/new/general/messages/', views.get_new_general_messages, name='get_new_general_messages'),


    # Admin Dashboard URLs
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('chat/history/<int:user_id>/', views.get_chat_history, name='get_chat_history'),
    path('transaction/<int:transaction_id>/<str:action>/', views.process_transaction, name='process_transaction'),

]