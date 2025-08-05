from django.urls import path
from . import views

urlpatterns = [
   
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

  
    path('', views.trade_investment_dashboard, name='trade_investment_dashboard'),
    path('open_trade/', views.open_trade, name='open_trade'),
    path('close_trade/<int:position_id>/', views.close_trade, name='close_trade'),
    path('create_investment/', views.create_investment, name='create_investment'),
    path('market_data/<str:symbol>/', views.get_market_data, name='get_market_data'),

    # Financial Transaction URLs
    path('deposit/page/', views.deposit_page, name='deposit_page'),
    path('deposit_funds/', views.deposit_funds, name='deposit_funds'),
    path('withdraw/cash/', views.withdraw_fund, name='withdraw_fund'),

    path('support/', views.support_chat, name='support_chat'),
    path('support/create-ticket/', views.create_ticket, name='create_ticket'),
    path('support/ticket/<int:ticket_id>/messages/', views.get_ticket_messages, name='get_ticket_messages'),
    path('support/ticket/<int:ticket_id>/send/', views.send_message, name='send_message'),
    path('support/ticket/<int:ticket_id>/close/', views.close_ticket, name='close_ticket'),

    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/transaction/<int:transaction_id>/<str:action>/', views.process_transaction, name='admin_process_transaction'),

    path('dash/trades/', views.trade_list, name='trade_list'),
    path('dash/trades/<int:trade_id>/json/', views.get_trade_json, name='get_trade_json'),
    path('dash/trades/update/', views.update_trade, name='update_trade'),
    path('dash/trades/<int:trade_id>/delete/', views.delete_trade, name='delete_trade'),

    path('admin/chat/<int:ticket_id>/', views.get_ticket_chat, name='get_ticket_chat'),
    path('admin/chat/<int:ticket_id>/reply/', views.send_reply, name='send_reply'),
    path('admin/chat/recent/', views.get_recent_chats, name='get_recent_chats'),

    path('credit/transaction/<int:trans_id>', views.credit_transaction, name='credit_transaction'),
    path('delete/transaction/<int:trans_id>', views.delete_transaction, name='delete_transaction'),

    path('trade/edit/<int:trade_id>/', views.edit_trade, name='edit_trade'),
    path('trade/hide/<int:trade_id>/', views.hide_trade, name='hide_trade'),
    path('referal/code/',  views.referal_code, name='referal_code'),
    path('generate/code/', views.generate_code, name='generate_code'),
    path('api/tickets/<int:ticket_id>/messages/', views.ticket_messages, name='ticket_messages'),
    path('dash/withdrawal/', views.dash_withdrawal, name='dash_withdrawal'),
    path('reject/withdrawals/<int:transaction_id>', views.reject_withdrawals, name='reject_withdrawals'),
    path('approve/withdrawals/<int:transaction_id>', views.approve_withdrawals, name='approve_withdrawals'),
    path('settings/edit/<int:setting_id>/', views.edit_setting, name='edit_setting'),

    path('ticket/<int:ticket_id>/messages/', views.get_ticket_messages_new, name='get_ticket_messages'),
    path('ticket/<int:ticket_id>/send/', views.send_ticket_message, name='send_ticket_message'),

]


from django.urls import re_path
from bank import consumers

websocket_urlpatterns = [
    re_path(r'ws/support/(?P<ticket_id>\w+)/$', consumers.ChatConsumer.as_asgi()),
]