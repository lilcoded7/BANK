from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.contrib import messages

from .forms import *


from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string

from bank.models import *
from bank.pay import *


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
          
            messages.success(request, "Login successful")
            return redirect("dashboard")
        messages.error(request, "Invalid credentials")
    return render(request, "auth/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out")
    return redirect("login")


def generate_transaction_id():
    return get_random_string(12).upper()


def dashboard(request):
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


def bank_transfer(request):
    if request.method == "POST":
        form = BankTransferForm(request.POST)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.transaction_type = "TRANSFER"
            tx.transaction_id = generate_transaction_id()
            tx.customer = tx.sender_account.customer
            tx.status = "success"
            tx.save()

            # tx.sender_account.balance-=tx.amount
            # tx.recipient_account.balance+=tx.amount
            # tx.sender_account.save()
            # tx.recipient_account.save()
            # tx.save()

            cal_url = request.build_absolute_uri('/veryfy/transaction')

            response = initialize_transaction(tx, cal_url)

            if response['status']:
                authorization_url = response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, 'Fail Processing request, Kindly Try Again Later')

            return redirect("transfer_funds")
    messages.error(request, "Bank transfer failed.")
    return redirect("transfer_funds")


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

            cal_url = request.build_absolute_uri('/veryfy/transaction')

            response = initialize_transaction(tx, cal_url)

            if response['status']:
                authorization_url = response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, 'Fail Processing request, Kindly Try Again Later')


            messages.success(request, "Mobile money sent successfully.")
            return redirect("transfer_funds")
    messages.error(request, "Mobile money transaction failed.")
    return redirect("transfer_funds")


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

            # account.balance += amount
            # account.save()
            cal_url = request.build_absolute_uri('/veryfy/transaction')

            response = initialize_transaction(tx, cal_url)

            if response['status']:
                authorization_url = response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, 'Fail Processing request, Kindly Try Again Later')

            return redirect("transfer_funds")
    messages.error(request, "Deposit failed.")
    return redirect("transfer_funds")


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
                cal_url = request.build_absolute_uri('/veryfy/transaction')

            response = initialize_transaction(tx, cal_url)

            if response['status']:
                authorization_url = response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, 'Fail Processing request, Kindly Try Again Later')

            return redirect("transfer_funds")
    messages.error(request, "Withdrawal failed.")
    return redirect("transfer_funds")


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
            cal_url = request.build_absolute_uri('/veryfy/transaction')

            response = initialize_transaction(tx, cal_url)

            if response['status']:
                authorization_url = response['data']['authorization_url']
                return redirect(authorization_url)
            else:
                messages.error(request, 'Fail Processing request, Kindly Try Again Later')

            messages.success(request, "Bill payment successful.")
            return redirect("transfer_funds")
    messages.error(request, "Bill payment failed.")
    return redirect("transfer_funds")



def customer_profile(request):
    customer = get_object_or_404(Customer, user=request.user)

    accounts = Account.objects.filter(customer=customer, )

    transactions = Transaction.objects.filter(
        customer=customer
    ).select_related("sender_account", "recipient_account", 'customer')[:20]  

    context = {
        "customer": customer,
        "accounts": accounts,
        "transactions": transactions,
    }
    return render(request, "main/profile.html", context)


@login_required
def security_settings(request,):
  
    return render(request, "main/security.html")




def verify_transaction(request):
    reference = request.GET.get('reference')
    res = confirm_transaction(reference)

    if res['status'] and res['data']['status'] == 'success':
        transaction = get_object_or_404(Transaction, transaction_id=reference)
        transaction.status='sucess'
        transaction.save()
        print('transaction is successful here oooooo')


        messages.success(request, 'Payment Successful')
        return redirect('dashboard')
    return render(request, 'main/verify_transaction.html')