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
    LoginForm,
    TransferForm,
    MobileMoneyForm,
    BillPaymentForm,
    DepositForm,
    WithdrawalForm,
    SecuritySettingsForm,
)
import json
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash

from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
from django.views.decorators.csrf import csrf_exempt
from bank.models import UserBiometricData


def login_view(request):
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
                details="Login successful",
            )
            messages.success(request, "Login successful")
            return redirect("dashboard")
        messages.error(request, "Invalid credentials")
    return render(request, "auth/login.html", {"form": form})


@login_required
def logout_view(request):
    SecurityLog.objects.create(
        user=request.user,
        event_type="LOGOUT",
        ip_address=get_client_ip(request),
        details="User logged out",
    )
    logout(request)
    messages.success(request, "You have been logged out")
    return redirect("login")


@login_required
def dashboard(request):
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    total_balance = accounts.aggregate(total=Sum("balance"))["total"] or 0
    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=request.user)
        | Q(recipient_account__customer=request.user),
        status="COMPLETED",
    ).select_related("sender_account", "recipient_account")[:10]
    return render(
        request,
        "main/dashboard.html",
        {
            "accounts": accounts,
            "total_balance": total_balance,
            "recent_transactions": recent_transactions,
            "has_biometric": getattr(request.user, "is_biometric_enabled", False),
        },
    )


@login_required
def transfer_funds(request):
    return render(
        request,
        "main/transfer.html",
        {
            "accounts": Account.objects.filter(customer=request.user),
            "transfer_form": TransferForm(user=request.user),
            "mobile_money_form": MobileMoneyForm(user=request.user),
            "bill_payment_form": BillPaymentForm(user=request.user),
            "deposit_form": DepositForm(user=request.user),
            "withdrawal_form": WithdrawalForm(user=request.user),
            "recent_transactions": Transaction.objects.filter(
                Q(sender_account__customer=request.user)
                | Q(recipient_account__customer=request.user)
            ).order_by("-timestamp")[:10],
        },
    )


@login_required
@db_transaction.atomic
def bank_transfer(request):
    form = TransferForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        from_account = form.cleaned_data["from_account"]
        to_account = form.cleaned_data["to_account_number"]
        amount = form.cleaned_data["amount"]
        from_account.balance -= amount
        to_account.balance += amount
        from_account.save()
        to_account.save()
        Transaction.objects.create(
            sender_account=from_account,
            recipient_account=to_account,
            amount=amount,
            transaction_type="TRANSFER",
        )
        messages.success(request, f"Transfer of GHS {amount:.2f} successful")
        return redirect("transfer_funds")
    return render(request, "main/transfer.html", {"transfer_form": form})


@login_required
@db_transaction.atomic
def mobile_money(request):
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
            request, f"Mobile Money transfer of GHS {amount:.2f} successful"
        )
        return redirect("transfer_funds")
    return render(request, "main/transfer.html", {"mobile_money_form": form})


@login_required
@db_transaction.atomic
def bill_payment(request):
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
        messages.success(request, f"Bill payment of GHS {amount:.2f} successful")
        return redirect("transfer_funds")
    return render(request, "main/transfer.html", {"bill_payment_form": form})


@login_required
@db_transaction.atomic
def deposit(request):
    form = DepositForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        to_account = form.cleaned_data["to_account"]
        amount = form.cleaned_data["amount"]
        to_account.balance += amount
        to_account.save()
        Transaction.objects.create(
            recipient_account=to_account,
            amount=amount,
            transaction_type="DEPOSIT",
            description=form.cleaned_data.get("description", ""),
        )
        messages.success(request, f"Deposit of GHS {amount:.2f} successful")
        return redirect("transfer_funds")
    return render(request, "main/transfer.html", {"deposit_form": form})


@login_required
@db_transaction.atomic
def withdrawal(request):
    form = WithdrawalForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        from_account = form.cleaned_data["from_account"]
        amount = form.cleaned_data["amount"]
        from_account.balance -= amount
        from_account.save()
        Transaction.objects.create(
            sender_account=from_account,
            amount=amount,
            transaction_type="WITHDRAWAL",
            description=form.cleaned_data.get("description", ""),
        )
        messages.success(request, f"Withdrawal of GHS {amount:.2f} successful")
        return redirect("transfer_funds")
    return render(request, "main/transfer.html", {"withdrawal_form": form})


@login_required
@require_POST
def verify_account(request):
    number = request.POST.get("account_number")
    try:
        account = Account.objects.get(account_number=number, status="ACTIVE")
        return JsonResponse(
            {
                "exists": True,
                "account_type": account.get_account_type_display(),
                "account_holder": f"{account.customer.first_name} {account.customer.last_name}",
            }
        )
    except Account.DoesNotExist:
        return JsonResponse({"exists": False})


@login_required
def security_settings(request):
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    form = SecuritySettingsForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("new_password"):
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully")
            SecurityLog.objects.create(
                user=request.user,
                event_type="PASSWORD_CHANGE",
                ip_address=get_client_ip(request),
                details="Password updated",
            )
        return redirect("security_settings")

    logs = SecurityLog.objects.filter(user=request.user).order_by("-timestamp")[:20]
    return render(
        request,
        "main/security.html",
        {
            "form": form,
            "accounts": accounts,
            "security_logs": logs,
        },
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return (
        x_forwarded_for.split(",")[0]
        if x_forwarded_for
        else request.META.get("REMOTE_ADDR")
    )


@login_required
def security_settings(request):
    # Your existing security settings view
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    form = SecuritySettingsForm(request.user, request.POST or None)

    if request.method == "POST" and form.is_valid():
        if form.cleaned_data.get("new_password"):
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully")
            SecurityLog.objects.create(
                user=request.user,
                event_type="PASSWORD_CHANGE",
                ip_address=get_client_ip(request),
                details="Password updated",
            )
        return redirect("security_settings")

    logs = SecurityLog.objects.filter(user=request.user).order_by("-timestamp")[:20]
    return render(
        request,
        "main/security.html",
        {
            "form": form,
            "accounts": accounts,
            "security_logs": logs,
        },
    )


@login_required
def start_biometric_registration(request):
    """Start the biometric registration process"""
    # Check if user already has biometric data
    if (
        hasattr(request.user, "biometric_data")
        and request.user.biometric_data.is_verified
    ):
        return JsonResponse(
            {
                "status": "error",
                "message": "Biometric authentication is already enabled for this account.",
            }
        )

    # Generate registration options (simplified)
    options = {
        "challenge": "random_challenge_string",  # In real implementation, generate a secure random string
        "rp": {"name": "Prestige Bank", "id": "prestigebank.com"},
        "user": {
            "id": str(request.user.id),
            "name": request.user.email,
            "displayName": request.user.get_full_name(),
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": -7},  # ES256
            {"type": "public-key", "alg": -257},  # RS256
        ],
        "timeout": 60000,
        "attestation": "direct",
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",
            "requireResidentKey": True,
            "userVerification": "preferred",
        },
    }

    # Store the challenge in session for verification later
    request.session["biometric_registration_challenge"] = options["challenge"]

    return JsonResponse(options)


@csrf_exempt
@login_required
def complete_biometric_registration(request):
    """Complete the biometric registration process"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"})

    try:
        data = json.loads(request.body)
        credential = data.get("credential")

        # Verify the challenge matches what we sent
        stored_challenge = request.session.get("biometric_registration_challenge")
        if not stored_challenge or stored_challenge != data.get("challenge"):
            return JsonResponse({"status": "error", "message": "Invalid challenge"})

        # In a real implementation, you would verify the attestation here
        # For this example, we'll just store the credential data

        # Create or update biometric data
        biometric_data, created = UserBiometricData.objects.get_or_create(
            user=request.user
        )
        biometric_data.credential_id = credential.get("id")
        biometric_data.public_key = json.dumps(credential.get("response", {}))
        biometric_data.is_verified = True
        biometric_data.save()

        # Update user model
        request.user.is_biometric_enabled = True
        request.user.save()

        # Create security log
        SecurityLog.objects.create(
            user=request.user,
            event_type="BIOMETRIC_ENABLED",
            ip_address=get_client_ip(request),
            details="Biometric authentication enabled",
        )

        # Clean up session
        if "biometric_registration_challenge" in request.session:
            del request.session["biometric_registration_challenge"]

        return JsonResponse(
            {"status": "success", "message": "Biometric registration completed"}
        )

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@login_required
def disable_biometric(request):
    """Disable biometric authentication for the user"""
    if request.method == "POST":
        try:
            # Delete biometric data
            UserBiometricData.objects.filter(user=request.user).delete()

            # Update user model
            request.user.is_biometric_enabled = False
            request.user.save()

            # Create security log
            SecurityLog.objects.create(
                user=request.user,
                event_type="BIOMETRIC_DISABLED",
                ip_address=get_client_ip(request),
                details="Biometric authentication disabled",
            )

            messages.success(request, "Biometric authentication has been disabled.")
        except Exception as e:
            messages.error(
                request, f"Error disabling biometric authentication: {str(e)}"
            )

    return redirect("security_settings")


@csrf_exempt
def verify_biometric(request):
    """Verify biometric data for authentication"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"})

    try:
        data = json.loads(request.body)
        credential_id = data.get("credentialId")

        # Look up the user by credential ID
        try:
            biometric_data = UserBiometricData.objects.get(credential_id=credential_id)
            user = biometric_data.user

            # In a real implementation, you would verify the signature here
            # For this example, we'll assume verification is successful

            # Log the user in
            from django.contrib.auth import login

            login(request, user)

            # Create security log
            SecurityLog.objects.create(
                user=user,
                event_type="BIOMETRIC_LOGIN",
                ip_address=get_client_ip(request),
                details="Logged in using biometric authentication",
            )

            return JsonResponse({"status": "success", "redirectUrl": "/"})

        except UserBiometricData.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid credential"})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


@login_required
def process_biometric_data(request):
    if request.method == "POST":

        facial_data = request.POST.get("facial_data")
        fingerprint_data = request.POST.get("fingerprint_data")

        biometric_data, created = UserBiometricData.objects.get_or_create(
            user=request.user
        )
        biometric_data.facial_data = facial_data
        biometric_data.fingerprint_data = fingerprint_data
        biometric_data.is_verified = True
        biometric_data.save()

        return JsonResponse({"status": "success"})
