from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction as db_transaction
from .models import Account, Transaction, SecurityLog
from .forms import (
    LoginForm, TransferForm, MobileMoneyForm,
    BillPaymentForm, SecuritySettingsForm
)


# ---------------- AUTH ---------------- #

def login_view(request):
    """Handle user login with security logging."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user:
            login(request, user)
            SecurityLog.objects.create(
                user=user,
                event_type="LOGIN",
                ip_address=get_client_ip(request),
                device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                details="Standard password authentication",
            )
            messages.success(request, "Login successful!")
            return redirect("dashboard")
        messages.error(request, "Invalid email or password")

    return render(request, "auth/login.html", {"form": form})


@login_required
def logout_view(request):
    """Logout the user and log the event."""
    SecurityLog.objects.create(
        user=request.user,
        event_type="LOGOUT",
        ip_address=get_client_ip(request),
        details="User initiated logout",
    )
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")


# ---------------- DASHBOARD ---------------- #

@login_required
def dashboard(request):
    """Show account summary and recent transactions."""
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    total_balance = accounts.aggregate(total=Sum("balance"))["total"] or 0

    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=request.user)
        | Q(recipient_account__customer=request.user)
    ).select_related("sender_account", "recipient_account")[:10]

    return render(request, "main/dashboard.html", {
        "accounts": accounts,
        "total_balance": total_balance,
        "recent_transactions": recent_transactions,
        "has_biometric": getattr(request.user, "is_biometric_enabled", False),
    })


# ---------------- TRANSFERS ---------------- #

@login_required
def transfer_funds(request):
    """Render transfer form page (bank transfer, mobile money, bills)."""
    return render(request, "main/transfer.html", {
        "accounts": Account.objects.filter(customer=request.user),
        "transfer_form": TransferForm(user=request.user),
        "mobile_money_form": MobileMoneyForm(user=request.user),
        "bill_form": BillPaymentForm(user=request.user),
    })


@login_required
@db_transaction.atomic
def bank_transfer(request):
    """Process direct account-to-account transfers."""
    form = TransferForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        from_account = form.cleaned_data["from_account"]
        to_account = form.cleaned_data["to_account_number"]
        amount = form.cleaned_data["amount"]

        from_account.balance -= amount
        to_account.balance += amount
        from_account.save()
        to_account.save()

        transaction = Transaction.objects.create(
            sender_account=from_account,
            recipient_account=to_account,
            amount=amount,
            transaction_type="TRANSFER",
        )

        messages.success(
            request,
            f"Transfer successful to {transaction.recipient_account.customer.full_name}. "
            f"New balance: GHS {from_account.balance:.2f}",
        )
        return redirect("transfer_funds")

    return render(request, "main/transfer.html", {"transfer_form": form})


# ---------------- MOBILE MONEY ---------------- #

@login_required
@db_transaction.atomic
def mobile_money(request):
    """Handle Mobile Money transfers."""
    form = MobileMoneyForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        from_account = form.cleaned_data["from_account"]
        amount = form.cleaned_data["amount"]

        from_account.balance -= amount
        from_account.save()

        Transaction.objects.create(
            sender_account=from_account,
            recipient_mobile=form.cleaned_data["mobile_number"],
            network=form.cleaned_data["network"],
            amount=amount,
            transaction_type="MOBILE_MONEY",
        )

        messages.success(
            request,
            f"Mobile Money transfer of GHS {amount:.2f} successful. "
            f"New balance: GHS {from_account.balance:.2f}",
        )
        return redirect("transfer_funds")

    return render(request, "main/transfer.html", {"mobile_money_form": form})


# ---------------- BILL PAYMENTS ---------------- #

@login_required
@db_transaction.atomic
def bill_payment(request):
    """Handle bill payments."""
    form = BillPaymentForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        from_account = form.cleaned_data["from_account"]
        amount = form.cleaned_data["amount"]

        from_account.balance -= amount
        from_account.save()

        Transaction.objects.create(
            sender_account=from_account,
            bill_type=form.cleaned_data["bill_type"],
            recipient_account_number=form.cleaned_data["account_number"],
            amount=amount,
            transaction_type="BILL_PAYMENT",
            description=form.cleaned_data.get("description", ""),
        )

        messages.success(
            request,
            f"Bill payment of GHS {amount:.2f} successful. "
            f"New balance: GHS {from_account.balance:.2f}",
        )
        return redirect("transfer_funds")

    return render(request, "main/transfer.html", {"bill_form": form})


# ---------------- SECURITY SETTINGS ---------------- #

@login_required
def security_settings(request):
    """Manage password changes and biometric preferences."""
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    form = SecuritySettingsForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        # Password update
        if form.cleaned_data.get("new_password"):
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully!")
            SecurityLog.objects.create(
                user=request.user,
                event_type="PASSWORD_CHANGE",
                ip_address=get_client_ip(request),
                details="Password changed successfully",
            )

        # Biometric toggle
        new_biometric = form.cleaned_data.get("enable_biometric", False)
        if request.user.is_biometric_enabled != new_biometric:
            request.user.is_biometric_enabled = new_biometric
            request.user.save()
            status = "enabled" if new_biometric else "disabled"
            messages.success(request, f"Biometric authentication {status}!")
            SecurityLog.objects.create(
                user=request.user,
                event_type="BIOMETRIC_UPDATE",
                ip_address=get_client_ip(request),
                details=f"Biometric authentication {status}",
            )

        return redirect("security_settings")

    logs = SecurityLog.objects.filter(user=request.user).order_by("-timestamp")[:20]
    return render(request, "main/security.html", {
        "form": form,
        "accounts": accounts,
        "security_logs": logs,
    })


# ---------------- UTILITIES ---------------- #

@login_required
@require_POST
def verify_account(request):
    """AJAX endpoint to check if account exists."""
    number = request.POST.get("account_number")
    try:
        account = Account.objects.get(account_number=number, status="ACTIVE")
        return JsonResponse({
            "exists": True,
            "account_type": account.get_account_type_display(),
            "account_holder": f"{account.customer.first_name} {account.customer.last_name}",
        })
    except Account.DoesNotExist:
        return JsonResponse({"exists": False})


def get_client_ip(request):
    """Get real client IP (handles proxies)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")
