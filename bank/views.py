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
    BillPaymentForm, DepositForm, WithdrawalForm,
    SecuritySettingsForm
)
import json
from django.http import JsonResponse
from django.contrib.auth import update_session_auth_hash

from fido2.server import Fido2Server
from fido2.webauthn import PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
from django.views.decorators.csrf import csrf_exempt



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
        Q(sender_account__customer=request.user) |
        Q(recipient_account__customer=request.user),
        status='COMPLETED'
    ).select_related("sender_account", "recipient_account")[:10]
    return render(request, "main/dashboard.html", {
        "accounts": accounts,
        "total_balance": total_balance,
        "recent_transactions": recent_transactions,
        "has_biometric": getattr(request.user, "is_biometric_enabled", False),
    })


@login_required
def transfer_funds(request):
    return render(request, "main/transfer.html", {
        "accounts": Account.objects.filter(customer=request.user),
        "transfer_form": TransferForm(user=request.user),
        "mobile_money_form": MobileMoneyForm(user=request.user),
        "bill_payment_form": BillPaymentForm(user=request.user),
        "deposit_form": DepositForm(user=request.user),
        "withdrawal_form": WithdrawalForm(user=request.user),
        "recent_transactions": Transaction.objects.filter(
            Q(sender_account__customer=request.user) |
            Q(recipient_account__customer=request.user)
        ).order_by("-timestamp")[:10],
    })


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
        messages.success(request, f"Mobile Money transfer of GHS {amount:.2f} successful")
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
        return JsonResponse({
            "exists": True,
            "account_type": account.get_account_type_display(),
            "account_holder": f"{account.customer.first_name} {account.customer.last_name}",
        })
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
                details="Password updated"
            )
        return redirect("security_settings")

    logs = SecurityLog.objects.filter(user=request.user).order_by("-timestamp")[:20]
    return render(request, "main/security.html", {
        "form": form,
        "accounts": accounts,
        "security_logs": logs,
    })

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")


@login_required
def start_biometric_registration(request):
    rp = PublicKeyCredentialRpEntity(id="prestigebank.com", name="Prestige Bank")
    fido_server = Fido2Server(rp)

    user_entity = PublicKeyCredentialUserEntity(
        id=str(request.user.id).encode(),
        name=request.user.email,
        display_name=request.user.get_full_name(),
    )

    options, state = fido_server.register_begin(
        user_entity,
        credentials=None,
        user_verification="preferred"
    )

    request.session["fido_state"] = state

    # Convert FIDO2 options to a JSON-serializable dictionary
    options_dict = {
        "publicKey": {
            "rp": {
                "id": options.public_key.rp.id,
                "name": options.public_key.rp.name
            },
            "user": {
                "id": list(options.public_key.user.id),
                "name": options.public_key.user.name,
                "displayName": options.public_key.user.display_name
            },
            "challenge": list(options.public_key.challenge),
            "pubKeyCredParams": [
                {
                    "type": param.type,
                    "alg": param.alg
                }
                for param in options.public_key.pub_key_cred_params
            ],
            "timeout": options.public_key.timeout,
            "excludeCredentials": [
                {
                    "type": cred.type,
                    "id": list(cred.id),
                    "transports": cred.transports if hasattr(cred, 'transports') else []
                }
                for cred in options.public_key.exclude_credentials
            ] if options.public_key.exclude_credentials else [],
            "authenticatorSelection": {
                "authenticatorAttachment": options.public_key.authenticator_selection.authenticator_attachment if hasattr(options.public_key.authenticator_selection, 'authenticator_attachment') else None,
                "requireResidentKey": options.public_key.authenticator_selection.require_resident_key,
                "userVerification": options.public_key.authenticator_selection.user_verification
            } if options.public_key.authenticator_selection else None,
            "attestation": options.public_key.attestation,
            "extensions": options.public_key.extensions if hasattr(options.public_key, 'extensions') else {}
        }
    }

    return JsonResponse(options_dict, safe=False)


@login_required
@csrf_exempt
def complete_biometric_registration(request):
    rp = PublicKeyCredentialRpEntity(id="prestigebank.com", name="Prestige Bank")
    fido_server = Fido2Server(rp)

    state = request.session.pop("fido_state", None)
    if not state:
        return JsonResponse({"success": False, "error": "Registration session expired"})
    
    try:
        data = json.loads(request.body)
        # Convert back to the format expected by Fido2Server
        credential_data = {
            "id": data["id"],
            "type": data["type"],
            "rawId": Uint8Array(data["rawId"]).buffer if hasattr(data["rawId"], '__iter__') else data["rawId"],
            "response": {
                "attestationObject": Uint8Array([ord(c) for c in atob(data["response"]["attestationObject"])]).buffer,
                "clientDataJSON": Uint8Array([ord(c) for c in atob(data["response"]["clientDataJSON"])]).buffer
            }
        }
        
        auth_data = fido_server.register_complete(state, credential_data)

        request.user.biometric_data = json.dumps(auth_data.credential_data)
        request.user.is_biometric_enabled = True
        request.user.save()

        SecurityLog.objects.create(
            user=request.user,
            event_type="BIOMETRIC_UPDATE",
            ip_address=get_client_ip(request),
            details="Biometric registered"
        )

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})