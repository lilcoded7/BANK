from django.urls import path
from . import views

urlpatterns = [
    # path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('', views.trade_investment_dashboard, name='trade_investment_dashboard'),
    path('open_trade/', views.open_trade, name='open_trade'),
    path('close_trade/<int:position_id>/', views.close_trade, name='close_trade'),
    path('create_investment/', views.create_investment, name='create_investment'),
    path('deposit_funds/', views.deposit_funds, name='deposit_funds'),
    path('market_data/<str:symbol>/', views.get_market_data, name='get_market_data'),
    path('deposit/page/', views.deposit_page, name='deposit_page'),
    path('support/page/', views.support_page, name='support_page'),

    path('create/support/ticket', views.create_support_ticket, name='create_support_ticket'),
    path('support/page/', views.send_support_message, name='send_support_message'),
    path('close/support/ticket/', views.close_support_ticket, name='close_support_ticket')
]