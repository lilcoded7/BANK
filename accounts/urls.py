from django.urls import path
from accounts.views import *


urlpatterns = [
    path('register/', register_user, name='register_user'),
    path('get/user/email/', get_user_email, name='get_user_email'),
    path('reset/password/', reset_password, name='reset_password')
]