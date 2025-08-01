# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from .models import *
from .forms import *
from django.db.models import Sum
from .models import (
    Account,
    InvestmentPackage,
    Investment,
    TradePosition,
    Transaction,
    SecurityLog,
    PrestigeSettings,
)
from decimal import Decimal
import random
import string
from django.http import JsonResponse
from django.db import transaction
import json


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                email=form.cleaned_data["email"], password=form.cleaned_data["password"]
            )
            if user is not None:
                login(request, user)
                SecurityLog.objects.create(
                    user=user,
                    event_type="LOGIN",
                    ip_address=request.META.get("REMOTE_ADDR"),
                    device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                    details="Standard password authentication",
                )
                return redirect("dashboard")
            else:
                messages.error(request, "Invalid email or password")
        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form})


@login_required
def logout_view(request):
    SecurityLog.objects.create(
        user=request.user,
        event_type="LOGOUT",
        ip_address=request.META.get("REMOTE_ADDR"),
        details="User initiated logout",
    )
    logout(request)
    return redirect("login")


# views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from .models import (
    Account,
    InvestmentPackage,
    Investment,
    TradePosition,
    Transaction,
    SecurityLog,
    PrestigeSettings,
)
from .forms import *
from decimal import Decimal
import random
import string
from django.http import JsonResponse


@login_required
def trade_investment_dashboard(request):
    user = request.user
    bank_settings = PrestigeSettings.load()
    investment_form = InvestmentForm()

    investment_account, created = Account.objects.get_or_create(
        customer=user,
        account_type="INVESTMENT",
        defaults={"balance": Decimal("0.00"), "currency": "GHS", "status": "ACTIVE"},
    )
    account = Account.objects.filter(customer=request.user).first()

    investment_balance = account.balance
    active_trades = TradePosition.objects.filter(user=user, status="OPEN").count()
    pending_trades = TradePosition.objects.filter(user=user, status="PENDING").count()

    total_profit = TradePosition.objects.filter(user=user, status="CLOSED").aggregate(
        Sum("profit_loss")
    )["profit_loss__sum"] or Decimal("0.00")

    has_active_investment = Investment.objects.filter(
        account=investment_account, status="ACTIVE"
    ).exists()

    packages = InvestmentPackage.objects.all()

    active_positions = TradePosition.objects.filter(user=user, status="OPEN").order_by(
        "-opened_at"
    )

    for position in active_positions:

        price_change = Decimal(random.uniform(-0.05, 0.05))
        position.current_price = position.entry_price * (1 + price_change)
        position.calculate_profit_loss()

    deposit_form = DepositForm()
    open_trade_form = OpenTradeForm(user=user, bank_settings=bank_settings)
    

    SecurityLog.objects.create(
        user=user,
        event_type="DASHBOARD_ACCESS",
        ip_address=request.META.get("REMOTE_ADDR"),
        device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
        details="Accessed Trade Investment Dashboard",
    )

    context = {
        "investment_balance": investment_balance,
        "active_trades": active_trades,
        "pending_trades": pending_trades,
        "total_profit": total_profit,
        "has_active_investment": has_active_investment,
        "packages": packages,
        "active_positions": active_positions,
        "accounts": Account.objects.filter(customer=user),
        "bank_settings": bank_settings,
        "deposit_form": deposit_form,
        "open_trade_form": open_trade_form,
        'investment_form':investment_form
    }

    return render(request, "main/trade.html", context)


@login_required
def open_trade(request):
    user = request.user
    bank_settings = PrestigeSettings.load()

    if request.method == "POST":
        form = OpenTradeForm(request.POST, user=user, bank_settings=bank_settings)

        if form.is_valid():
            symbol = form.cleaned_data["symbol"]
            trade_type = form.cleaned_data["trade_type"]
            amount = form.cleaned_data["amount"]
            leverage = form.cleaned_data["leverage"]
            take_profit = form.cleaned_data["take_profit"]
            stop_loss = form.cleaned_data["stop_loss"]
            entry_price = form.cleaned_data.get("entry_price", 0)

            try:
                account = Account.objects.get(customer=user, account_type="INVESTMENT")
            except Account.DoesNotExist:
                messages.error(request, "No investment account found")
                return redirect("trade_investment_dashboard")

            margin_required = amount / leverage

            position = TradePosition.objects.create(
                user=user,
                symbol=symbol,
                trade_type=trade_type,
                amount=amount,
                leverage=leverage,
                entry_price=entry_price,
                current_price=entry_price,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )

            account.balance -= margin_required
            account.save()

            transaction_id = generate_transaction_id()
            Transaction.objects.create(
                account=account,
                transaction_id=transaction_id,
                transaction_type="TRADE_OPEN",
                amount=margin_required,
                currency="GHS",
                status="COMPLETED",
                description=f"{trade_type} position on {symbol}",
                trade_position=position,
            )

            SecurityLog.objects.create(
                user=user,
                event_type="TRADE_OPENED",
                ip_address=request.META.get("REMOTE_ADDR"),
                device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                details=f"Opened {trade_type} trade on {symbol} for ${amount}",
            )

            messages.success(
                request, f"✅ Trade opened successfully! Position ID: {position.id}"
            )
            return redirect("trade_investment_dashboard")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        messages.error(request, "Invalid request method")

    return redirect("trade_investment_dashboard")


@login_required
def close_trade(request, position_id):
    user = request.user

    try:
        position = TradePosition.objects.get(id=position_id, user=user, status="OPEN")

        account = Account.objects.get(customer=user, account_type="INVESTMENT")

        position.calculate_profit_loss()
        profit_loss = position.profit_loss

        position.status = "CLOSED"
        position.closed_at = timezone.now()
        position.save()

        amount_to_return = position.margin_required + profit_loss

        account.balance += amount_to_return
        account.save()

        transaction_id = generate_transaction_id()
        Transaction.objects.create(
            account=account,
            transaction_id=transaction_id,
            transaction_type="TRADE_CLOSE",
            amount=amount_to_return,
            currency="GHS",
            status="COMPLETED",
            description=f"Closed {position.get_trade_type_display()} position on {position.symbol}",
            trade_position=position,
        )

        SecurityLog.objects.create(
            user=user,
            event_type="TRADE_CLOSED",
            ip_address=request.META.get("REMOTE_ADDR"),
            device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
            details=f"Closed trade on {position.symbol} with {'profit' if profit_loss >= 0 else 'loss'} of ${abs(profit_loss):.2f}",
        )

        messages.success(
            request,
            f"✅ Position closed! {'Profit' if profit_loss >= 0 else 'Loss'}: ${abs(profit_loss):.2f}",
        )
    except TradePosition.DoesNotExist:
        messages.error(request, "Position not found or already closed")
    except Account.DoesNotExist:
        messages.error(request, "Investment account not found")

    return redirect("trade_investment_dashboard")



@login_required
def create_investment(request):
    try:
        account = Account.objects.select_for_update().get(customer=request.user)
    except Account.DoesNotExist:
        messages.error(request, "Account not found.")
        return redirect("trade_investment_dashboard")

    if request.method == "POST":
        form = InvestmentForm(request.POST)
        if form.is_valid():
            package = form.cleaned_data['package']
            amount = form.cleaned_data['amount']

            if not package.min_amount <= amount <= package.max_amount:
                messages.error(
                    request, 
                    f"Amount must be between ${package.min_amount} and ${package.max_amount}."
                )
                return redirect("trade_investment_dashboard")

            if amount > account.balance:
                messages.error(request, "Insufficient funds for this investment.")
                return redirect("trade_investment_dashboard")

            try:
                with transaction.atomic():
               
                    investment = Investment(
                        account=account,
                        package=package,
                        amount=amount,
                    )
                    investment.save()
                  
                    account.balance -= amount
                    account.save()
                    
                messages.success(request, "Investment created successfully!")
                return redirect("trade_investment_dashboard")
                    
            except Exception as e:
                
                messages.error(request, "Failed to create investment. Please try again.")
        else:
       
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    
    return render(request, "trade_investment_dashboard.html", {
        'form': form,
        'packages': InvestmentPackage.objects.all(),
       
    })

@login_required
def deposit_funds(request):
    user = request.user

    if request.method == "POST":
        form = DepositForm(request.POST)

        if form.is_valid():
            currency = form.cleaned_data["currency"]
            amount = form.cleaned_data["amount"]

            # Get deposit address from settings
            settings = PrestigeSettings.load()
            address_lookup = {
                "BTC": settings.deposit_btc_address,
                "ETH": settings.deposit_eth_address,
                "USDT": settings.deposit_usdt_address,
            }
            deposit_address = address_lookup.get(currency)

            if not deposit_address:
                messages.error(request, f"No deposit address configured for {currency}")
                return redirect("trade_investment_dashboard")

            # Get user's investment account
            try:
                account = Account.objects.get(customer=user, account_type="INVESTMENT")
            except Account.DoesNotExist:
                messages.error(request, "Investment account not found")
                return redirect("trade_investment_dashboard")

            # Create pending transaction
            transaction_id = generate_transaction_id()
            Transaction.objects.create(
                account=account,
                transaction_id=transaction_id,
                transaction_type="DEPOSIT",
                amount=Decimal(amount),
                currency=currency,
                status="PENDING",
                description="Crypto deposit to investment account",
                metadata={
                    "deposit_address": deposit_address,
                    "currency": currency,
                    "expected_amount": str(amount),
                },
            )

            SecurityLog.objects.create(
                user=user,
                event_type="DEPOSIT_INITIATED",
                ip_address=request.META.get("REMOTE_ADDR"),
                device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                details=f"Initiated {currency} deposit of {amount}",
            )

            messages.success(
                request,
                f"📬 Deposit Instructions:\n\n"
                f"1. Send exactly {amount} {currency} to:\n"
                f"   **{deposit_address}**\n\n"
                f"2. After sending, contact support with:\n"
                f"   - Transaction ID: **{transaction_id}**\n"
                f"   - Transaction hash\n\n"
                f"💡 Funds will be credited after verification.",
            )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        messages.error(request, "Invalid request method")

    return redirect("trade_investment_dashboard")


@login_required
def get_market_data(request, symbol):

    try:

        base_price = {
            "BTCUSDT": Decimal("55000.00"),
            "ETHUSDT": Decimal("3000.00"),
            "BNBUSDT": Decimal("500.00"),
            "SOLUSDT": Decimal("100.00"),
            "XRPUSDT": Decimal("0.50"),
        }.get(symbol, Decimal("10000.00"))

        price = base_price * Decimal(1 + random.uniform(-0.02, 0.02)).quantize(
            Decimal("0.01")
        )
        change = Decimal(random.uniform(-3, 3)).quantize(Decimal("0.01"))
        high = price * Decimal(1 + random.uniform(0.01, 0.03)).quantize(Decimal("0.01"))
        low = price * Decimal(1 - random.uniform(0.01, 0.03)).quantize(Decimal("0.01"))
        volume = round(random.uniform(1000000, 50000000))

        return JsonResponse(
            {
                "success": True,
                "symbol": symbol,
                "price": float(price),
                "change": float(change),
                "high": float(high),
                "low": float(low),
                "volume": volume,
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def generate_transaction_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=12))


@login_required
def deposit_page(request):

    deposits = Transaction.objects.filter(
        account__customer=request.user, transaction_type="DEPOSIT"
    ).order_by("-timestamp")

    total_deposited = (
        deposits.aggregate(total=Sum("amount", filter=Q(status="COMPLETED")))["total"]
        or 0
    )

    completed_deposits = deposits.filter(status="COMPLETED").count()
    pending_deposits = deposits.filter(status="PENDING").count()

    context = {
        "deposits": deposits,
        "total_deposited": total_deposited,
        "completed_deposits": completed_deposits,
        "pending_deposits": pending_deposits,
        "deposit_form": DepositForm(),
    }

    return render(request, "main/deposit.html", context)


@login_required
def support_page(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-updated_at")

    active_ticket = None
    ticket_id = request.GET.get("ticket")
    if ticket_id:
        try:
            active_ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
        except SupportTicket.DoesNotExist:
            messages.error(request, "Ticket not found")

    context = {"tickets": tickets, "active_ticket": active_ticket}
    return render(request, "main/support.html", context)


@login_required
def create_support_ticket(request):
    if request.method == "POST":
        subject = request.POST.get("subject")
        priority = request.POST.get("priority")
        message_text = request.POST.get("message")

        if subject and message_text:

            ticket = SupportTicket.objects.create(
                user=request.user, subject=subject, priority=priority
            )

            SupportMessage.objects.create(
                ticket=ticket, user=request.user, message=message_text
            )

            messages.success(request, "Support ticket created successfully")
            return redirect("support_page") + f"?ticket={ticket.id}"
        else:
            messages.error(request, "Subject and message are required")

    return redirect("support_page")


@login_required
def send_support_message(request, ticket_id):
    if request.method == "POST":
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            message_text = request.POST.get("message")
            image = request.FILES.get("image")

            if message_text or image:

                SupportMessage.objects.create(
                    ticket=ticket, user=request.user, message=message_text, image=image
                )

                if ticket.status == "RESOLVED" or ticket.status == "CLOSED":
                    ticket.status = "OPEN"
                    ticket.save()

                messages.success(request, "Message sent successfully")
            else:
                messages.error(request, "Message or image is required")
        except SupportTicket.DoesNotExist:
            messages.error(request, "Ticket not found")

    return redirect("support_page") + f"?ticket={ticket_id}"


@login_required
def close_support_ticket(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
        ticket.status = "CLOSED"
        ticket.save()
        messages.success(request, "Ticket closed successfully")
    except SupportTicket.DoesNotExist:
        messages.error(request, "Ticket not found")

    return redirect("support_page")
