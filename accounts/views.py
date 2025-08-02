from django.shortcuts import render
from accounts.forms import RegisterUser

# Create your views here.



def register_user(request):
    return render(request, 'main/')