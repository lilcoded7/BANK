from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Avg
from bank.utils import *

from .forms import *


from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model
from bank.models import *
from bank.pay import *
import random

User = get_user_model()

sender = EmailSender()


def staff_required(user):
    return user.is_staff or user.is_superuser


def get_user_email_address(request):
    form = EmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        user = get_object_or_404(User, email=data.get('email'))
        otp_code = random.randint(100000, 999999)  # 6-digit OTP
        user.code = otp_code
        user.save()
        try:
            sender.send_otp(user)
            return redirect('get_user_email_address')
        except:
            pass
        
        # Optionally redirect or show success message
    return render(request, 'auth/get_user_email.html', {'form': form})


def  reset_password(request):
    form = ResetPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        code = data.get('code')
        new_password = data.get('password')
        
        # Find the user with this OTP code
        user = User.objects.filter(code=code).first()
        if user:
            user.set_password(new_password)  # Update password securely
            user.code = ''  # Clear the OTP code
            user.save()
            messages.success(request, "Your password has been reset successfully!")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP code. Please try again.")

    return render(request, 'auth/reset_password.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")  

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        user = authenticate(request, email=email, password=password)
        if user is not None:
            if user.is_2factor_authentication:
                try:
                    sender.send_otp(user)
                except:
                    pass
               
                return redirect('two_factor_auth', user_id=user.id)
            
            
            login(request, user)
            messages.success(request, f"Welcome back, {user.email}!")
            return redirect("dashboard")  
        else:
            messages.error(request, "Invalid email or password")

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out")
    return redirect("login")


def two_factor_auth(request, user_id):
    user = get_object_or_404(User, id=user_id)

    form = CodeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        user = User.objects.get(code=code)
   
        user.code = ""
        user.save()

        login(request, user)

        messages.success(request, "Two-Factor authentication successful!")
        return redirect("dashboard") 

    return render(request, "auth/2factor_.html", {"form": form, 'user':user})

def resen_auth_code(request, user_id):
    opt_code = random.randint(00000, 99999)
    user = get_object_or_404(User, id=user_id)
    user.code=opt_code
    user.save()
    try:
        sender.send_otp(user)
    except:
        pass
    messages.success(request, 'OTP Code has been sent to your email address')
    return redirect('two_factor_auth', user.id)



login_required
def dashboard(request):
    if request.user.is_admin:
        return redirect('support_chat_dashboard')
    
    customer = Customer.objects.filter(user=request.user).first()
    accounts = Account.objects.filter(customer=customer, status="ACTIVE")
    total_balance = accounts.aggregate(total=Sum("balance"))["total"] or 0
    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=customer) | Q(recipient_account__customer=customer)
    ).select_related("sender_account", "recipient_account")[:10]

    return render(
        request,
        "main/dashboard.html",
        {
            "accounts": accounts,
            "total_balance": total_balance,
            "recent_transactions": recent_transactions,
            "has_biometric": getattr(customer, "is_biometric_enabled", False),
        },
    )

login_required
def transfer_funds(request):
    customer = Customer.objects.filter(user=request.user).first()
    accounts = Account.objects.filter(customer=customer)
    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=customer) | Q(recipient_account__customer=customer)
    )[:20]

    context = {
        "transfer_form": BankTransferForm(),
        "mobile_money_form": MobileMoneyForm(),
        "deposit_form": DepositForm(),
        "withdrawal_form": WithdrawalForm(),
        "bill_payment_form": BillPaymentForm(),
        "accounts": accounts,
        "recent_transactions": recent_transactions,
    }
    return render(request, "main/transfer.html", context)


login_required
@transaction.atomic
def bank_transfer(request):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == "POST":
        form = BankTransferForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            sender_account = get_object_or_404(Account, account_number=data["sender_account"].strip())
            recipient = get_object_or_404(Account, account_number=data["recipient_account"].strip())

            if sender_account.balance < data["amount"]:
                messages.error(request, "Insufficient funds.")
                return redirect("transfer_funds")

            tx = Transaction.objects.create(
                customer=customer,
                transaction_id=generate_transaction_id(),
                transaction_type="TRANSFER",
                amount=data["amount"],
                sender_account=sender_account,
                recipient_account=recipient,
                description=data.get("description") or "N/A",
                status="pending",
            )

            response = initialize_transaction(tx, request.build_absolute_uri("/verify/transaction"))
            if response and response.get("status"):
                return redirect(response["data"]["authorization_url"])

            tx.status = "failed"
            tx.save()
            messages.error(request, "Failed processing request. Please try again later.")
            return redirect("transfer_funds")
    else:
        form = BankTransferForm()

    return render(request, "main/transfer.html", {"form": form})


login_required
def mobile_money(request):
    if request.method == "POST":
        form = MobileMoneyForm(request.POST)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.transaction_type = "MOBILE_MONEY"
            tx.transaction_id = generate_transaction_id()
            tx.customer = tx.sender_account.customer
            tx.status = "pending"
            tx.save()

            cal_url = request.build_absolute_uri("/verify/transaction")

            response = initialize_transaction(tx, cal_url)

            if response["status"]:
                authorization_url = response["data"]["authorization_url"]
                return redirect(authorization_url)
            else:
                messages.error(
                    request, "Fail Processing request, Kindly Try Again Later"
                )

            messages.success(request, "Mobile money sent successfully.")
            return redirect("transfer_funds")
    messages.error(request, "Mobile money transaction failed.")
    return redirect("transfer_funds")

login_required
def deposit(request):
    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            account = form.cleaned_data["to_account"]
            amount = form.cleaned_data["amount"]
            desc = form.cleaned_data.get("description", "")

            tx = Transaction.objects.create(
                transaction_type="DEPOSIT",
                transaction_id=generate_transaction_id(),
                customer=account.customer,
                recipient_account=account,
                amount=amount,
                description=desc,
                status="pending",
            )

            cal_url = request.build_absolute_uri("/verify/transaction")

            response = initialize_transaction(tx, cal_url)

            if response["status"]:
                authorization_url = response["data"]["authorization_url"]
                return redirect(authorization_url)
            else:
                messages.error(
                    request, "Fail Processing request, Kindly Try Again Later"
                )

            return redirect("transfer_funds")
    messages.error(request, "Deposit failed.")
    return redirect("transfer_funds")

login_required
def withdrawal(request):
    if request.method == "POST":
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            account = form.cleaned_data["from_account"]
            amount = form.cleaned_data["amount"]
            desc = form.cleaned_data.get("description", "")

            if account.balance >= amount:
                tx = Transaction.objects.create(
                    transaction_type="WITHDRAWAL",
                    transaction_id=generate_transaction_id(),
                    customer=account.customer,
                    sender_account=account,
                    amount=amount,
                    description=desc,
                    status="pending",
                )
                # account.balance -= amount
                # account.save()
                cal_url = request.build_absolute_uri("/verify/transaction")

            response = initialize_transaction(tx, cal_url)

            if response["status"]:
                authorization_url = response["data"]["authorization_url"]
                return redirect(authorization_url)
            else:
                messages.error(
                    request, "Fail Processing request, Kindly Try Again Later"
                )

            return redirect("transfer_funds")
    messages.error(request, "Withdrawal failed.")
    return redirect("transfer_funds")

login_required
def bill_payment(request):
    if request.method == "POST":
        form = BillPaymentForm(request.POST)
        if form.is_valid():
            
            tx = form.save(commit=False)
            tx.transaction_type = "BILL_PAYMENT"
            tx.transaction_id = generate_transaction_id()
            tx.customer = tx.sender_account.customer
            tx.status = "pending"
            tx.save()
            cal_url = request.build_absolute_uri("/verify/transaction")

            response = initialize_transaction(tx, cal_url)

            if response["status"]:
                authorization_url = response["data"]["authorization_url"]
                return redirect(authorization_url)
            else:
                messages.error(
                    request, "Fail Processing request, Kindly Try Again Later"
                )
            messages.success(request, "Bill payment successful.")
            return redirect("transfer_funds")
    messages.error(request, "Bill payment failed.")
    return redirect("transfer_funds")

login_required
def customer_profile(request):
    customer = get_object_or_404(Customer, user=request.user)

    accounts = Account.objects.filter(
        customer=customer,
    )

    transactions = Transaction.objects.filter(customer=customer).select_related(
        "sender_account", "recipient_account", "customer"
    )[:20]

    context = {
        "customer": customer,
        "accounts": accounts,
        "transactions": transactions,
    }
    return render(request, "main/profile.html", context)


@login_required
def security_settings(
    request,
):

    return render(request, "main/security.html")

login_required
def verify_transaction(request):
    reference = request.GET.get("reference")
    res = confirm_transaction(reference)

    transaction = get_object_or_404(Transaction, transaction_id=reference)

    if res["status"] and res["data"]["status"] == "success":
        if transaction.status != "success":  # Prevent double processing
            if transaction.transaction_type == "TRANSFER":
                credit_bank_transfer(transaction)
            elif transaction.transaction_type == "DEPOSIT":
                credit_deposit(transaction)
            elif transaction.transaction_type == "WITHDRAWAL":
                process_withdrawal(transaction)
            elif transaction.transaction_type == "BILL_PAYMENT":
                process_bill_payment(transaction)
            elif transaction.transaction_type == "MOBILE_MONEY":
                process_mobile_money(transaction)
            else:
                transaction.status = "failed"
                transaction.save()

        messages.success(request, "Payment Successful")
        return redirect("dashboard")

    transaction.status = "failed"
    transaction.save()
    messages.error(request, "Transaction verification failed.")
    return render(request, "main/verify_transaction.html")

login_required
def toggle_2fa(request):
    user = request.user
    
    user.is_2factor_authentication = not user.is_2factor_authentication  
    
    if user.is_2factor_authentication:
        messages.success(request, "Two-Factor Authentication has been enabled ✅")
    else:
        messages.warning(request, "Two-Factor Authentication has been disabled ❌")
    
    user.save()
    return redirect("security_settings")


login_required
def chat_page(request):
    """Render the chat interface"""
    messages = ChatMessage.objects.filter(user=request.user)
    return render(request, "main/chat.html", {"messages": messages})

@login_required
def send_message(request):
    """Customer sends message"""
    if request.method == "POST":
        text = request.POST.get("message", "").strip()
        if text:
            ChatMessage.objects.create(
                user=request.user,
                sender="customer",
                message=text
            )
    return redirect("chat_page")

@login_required
def get_messages(request):
    """Fetch messages for AJAX refresh"""
    messages = ChatMessage.objects.filter(user=request.user).values("sender", "message", "timestamp")
    return JsonResponse(list(messages), safe=False)

@login_required
def support_reply(request, user_id):
    """
    Support staff can reply to a customer.
    (You’d normally restrict this to support/admin users)
    """
    if request.method == "POST":
        text = request.POST.get("message", "").strip()
        if text:
            ChatMessage.objects.create(
                user_id=user_id,
                sender="support",
                message=text
            )
    return redirect("chat_page")  


def support_dashboard(request):
    total_customers = Customer.objects.count()
    total_accounts = Account.objects.count()
    total_transactions = Transaction.objects.count()
    total_balance = Account.objects.aggregate(total=Sum("balance"))["total"] or 0

    # Transaction flow for chart (group by month)
    transactions = (
        Transaction.objects.extra(select={'month': "strftime('%%m', timestamp)"})
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    chart_labels = [t['month'] for t in transactions]
    chart_data = [t['total'] for t in transactions]

    users = Customer.objects.all()

    return render(request, "dash/dashboard.html", {
        "total_customers": total_customers,
        "total_accounts": total_accounts,
        "total_transactions": total_transactions,
        "total_balance": total_balance,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "users": users,
    })


def transactions_dashboard(request):
    # Calculate aggregates
    amount_in = Transaction.objects.filter(
        transaction_type__in=["DEPOSIT", "TRANSFER", "MOBILE_MONEY"]
    ).aggregate(total=Sum("amount"))["total"] or 0

    amount_out = Transaction.objects.filter(
        transaction_type__in=["WITHDRAWAL", "BILL_PAYMENT"]
    ).aggregate(total=Sum("amount"))["total"] or 0

    total_balance = Account.objects.aggregate(total=Sum("balance"))["total"] or 0
    average_transaction = Transaction.objects.aggregate(avg=Avg("amount"))["avg"] or 0

    # Get all transactions
    transactions = Transaction.objects.select_related("customer").all()

    return render(request, "dash/transactions_dashboard.html", {
        "amount_in": amount_in,
        "amount_out": amount_out,
        "total_balance": total_balance,
        "average_transaction": average_transaction,
        "transactions": transactions,
    })


def support_chat_dashboard(request, customer_id=None):
    # Customers with existing chats
    users = User.objects.filter(chat_messages__isnull=False).distinct()

    customer = None
    messages = []
    if customer_id:
        customer = get_object_or_404(User, id=customer_id)
        messages = ChatMessage.objects.filter(user=customer).order_by("timestamp")

        # Handle support reply
        if request.method == "POST":
            msg = request.POST.get("message")
            if msg:
                ChatMessage.objects.create(
                    user=customer,
                    sender="support",
                    message=msg,
                )
                return redirect("support_chat_dashboard", customer_id=customer.id)

    return render(request, "dash/support_chat.html", {
        "users": users,
        "customer": customer,
        "messages": messages,
    })


def customer_list(request):
    customers = Customer.objects.select_related("user").all()

    if request.method == "POST":
        form = CustomerCreateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer and Account created successfully!")
            return redirect("customer_list")
    else:
        form = CustomerCreateForm()

    return render(request, "dash/customers.html", {"customers": customers, "form": form})