from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum
from decimal import Decimal
import random
import string
from .models import (
    Account,
    InvestmentPackage,
    Investment,
    TradePosition,
    Transaction,
    SecurityLog,
    PrestigeSettings,
    SupportTicket,
    SupportChat
)
from .forms import (
    LoginForm,
    DepositForm,
    InvestmentForm,
    OpenTradeForm,
    SupportTicketForm,
    SupportChatForm
)

User = get_user_model()

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(email=form.cleaned_data["email"], password=form.cleaned_data["password"])
            if user:
                login(request, user)
                SecurityLog.objects.create(
                    user=user,
                    event_type="LOGIN",
                    ip_address=request.META.get("REMOTE_ADDR"),
                    device_info={"user_agent": request.META.get("HTTP_USER_AGENT")},
                    details="Standard password authentication",
                )
                return redirect("trade_investment_dashboard")
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

@login_required
def trade_investment_dashboard(request):
    user = request.user
    bank_settings = PrestigeSettings.load()
    account = Account.objects.filter(customer=user).first()

    context = {
        "investment_balance": account.balance if account else 0,
        "active_trades": TradePosition.objects.filter(user=user, status="OPEN").count(),
        "pending_trades": TradePosition.objects.filter(user=user, status="PENDING").count(),
        "total_profit": TradePosition.objects.filter(user=user, status="CLOSED").aggregate(
            Sum("profit_loss"))["profit_loss__sum"] or Decimal("0.00"),
        "has_active_investment": Investment.objects.filter(
            account__customer=user, status="ACTIVE").exists(),
        "packages": InvestmentPackage.objects.all(),
        "active_positions": TradePosition.objects.filter(user=user, status="OPEN").order_by("-opened_at"),
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

    if form.is_valid():
        try:
            with transaction.atomic():
                account = Account.objects.get(customer=user, account_type="INVESTMENT")
                data = form.cleaned_data
                margin_required = data["amount"] / data["leverage"]

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
                    transaction_id=''.join(random.choices(string.ascii_uppercase + string.digits, k=12)),
                    transaction_type="TRADE",
                    amount=margin_required,
                    description=f"{data['trade_type']} position on {data['symbol']}",
                    trade_position=position,
                )

               
                messages.success(request, f"✅ Trade opened successfully! Position ID: {position.id}")
                return redirect("trade_investment_dashboard")

        except Account.DoesNotExist:
            messages.error(request, "Investment account not found")
    else:
        for error in form.errors.values():
            messages.error(request, error[0])
    return redirect("trade_investment_dashboard")

@login_required
def close_trade(request, position_id):
    try:
        position = TradePosition.objects.get(id=position_id, user=request.user, status="OPEN")
        account = Account.objects.get(customer=request.user, account_type="INVESTMENT")

        with transaction.atomic():
            position.calculate_profit_loss()
            position.status = "CLOSED"
            position.closed_at = timezone.now()
            position.save()

            amount_to_return = position.margin_required + position.profit_loss
            account.balance += amount_to_return
            account.save()

            Transaction.objects.create(
                account=account,
                transaction_id=''.join(random.choices(string.ascii_uppercase + string.digits, k=12)),
                transaction_type="TRADE_CLOSE",
                amount=amount_to_return,
                description=f"Closed {position.get_trade_type_display()} position",
                trade_position=position,
            )

            SecurityLog.objects.create(
                user=request.user,
                event_type="TRADE_CLOSED",
                details=f"Closed trade on {position.symbol}",
            )
            messages.success(request, f"✅ Position closed! Profit/Loss: ${position.profit_loss:.2f}")

    except TradePosition.DoesNotExist:
        messages.error(request, "Position not found or already closed")
    except Account.DoesNotExist:
        messages.error(request, "Investment account not found")

    return redirect("trade_investment_dashboard")

@login_required
def create_investment(request):
    form = InvestmentForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                account = Account.objects.get(customer=request.user, account_type="INVESTMENT")
                package = form.cleaned_data["package"]
                amount = form.cleaned_data["amount"]

                if not package.min_amount <= amount <= package.max_amount:
                    messages.error(request, f"Amount must be between ${package.min_amount} and ${package.max_amount}")
                    return redirect("trade_investment_dashboard")

                if amount > account.balance:
                    messages.error(request, "Insufficient funds for this investment")
                    return redirect("trade_investment_dashboard")

                investment = Investment.objects.create(
                    account=account,
                    package=package,
                    amount=amount,
                )
                account.balance -= amount
                account.save()

                messages.success(request, "Investment created successfully!")
        except Account.DoesNotExist:
            messages.error(request, "Account not found")
    else:
        for error in form.errors.values():
            messages.error(request, error[0])
    return redirect("trade_investment_dashboard")

@login_required
def deposit_page(request):
    account = Account.objects.filter(customer=request.user).first()
    deposits = Transaction.objects.filter(
        account__customer=request.user, transaction_type="DEPOSIT"
    ).order_by("-timestamp")

    context = {
        "deposits": deposits,
        "total_deposited": deposits.filter(status="COMPLETED").aggregate(Sum("amount"))["amount__sum"] or 0,
        "completed_deposits": deposits.filter(status="COMPLETED").count(),
        "pending_deposits": deposits.filter(status="PENDING").count(),
        "deposit_form": DepositForm(),
        "account": account,
    }
    return render(request, "main/deposit.html", context)

@login_required
def support_page(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
    active_ticket_id = request.GET.get("ticket")
    active_ticket = None

    if active_ticket_id:
        try:
            active_ticket = SupportTicket.objects.get(id=active_ticket_id, user=request.user)
        except SupportTicket.DoesNotExist:
            messages.error(request, "Ticket not found")

    if not active_ticket and tickets.exists():
        active_ticket = tickets.first()

    return render(request, "main/support.html", {
        "tickets": tickets,
        "active_ticket": active_ticket,
    })

@login_required
@require_POST
def create_ticket(request):
    form = SupportTicketForm(request.POST, user=request.user)
    if form.is_valid():
        ticket = form.save()
        SupportChat.objects.create(
            ticket=ticket,
            user=request.user,
            message=form.cleaned_data['message']
        )
        return JsonResponse({'success': True, 'ticket_id': ticket.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def send_message(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    form = SupportChatForm(request.POST, request.FILES)
    
    if form.is_valid():
        chat = form.save(commit=False)
        chat.ticket = ticket
        chat.user = request.user
        chat.save()

        if ticket.status == "OPEN":
            ticket.status = "IN_PROGRESS"
            ticket.save()

        return JsonResponse({
            "success": True,
            "message": {
                "id": chat.id,
                "text": chat.message,
                "image_url": chat.image.url if chat.image else None,
                "file_url": chat.file.url if chat.file else None,
                "created_at": chat.created_at.strftime("%H:%M"),
                "sender": "You",
            },
        })
    return JsonResponse({"success": False, "errors": form.errors}, status=400)

@login_required
def get_new_messages(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    last_message_id = request.GET.get("last_message_id", 0)

    messages = (
        SupportChat.objects.filter(ticket=ticket, id__gt=last_message_id)
        .exclude(user=request.user)
        .order_by("created_at")
    )

    messages_data = [{
        "id": msg.id,
        "text": msg.message,
        "image_url": msg.image.url if msg.image else None,
        "file_url": msg.file.url if msg.file else None,
        "created_at": msg.created_at.strftime("%H:%M"),
        "sender": "Support Agent",
    } for msg in messages]

    last_id = messages.last().id if messages else last_message_id
    return JsonResponse({"messages": messages_data, "last_message_id": last_id})

@login_required
def close_ticket(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    ticket.status = "CLOSED"
    ticket.save()
    return redirect("support_page")

@login_required
def withdraw_fund(request):

    account = Account.objects.filter(customer=request.user).first()

    if request.method == 'POST':
        currency = request.POST.get('currency')
        amount = request.POST.get('amount')
        user_address = request.POST.get('userAddress')

        if amount <0:
            messages.error(request, 'Enter a valid amount')
            return redirect('withdraw_fund')
        
        transaction = Transaction.objects.create(
            account=account, transaction_type='WITHDRAWAL',
            amount=amount, currency=currency, wallet_address=user_address, status='status'
        )
        account.balance-=transaction.amount
        account.save()
        messages.success(request, 'Your account would be credited with in 24 hours')


    withdrawals = Transaction.objects.filter(
        account__customer=request.user, transaction_type="WITHDRAWAL"
    ).order_by("-timestamp")

    context = {
        "account": account,
        "withdrawals": withdrawals,
        "completed_withdrawals": withdrawals.filter(status="COMPLETED").count(),
        "pending_withdrawals": withdrawals.filter(status="PENDING").count(),
        "total_withdrawals": withdrawals.filter(status="COMPLETED").aggregate(Sum("amount"))["amount__sum"] or 0,
    }
    return render(request, "main/withdraw_fund.html", context)

@login_required
def admin_dashboard(request):
    context = {
        'total_transactions': Transaction.objects.filter(status='COMPLETED').aggregate(Sum('amount'))['amount__sum'] or 0,
        'total_withdrawals': Transaction.objects.filter(transaction_type='WITHDRAWAL', status='COMPLETED').aggregate(Sum('amount'))['amount__sum'] or 0,
        'total_users': User.objects.count(),
        'pending_transactions': Transaction.objects.filter(status='PENDING').count(),
        'pending_transactions_list': Transaction.objects.filter(status='PENDING').select_related('account__customer').order_by('-created_at')[:10],
        'recent_chats': SupportChat.objects.order_by().values_list('user_id', flat=True).distinct()[:10],
    }
    return render(request, 'main/dashboard_admin.html', context)

@login_required
def get_chat_history(request, user_id):
    try:
        messages = SupportChat.objects.filter(user_id=user_id).order_by('created_at')
        messages_data = [{
            'id': msg.id,
            'user_id': msg.user.id,
            'user_name': msg.user.username,
            'message': msg.message,
            'image': msg.image.url if msg.image else None,
            'file': msg.file.url if msg.file else None,
            'created_at': msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'is_admin': msg.user.is_staff,
        } for msg in messages]
        return JsonResponse({'messages': messages_data})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@login_required
@require_POST
def send_general_message(request):
    form = SupportChatForm(request.POST, request.FILES)
    if form.is_valid():
        chat = form.save(commit=False)
        chat.user = request.user
        chat.save()
        return JsonResponse({'success': True, 'message_id': chat.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def get_new_general_messages(request):
    last_message_id = request.GET.get('last_message_id', 0)
    messages = SupportChat.objects.filter(
        id__gt=last_message_id,
        ticket__isnull=True
    ).exclude(user=request.user).order_by('created_at')

    messages_data = [{
        "id": msg.id,
        "text": msg.message,
        "image_url": msg.image.url if msg.image else None,
        "file_url": msg.file.url if msg.file else None,
        "created_at": msg.created_at.strftime("%H:%M"),
    } for msg in messages]

    last_id = messages.last().id if messages else last_message_id
    return JsonResponse({"messages": messages_data, "last_message_id": last_id})


@login_required
def get_market_data(request, symbol):
    try:
        # Mock market data - replace with actual market data implementation
        base_price = {
            "BTCUSDT": Decimal("55000.00"),
            "ETHUSDT": Decimal("3000.00"),
            "BNBUSDT": Decimal("500.00"),
            "SOLUSDT": Decimal("100.00"),
            "XRPUSDT": Decimal("0.50"),
        }.get(symbol, Decimal("10000.00"))

        price = base_price * Decimal(1 + random.uniform(-0.02, 0.02)).quantize(Decimal("0.01"))
        change = Decimal(random.uniform(-3, 3)).quantize(Decimal("0.01"))
        high = price * Decimal(1 + random.uniform(0.01, 0.03)).quantize(Decimal("0.01"))
        low = price * Decimal(1 - random.uniform(0.01, 0.03)).quantize(Decimal("0.01"))
        volume = round(random.uniform(1000000, 50000000))

        return JsonResponse({
            "success": True,
            "symbol": symbol,
            "price": float(price),
            "change": float(change),
            "high": float(high),
            "low": float(low),
            "volume": volume,
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
    


@login_required
def deposit_funds(request):
    user = request.user
    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
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

            try:
                account = Account.objects.get(customer=user, account_type="INVESTMENT")
            except Account.DoesNotExist:
                messages.error(request, "Investment account not found")
                return redirect("deposit_page")

            transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
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

    return redirect("deposit_page")


@login_required
def process_transaction(request, transaction_id, action):

    user_transction = get_object_or_404(Transaction, id=transaction_id)
    try:
   
        
        if action == 'credit':
       
            with transaction.atomic():
                user_transction.status = 'COMPLETED'
                user_transction.save()
                
            
                user_transction.account.balance += user_transction.amount
                user_transction.account.save()
                
               
                
                return JsonResponse({
                    'success': True,
                    'message': 'Transaction credited successfully'
                })
                
        elif action == 'delete':
            with transaction.atomic():
                transaction.delete()
                SecurityLog.objects.create(
                    user=request.user,
                    event_type="TRANSACTION_DELETED",
                    details=f"Deleted transaction {transaction_id}",
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Transaction deleted successfully'
                })
                
        else:
            return JsonResponse({
                'error': 'Invalid action'
            }, status=400)
            
    except Transaction.DoesNotExist:
        return JsonResponse({
            'error': 'Transaction not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)














