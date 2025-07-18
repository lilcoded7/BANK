from django.urls import path 
from bank.views import *

urlpatterns = [
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard')
]