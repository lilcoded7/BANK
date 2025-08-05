from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Max, Count, Q, Sum, F
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from django.utils.timezone import now
from datetime import timedelta
import random
import string
from bank.models import *
from bank.forms import *
import json

User = get_user_model()


def is_staff_user(user):
    return user.is_staff


def admin_required(user):
    return user.is_staff or user.is_superuser


def login_view(request):
    if request.user.is_authenticated:
        return redirect("trade_investment_dashboard")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                email=form.cleaned_data["email"], password=form.cleaned_data["password"]
            )
            if user:
                login(request, user)
                SecurityLog.objects.create(
                    user=user,
                    event_type="LOGIN",
                    ip_address=request.META.get("REMOTE_ADDR"),
                    device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                    details="Standard password authentication",
                )
                if user.is_admin:
                    return redirect("admin_dashboard")

                return redirect("trade_investment_dashboard")
            messages.error(request, "Invalid email or password")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    SecurityLog.objects.create(
        user=request.user,
        event_type="LOGOUT",
        ip_address=request.META.get("REMOTE_ADDR"),
        details="User initiated logout",
    )
    logout(request)
    return redirect("login")



@login_required
def trade_investment_dashboard(request):

    if request.user.is_admin:
        return redirect('admin_dashboard')

    user = request.user
    bank_settings = PrestigeSettings.load()
    account = Account.objects.filter(customer=user).first()

    context = {
        "investment_balance": account.balance if account else 0,
        "active_trades": TradePosition.objects.filter(user=user, hidden=False, status="OPEN").count(),
        "pending_trades": TradePosition.objects.filter(
            user=user, status="PENDING", hidden=False
        ).count(),
        "total_profit": TradePosition.objects.filter(
            user=user, status="CLOSED", hidden=False
        ).aggregate(Sum("profit_loss"))["profit_loss__sum"]
        or Decimal("0.00"),
        "has_active_investment": Investment.objects.filter(
            account__customer=user, status="ACTIVE"
        ).exists(),
        "packages": InvestmentPackage.objects.all(),
        "active_positions": TradePosition.objects.filter(
            user=user, status="OPEN"
        ).order_by("-opened_at"),
        "accounts": Account.objects.filter(customer=user),
        "bank_settings": bank_settings,
        "deposit_form": DepositForm(),
        "open_trade_form": OpenTradeForm(user=user, bank_settings=bank_settings),
        "investment_form": InvestmentForm(),
    }

    SecurityLog.objects.create(
        user=user,
        event_type="DASHBOARD_ACCESS",
        ip_address=request.META.get("REMOTE_ADDR"),
        details="Accessed Trade Investment Dashboard",
    )
    return render(request, "main/trade.html", context)


@login_required
def open_trade(request):
    user = request.user
    bank_settings = PrestigeSettings.load()
    form = OpenTradeForm(request.POST, user=user, bank_settings=bank_settings)

    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error[0])
        return redirect("trade_investment_dashboard")

    try:
        with transaction.atomic():
            account = Account.objects.get(customer=user, account_type="INVESTMENT")
            data = form.cleaned_data
            margin_required = data["amount"] / data["leverage"]

            if account.balance < margin_required:
                messages.error(request, "Insufficient funds for this trade")
                return redirect("trade_investment_dashboard")

            position = TradePosition.objects.create(
                user=user,
                symbol=data["symbol"],
                trade_type=data["trade_type"],
                amount=data["amount"],
                leverage=data["leverage"],
                entry_price=data.get("entry_price", 0),
                current_price=data.get("entry_price", 0),
                take_profit=data["take_profit"],
                stop_loss=data["stop_loss"],
            )

            account.balance -= margin_required
            account.save()

            Transaction.objects.create(
                account=account,
                transaction_id="".join(
                    random.choices(string.ascii_uppercase + string.digits, k=12)
                ),
                transaction_type="TRADE",
                amount=margin_required,
                description=f"{data['trade_type']} position on {data['symbol']}",
                trade_position=position,
            )

            messages.success(
                request, f"Trade opened successfully! Position ID: {position.id}"
            )
    except Account.DoesNotExist:
        messages.error(request, "Investment account not found")
    except Exception as e:
        messages.error(request, f"Error opening trade: {str(e)}")

    return redirect("trade_investment_dashboard")


@login_required
def close_trade(request, position_id):
    try:
        position = TradePosition.objects.get(
            id=position_id, user=request.user, status="OPEN"
        )
        account = Account.objects.get(customer=request.user, account_type="INVESTMENT")

        with transaction.atomic():
            position.calculate_profit_loss()
            position.status = "CLOSED"
            position.closed_at = timezone.now()
            position.save()

            amount_to_return = position.profit_loss
            account.balance += amount_to_return
            account.save()

            Transaction.objects.create(
                account=account,
                transaction_id="".join(
                    random.choices(string.ascii_uppercase + string.digits, k=12)
                ),
                transaction_type="TRADE_CLOSE",
                amount=amount_to_return,
                description=f"Closed {position.get_trade_type_display()} position",
                trade_position=position,
            )

            messages.success(
                request, f"Position closed! Profit/Loss: ${position.profit_loss:.2f}"
            )

    except TradePosition.DoesNotExist:
        messages.error(request, "Position not found or already closed")
    except Account.DoesNotExist:
        messages.error(request, "Investment account not found")
    except Exception as e:
        messages.error(request, f"Error closing trade: {str(e)}")

    return redirect("trade_investment_dashboard")


@login_required
def create_investment(request):
    form = InvestmentForm(request.POST)
    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error[0])
        return redirect("trade_investment_dashboard")

    try:
        with transaction.atomic():
            account = Account.objects.get(
                customer=request.user, account_type="INVESTMENT"
            )
            package = form.cleaned_data["package"]
            amount = form.cleaned_data["amount"]

            if not package.min_amount <= amount <= package.max_amount:
                messages.error(
                    request,
                    f"Amount must be between ${package.min_amount} and ${package.max_amount}",
                )
                return redirect("trade_investment_dashboard")

            if amount > account.balance:
                messages.error(request, "Insufficient funds for this investment")
                return redirect("trade_investment_dashboard")

            Investment.objects.create(
                account=account,
                package=package,
                amount=amount,
            )
            account.balance -= amount
            account.save()

            messages.success(request, "Investment created successfully!")
    except Account.DoesNotExist:
        messages.error(request, "Account not found")
    except Exception as e:
        messages.error(request, f"Error creating investment: {str(e)}")

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
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def deposit_page(request):
    prestige = PrestigeSettings.load()
    account = Account.objects.filter(customer=request.user).first()
    deposits = Transaction.objects.filter(
        account__customer=request.user, transaction_type="DEPOSIT"
    ).order_by("-timestamp")

    context = {
        "prestige": prestige,
        "deposits": deposits,
        "total_deposited": deposits.filter(status="COMPLETED").aggregate(Sum("amount"))[
            "amount__sum"
        ]
        or 0,
        "completed_deposits": deposits.filter(status="COMPLETED").count(),
        "pending_deposits": deposits.filter(status="PENDING").count(),
        "deposit_form": DepositForm(),
        "account": account,
    }
    return render(request, "main/deposit.html", context)


@login_required
def deposit_funds(request):

    form = DepositForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect("deposit_page")

    try:
        currency = form.cleaned_data["currency"]
        amount = form.cleaned_data["amount"]
        settings = PrestigeSettings.load()

        address_lookup = {
            "BTC": settings.deposit_btc_address,
            "ETH": settings.deposit_eth_address,
            "USDT": settings.deposit_usdt_address,
        }
        deposit_address = address_lookup.get(currency)

        if not deposit_address:
            messages.error(request, f"No deposit address configured for {currency}")
            return redirect("deposit_page")

        account = Account.objects.get(customer=request.user, account_type="INVESTMENT")

        transaction_id = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=12)
        )
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
            user=request.user,
            event_type="DEPOSIT_INITIATED",
            ip_address=request.META.get("REMOTE_ADDR"),
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
    except Account.DoesNotExist:
        messages.error(request, "Investment account not found")
    except Exception as e:
        messages.error(request, f"Error processing deposit: {str(e)}")

    return redirect("deposit_page")


@login_required
def withdraw_fund(request):
    account = Account.objects.filter(customer=request.user).first()

    if request.method == "POST":
        try:
            currency = request.POST.get("currency")
            amount = Decimal(request.POST.get("amount", 0))
            user_address = request.POST.get("userAddress")

            if amount <= 0:
                messages.error(request, "Enter a valid amount")
                return redirect("withdraw_fund")

            if account.balance < amount:
                messages.error(request, "Insufficient Balance")
                return redirect("withdraw_fund")

            with transaction.atomic():
                Transaction.objects.create(
                    account=account,
                    transaction_type="WITHDRAWAL",
                    amount=amount,
                    currency=currency,
                    wallet_address=user_address,
                    status="PENDING",
                )
                account.balance -= amount
                account.save()

            messages.success(
                request,
                "Your withdrawal request has been submitted and will be processed within 24 hours",
            )
        except Exception as e:
            messages.error(request, f"Error processing withdrawal: {str(e)}")

    withdrawals = Transaction.objects.filter(
        account__customer=request.user, transaction_type="WITHDRAWAL"
    ).order_by("-timestamp")

    context = {
        "account": account,
        "withdrawals": withdrawals,
        "completed_withdrawals": withdrawals.filter(status="COMPLETED").count(),
        "pending_withdrawals": withdrawals.filter(status="PENDING").count(),
        "total_withdrawals": withdrawals.filter(status="COMPLETED").aggregate(
            Sum("amount")
        )["amount__sum"]
        or 0,
    }
    return render(request, "main/withdraw_fund.html", context)


@login_required
def support_chat(request):
   
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-updated_at")

    active_ticket_id = request.GET.get("ticket_id")
    active_ticket = None

    if active_ticket_id:
        try:
            active_ticket = tickets.get(id=active_ticket_id)
        except SupportTicket.DoesNotExist:
            pass

    # Check if any admin is online
    admin_online = UserStatus.objects.filter(
        user__is_staff=True, status="ONLINE"
    ).exists()

    context = {
        "tickets": tickets,
        "active_ticket": active_ticket,
        "admin_online": admin_online,
    }

    return render(request, "main/support.html", context)


@csrf_exempt
def create_ticket(request):
    prestige_settings = PrestigeSettings.load()
    if request.method == "POST":
        try:
            subject = request.POST.get("subject", "General Support")
            priority = request.POST.get("priority", "MEDIUM")
            message = request.POST.get("message", "")

            ticket = SupportTicket.objects.create(
                user=request.user, subject=subject, priority=priority
            )

            support_message = SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                receiver=prestige_settings,
                message=message,
            )

            # Handle file uploads if needed

            return JsonResponse(
                {
                    "success": True,
                    "ticket_id": ticket.id,
                    "redirect_url": f"/support/?ticket_id={ticket.id}",
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method"})


@login_required
def get_ticket_messages(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
        messages = ticket.messages.all().order_by("created_at")

        messages_data = []
        print(messages_data, "Message data")
        for message in messages:
            messages_data.append(
                {
                    "id": message.id,
                    "message": message.message,
                    "image": message.image.url if message.image else None,
                    "file": {
                        "url": message.file.url if message.file else None,
                        "name": message.file.name if message.file else None,
                    },
                    "sender": {
                        "id": message.sender.id,
                        "name": message.sender.get_full_name(),
                        "is_me": message.sender == request.user,
                        "is_staff": message.sender.is_staff,
                    },
                    "created_at": message.created_at.strftime("%H:%M"),
                    "is_read": message.is_read,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "messages": messages_data,
                "ticket": {
                    "id": ticket.id,
                    "subject": ticket.subject,
                    "status": ticket.get_status_display(),
                },
                "admin_online": UserStatus.objects.filter(
                    user__is_staff=True, status="ONLINE"
                ).exists(),
            }
        )
    except SupportTicket.DoesNotExist:
        return JsonResponse({"success": False, "error": "Ticket not found"})


@login_required
@csrf_exempt
def send_message(request, ticket_id):
    prestige_setting = PrestigeSettings.load()
    if request.method == "POST":
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            message_text = request.POST.get("message")
            image = request.FILES.get("image")
            file = request.FILES.get("file")

            message = SupportMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                receiver=prestige_setting,
                message=message_text,
                image=image,
                file=file,
            )
            print(message, "Messages here ")

            if ticket.status in ["RESOLVED", "CLOSED"]:
                ticket.status = "IN_PROGRESS"
                ticket.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": {
                        "id": message.id,
                        "text": message_text,
                        "image": message.image.url if message.image else None,
                        "file": {
                            "url": message.file.url if message.file else None,
                            "name": message.file.name if message.file else None,
                        },
                        "sender": request.user.get_full_name(),
                        "is_me": True,
                        "created_at": message.created_at.strftime("%H:%M"),
                    },
                }
            )
        except SupportTicket.DoesNotExist:
            return JsonResponse({"success": False, "error": "Ticket not found"})

    return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
def close_ticket(request, ticket_id):
    if request.method == "POST":
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, user=request.user)
            ticket.status = "CLOSED"
            ticket.save()
            return JsonResponse({"success": True})
        except SupportTicket.DoesNotExist:
            return JsonResponse({"success": False, "error": "Ticket not found"})

    return JsonResponse({"success": False, "error": "Invalid request"})


@user_passes_test(admin_required)
def admin_dashboard(request):

    one_week_ago = timezone.now() - timedelta(days=7)

    recent_chats = []
    tickets = (
        SupportTicket.objects.filter(
            Q(messages__created_at__gte=one_week_ago) | Q(created_at__gte=one_week_ago)
        )
        .select_related("user")
        .prefetch_related("messages")
        .distinct()
    )

    for ticket in tickets.order_by("-updated_at")[:10]:
        last_message = ticket.messages.order_by("-created_at").first()
        unread_count = ticket.messages.filter(is_read=False, sender=ticket.user).count()

        recent_chats.append(
            {
                "ticket_id": ticket.id,
                "user": ticket.user,
                "subject": ticket.subject,
                "last_message": (
                    last_message.message if last_message else "No messages yet"
                ),
                "last_message_time": (
                    last_message.created_at if last_message else ticket.created_at
                ),
                "unread_count": unread_count,
                "status": ticket.status,
            }
        )

    # Financial data
    total_transactions = (
        Transaction.objects.filter(status="COMPLETED").aggregate(total=Sum("amount"))[
            "total"
        ]
        or 0
    )

    total_withdrawals = (
        Transaction.objects.filter(
            transaction_type="WITHDRAWAL", status="COMPLETED"
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    pending_transactions_list = (
        Transaction.objects.filter(status="PENDING")
        .select_related("account__customer")
        .order_by("-created_at")[:10]
    )

    context = {
        "total_transactions": total_transactions,
        "total_withdrawals": total_withdrawals,
        "total_users": User.objects.count(),
        "pending_transactions": Transaction.objects.filter(status="PENDING").count(),
        "pending_transactions_list": pending_transactions_list,
        "recent_chats": recent_chats,
    }
    return render(request, "main/dashboard_admin.html", context)


def credit_transaction(request, trans_id):
    transaction = get_object_or_404(Transaction, id=trans_id)
    transaction.status = "COMPLETED"
    transaction.save()

    transaction.account.balance += transaction.amount
    transaction.account.save()
    messages.success(request, "Account Credited Successfully")
    return redirect("admin_dashboard")


def delete_transaction(request, trans_id):
    transaction = get_object_or_404(Transaction, id=trans_id)
    transaction.delete()
    messages.success(request, "Account Deleted Successfully")
    return redirect("admin_dashboard")


@login_required
def process_transaction(request, transaction_id, action):
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        if action == "credit":
            with transaction.atomic():
                transaction.status = "COMPLETED"
                transaction.save()

                transaction.account.balance += transaction.amount
                transaction.account.save()

                return JsonResponse(
                    {"success": True, "message": "Transaction credited successfully"}
                )

        elif action == "delete":
            with transaction.atomic():
                transaction.delete()
                return JsonResponse(
                    {"success": True, "message": "Transaction deleted successfully"}
                )

        return JsonResponse({"success": False, "error": "Invalid action"}, status=400)
    except Transaction.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Transaction not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def is_admin(user):
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin)
def trade_list(request):
    trades = TradePosition.objects.all().order_by("-opened_at")

    status = request.GET.get("status")
    trade_type = request.GET.get("type")
    symbol = request.GET.get("symbol")
    search = request.GET.get("search")

    if status:
        trades = trades.filter(status=status)
    if trade_type:
        trades = trades.filter(trade_type=trade_type)
    if symbol:
        trades = trades.filter(symbol__icontains=symbol)
    if search:
        trades = trades.filter(
            Q(symbol__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )

    total_trades = TradePosition.objects.count()
    trades_this_month = TradePosition.objects.filter(
        opened_at__gte=now().replace(day=1)
    ).count()

    total_profit_loss = (
        TradePosition.objects.aggregate(total=models.Sum("profit_loss"))["total"] or 0
    )

    open_trades = TradePosition.objects.filter(status="OPEN").count()
    open_trades_today = TradePosition.objects.filter(
        status="OPEN", opened_at__date=now().date()
    ).count()

    pending_trades = TradePosition.objects.filter(status="PENDING").count()
    pending_trades_today = TradePosition.objects.filter(
        status="PENDING", opened_at__date=now().date()
    ).count()

    paginator = Paginator(trades, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "trades": page_obj,
        "total_trades": total_trades,
        "trades_this_month": trades_this_month,
        "total_profit_loss": total_profit_loss,
        "open_trades": open_trades,
        "open_trades_today": open_trades_today,
        "pending_trades": pending_trades,
        "pending_trades_today": pending_trades_today,
    }
    return render(request, "main/dash_trade.html", context)


@login_required
def get_trade_json(request, trade_id):
    try:
        trade = TradePosition.objects.get(id=trade_id)
        return JsonResponse(
            {
                "success": True,
                "trade": {
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "trade_type": trade.trade_type,
                    "amount": str(trade.amount),
                    "leverage": trade.leverage,
                    "entry_price": str(trade.entry_price),
                    "current_price": str(trade.current_price),
                    "take_profit": str(trade.take_profit),
                    "stop_loss": str(trade.stop_loss),
                    "status": trade.status,
                    "status_display": trade.get_status_display(),
                    "profit_loss": str(trade.profit_loss),
                },
            }
        )
    except TradePosition.DoesNotExist:
        return JsonResponse({"success": False, "error": "Trade not found"}, status=404)


@login_required
@user_passes_test(is_admin)
def update_trade(request):
    if request.method == "POST":
        try:
            trade = TradePosition.objects.get(id=request.POST.get("trade_id"))

            # Update trade fields
            trade.symbol = request.POST.get("symbol")
            trade.trade_type = request.POST.get("trade_type")
            trade.amount = request.POST.get("amount")
            trade.leverage = request.POST.get("leverage")
            trade.entry_price = request.POST.get("entry_price")
            trade.current_price = request.POST.get("current_price")
            trade.take_profit = request.POST.get("take_profit")
            trade.stop_loss = request.POST.get("stop_loss")
            trade.status = request.POST.get("status")

            # Recalculate P/L
            trade.calculate_profit_loss()

            trade.save()

            return JsonResponse(
                {
                    "success": True,
                    "trade": {
                        "id": trade.id,
                        "symbol": trade.symbol,
                        "trade_type": trade.trade_type,
                        "amount": str(trade.amount),
                        "leverage": trade.leverage,
                        "entry_price": str(trade.entry_price),
                        "current_price": str(trade.current_price),
                        "take_profit": str(trade.take_profit),
                        "stop_loss": str(trade.stop_loss),
                        "status": trade.status,
                        "status_display": trade.get_status_display(),
                        "profit_loss": str(trade.profit_loss),
                    },
                }
            )
        except TradePosition.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Trade not found"}, status=404
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    return JsonResponse(
        {"success": False, "error": "Invalid request method"}, status=405
    )


@user_passes_test(is_admin)
def delete_trade(request, trade_id):
    if request.method == "POST":
        try:
            trade = TradePosition.objects.get(id=trade_id)
            trade.delete()
            return JsonResponse({"success": True})
        except TradePosition.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Trade not found"}, status=404
            )
    return JsonResponse(
        {"success": False, "error": "Invalid request method"}, status=405
    )


@login_required
def get_ticket_chat(request, ticket_id):
    """Get messages for a specific ticket"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    SupportMessage.objects.filter(
        ticket=ticket, is_read=False, sender__is_staff=False
    ).update(is_read=True)

    messages = ticket.messages.select_related("sender").order_by("created_at")

    messages_data = [
        {
            "id": msg.id,
            "message": msg.message,
            "sender_id": msg.sender.id,
            "sender_name": msg.sender.get_full_name(),
            "is_admin": msg.sender.is_staff,
            "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": msg.is_read,
        }
        for msg in messages
    ]

    return JsonResponse(
        {
            "status": "success",
            "ticket": {
                "id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.get_status_display(),
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "user": {
                "id": ticket.user.id,
                "name": ticket.user.get_full_name(),
                "email": ticket.user.email,
            },
            "messages": messages_data,
        }
    )


@login_required
def send_reply(request, ticket_id):
    """Handle admin replies to tickets"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    data = json.loads(request.body)

    message = SupportMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        message=data.get("message"),
        is_read=False,  # Message to customer is unread by default
    )

    # Update ticket status if needed
    if ticket.status == "OPEN":
        ticket.status = "IN_PROGRESS"
        ticket.save()

    return JsonResponse(
        {
            "status": "success",
            "message": {
                "id": message.id,
                "text": message.message,
                "sender": request.user.get_full_name(),
                "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
    )


@login_required
def get_recent_chats(request):
    """Get recent chats for the sidebar"""
    one_week_ago = timezone.now() - timedelta(days=7)

    recent_chats = (
        SupportTicket.objects.filter(
            Q(messages__created_at__gte=one_week_ago) | Q(created_at__gte=one_week_ago)
        )
        .select_related("user")
        .annotate(
            last_message_time=Max("messages__created_at"),
            last_message_text=Max("messages__message"),
            unread_count=Count(
                "messages",
                filter=Q(
                    messages__is_read=False,
                    messages__sender__is_staff=False,
                ),
            ),
        )
        .order_by("-last_message_time")[:10]
    )

    chats_data = [
        {
            "ticket_id": chat.id,
            "user_id": chat.user.id,
            "user_name": chat.user.get_full_name(),
            "subject": chat.subject,
            "last_message": chat.last_message_text,
            "last_message_time": (
                chat.last_message_time.strftime("%Y-%m-%d %H:%M:%S")
                if chat.last_message_time
                else None
            ),
            "unread_count": chat.unread_count,
        }
        for chat in recent_chats
    ]

    return JsonResponse(
        {
            "status": "success",
            "chats": chats_data,
        }
    )


def admin_required(user):
    return user.is_staff or user.is_superuser


@user_passes_test(admin_required)
def edit_trade(request, trade_id):
    trade = get_object_or_404(TradePosition, id=trade_id)
    if request.method == "POST":
        profit = request.POST.get("profit_loss")
        status = request.POST.get("status")
        if profit is not None:
            trade.profit_loss = profit
        if status and status in dict(TradePosition.STATUS_CHOICES):
            trade.status = status
        trade.save()
        if request.is_ajax():
            return JsonResponse(
                {
                    "success": True,
                    "profit_loss": str(trade.profit_loss),
                    "status": trade.get_status_display(),
                }
            )
        return redirect("trade_list")

    return JsonResponse(
        {
            "id": trade.id,
            "profit_loss": str(trade.profit_loss),
            "status": trade.status,
        }
    )


@user_passes_test(admin_required)
def hide_trade(request, trade_id):
    trade = get_object_or_404(TradePosition, id=trade_id)
    if request.method == "POST":
        trade.hidden = True
        trade.save()
    return redirect("trade_list")


def referal_code(request):

    setting = PrestigeSettings.load() 
    form = SettingForm()

    prestige_settings = PrestigeSettings.load()

    referal_codes = ReferalCode.objects.all()

    return render(request, "main/referal_code.html", {"referal_codes": referal_codes, 'prestige_settings':prestige_settings, 'form':form, 'setting':setting if setting else None})


def edit_setting(request, setting_id=None):
    setting = get_object_or_404(PrestigeSettings, id=setting_id) if setting_id else None
    
    if request.method == 'POST':
        form = SettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings were successfully updated!')
            return redirect('referal_code')  # 
    else:
        form = SettingForm(instance=setting)
    
    context = {
        'form': form,
        'setting': setting,
        'title': 'Edit Settings'
    }
    return render(request, 'main/referal_code.html', context)


def generate_code(request):
    if request.method == "POST":
        name = request.POST["name"]

        code = ReferalCode.objects.create(name=name)
        messages.success(request, "Code Created Successfully")
        return redirect("referal_code")


@user_passes_test(admin_required)
def ticket_messages(request, ticket_id):
    try:
        ticket = SupportTicket.objects.get(id=ticket_id)
        messages = ticket.messages.all().order_by("created_at")
        data = [
            {
                "message": msg.message,
                "created_at": msg.created_at.isoformat(),
                "is_admin": msg.sender.is_staff,
            }
            for msg in messages
        ]
        return JsonResponse(data, safe=False)
    except SupportTicket.DoesNotExist:
        return JsonResponse({"error": "Ticket not found"}, status=404)


def dash_withdrawal(request):
    transactions = Transaction.objects.filter(transaction_type="WITHDRAWAL")

    context = {"transactions": transactions}
    return render(request, "main/dash_withdraws.html", context)


def approve_withdrawals(request, transaction_id):
    trans = get_object_or_404(Transaction, id=transaction_id)
    trans.status = "COMPLETED"
    trans.account.balance += trans.amount
    trans.save()
    trans.account.save()
    messages.success(request, "Transaction Approved Successfully")
    return redirect("dash_withdrawal")


def reject_withdrawals(request, transaction_id):
    trans = get_object_or_404(Transaction, id=transaction_id)
    trans.delete()
    messages.success(request, "Transaction Rejected ")
    return redirect("dash_withdrawal")


@require_POST
def send_ticket_message(request, ticket_id):
    cus_support = PrestigeSettings.load()
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    message_text = request.POST.get('message', '').strip()
    
    if not message_text:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'})

    message = SupportMessage.objects.create(
        ticket=ticket,
        sender=ticket.user,
        receiver=cus_support,  
        message=message_text,
        is_read=False
    )
    
   
    if ticket.status in ['RESOLVED', 'CLOSED']:
        ticket.status = 'IN_PROGRESS'
        ticket.save()
    
    return JsonResponse({
        'success': True,
        'message_id': message.id,
        'created_at': message.created_at.strftime("%b %d, %Y %I:%M %p"),
        'sender_name': request.user.get_full_name(),
        'sender_initials': request.user.get_full_name()[:2].upper()
    })


@login_required
def get_ticket_messages_new(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    SupportMessage.objects.filter(
        ticket=ticket,
        sender=ticket.user,
        is_read=False
    ).update(is_read=True)
    
    messages = ticket.messages.select_related('sender').order_by('created_at')
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'message': msg.message,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.get_full_name(),
            'sender_initials': msg.sender.get_full_name()[:2].upper(),
            'created_at': msg.created_at.strftime("%b %d, %Y %I:%M %p"),
            'is_support': msg.sender != ticket.user,
            'image': msg.image.url if msg.image else None,
            'file': msg.file.url if msg.file else None
        })
    
    return JsonResponse({
        'success': True,
        'messages': messages_data,
        'ticket_status': ticket.status,
        'ticket_subject': ticket.subject,
        'user_name': ticket.user.get_full_name(),
        'user_initials': ticket.user.get_full_name()[:2].upper()
    })