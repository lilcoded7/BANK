from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import RegisterUserForm
from bank.models import ReferalCode

User = get_user_model()


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

            messages.success(request, "User registration successful")
            auth_code.is_expired=True
            auth_code.save()
            return redirect("login")

        else:
            messages.error(request, "Please correct the errors below.")

    return render(request, "auth/signup.html", {"form": form})
