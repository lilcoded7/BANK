from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.trade_investment, name='trade_investment'),
    path('open_trade/', views.open_trade, name='open_trade'),
    path('close_trade/<int:position_id>/', views.close_trade, name='close_trade'),
    path('create_investment/', views.create_investment, name='create_investment'),
    path('deposit_funds/', views.deposit_funds, name='deposit_funds'),
    path('market_data/<str:symbol>/', views.get_market_data, name='get_market_data'),
]