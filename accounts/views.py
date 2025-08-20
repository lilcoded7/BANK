from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import *
from bank.models import ReferalCode
from bank.models import Account
from accounts.utils import *
import random

User = get_user_model()

sender = EmailSender()

def register_user(request):
    form = RegisterUserForm()

    if request.method == "POST":
        form = RegisterUserForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            referal_code = form.cleaned_data["referal_code"]

            auth_code = get_object_or_404(ReferalCode, code=referal_code)

            user = User.objects.create(username=username, email=email)
            user.set_password(password)
            user.save()

            account = Account.objects.create(
                customer=user, account_type='INVESTMENT', status='ACTIVE'
            )

            messages.success(request, "User registration successful")
            auth_code.is_expired=True
            auth_code.save()
            return redirect("login")

        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "auth/signup.html", {"form": form})



def get_user_email(request):
    form = EmailForm()

    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = get_object_or_404(User, email=email)

            code = random.randint(0000, 9999)
            user.code=code
            user.save()
            '''sending verification code '''    
            try:
                sender.send_reset_password_code(user)
            except:
                pass 

            messages.success(request, 'a verification code has been sent to your email account, kindly check to reset your password')
            return redirect('reset_password')
        else:
            messages.error(request, 'NO account match with this email')
    else:
        form = EmailForm()

    return render(request, 'auth/email.html', {'form':form})


def reset_password(request):
    form = ResetPasswordForm()

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)

        if form.is_valid():      
            code = form.cleaned_data['code']
            password = form.cleaned_data['new_password']

            user = get_object_or_404(User, code=code)
            user.set_password(password)
            
            user.code = None  
            user.save()
            '''send success message '''   
            try:
                sender.send_reset_password_success_message(user)
            except:
                pass 
            messages.success(request, 'password reset successfully')
            return redirect('login')
        else:
            form = ResetPasswordForm()
    else:
        form = ResetPasswordForm()
    
    return render(request, 'auth/reset_password.html', {'form':form})

