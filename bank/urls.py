from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('transfer/', views.transfer_funds, name='transfer_funds'),
    path('mobile-money/', views.mobile_money, name='mobile_money'),
    path('security/', views.security_settings, name='security_settings'),
    path('trading/investment/', views.trading_investment, name='trade_investment')
]