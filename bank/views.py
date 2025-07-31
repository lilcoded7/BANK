# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from .models import *
from .forms import LoginForm, TransferForm, MobileMoneyForm, SecuritySettingsForm
from django.db.models import Sum
from .models import (
    Account, InvestmentPackage, Investment, TradePosition, 
    Transaction, SecurityLog, PrestigeSettings
)
from decimal import Decimal
import random
import string
from django.http import JsonResponse
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


@login_required
def dashboard(request):
    accounts = Account.objects.filter(customer=request.user, status="ACTIVE")
    total_balance = sum(account.balance for account in accounts)

    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=request.user)
        | Q(recipient_account__customer=request.user)
    ).order_by("-timestamp")[:5]

    context = {
        "user": request.user,
        "accounts": accounts,
        "total_balance": total_balance,
        "recent_transactions": recent_transactions,
        "has_biometric": getattr(request.user, "is_biometric_enabled", False),
    }
    return render(request, "main/dashboard.html", context)



@login_required
def trade_investment(request):
    user = request.user
    
    # Get investment account
    try:
        investment_account = Account.objects.get(
            customer=user,
            account_type="INVESTMENT"
        )
    except Account.DoesNotExist:
        # Create investment account if doesn't exist
        investment_account = Account.objects.create(
            customer=user,
            account_type="INVESTMENT",
            balance=0.00,
            currency="GHS",
            status="ACTIVE"
        )
    
    # Calculate investment metrics
    investment_balance = investment_account.balance
    active_trades = TradePosition.objects.filter(user=user, status="OPEN").count()
    pending_trades = TradePosition.objects.filter(user=user, status="PENDING").count()
    
    # Calculate total profit from closed trades
    total_profit = TradePosition.objects.filter(
        user=user, 
        status="CLOSED"
    ).aggregate(Sum('profit_loss'))['profit_loss__sum'] or Decimal('0.00')
    
    # Check if user has active investments
    has_active_investment = Investment.objects.filter(
        account=investment_account,
        status="ACTIVE"
    ).exists()
    
    # Get investment packages
    packages = InvestmentPackage.objects.all()
    
    # Get active positions with current prices
    active_positions = TradePosition.objects.filter(
        user=user,
        status="OPEN"
    ).order_by('-opened_at')
    
    # Update positions with current prices (simulated)
    for position in active_positions:
        # In a real app, get from market API
        position.current_price = position.entry_price * Decimal(1 + random.uniform(-0.05, 0.05))
        position.calculate_profit_loss()
    
    # Get bank settings
    bank_settings = PrestigeSettings.load()
    
    # Log security event
    SecurityLog.objects.create(
        user=user,
        event_type="TRADE_EXECUTED",
        ip_address=request.META.get('REMOTE_ADDR'),
        device_info={"user_agent": request.META.get('HTTP_USER_AGENT')},
        details="Accessed Trade Investment Dashboard"
    )
    
    context = {
        'investment_balance': investment_balance,
        'active_trades': active_trades,
        'pending_trades': pending_trades,
        'total_profit': total_profit,
        'has_active_investment': has_active_investment,
        'packages': packages,
        'active_positions': active_positions,
        'accounts': Account.objects.filter(customer=user),
        'bank_settings': bank_settings,
    }
    
    return render(request, 'trade_investment.html', context)

@login_required
def open_trade(request):
    if request.method == 'POST':
        user = request.user
        bank_settings = PrestigeSettings.load()
        
        # Extract form data
        symbol = request.POST.get('symbol')
        trade_type = request.POST.get('trade_type')
        amount = Decimal(request.POST.get('amount', 0))
        leverage = int(request.POST.get('leverage', 1))
        take_profit = Decimal(request.POST.get('take_profit', 0))
        stop_loss = Decimal(request.POST.get('stop_loss', 0))
        entry_price = Decimal(request.POST.get('entry_price', 0))
        
        # Validate minimum amount
        if amount < bank_settings.min_trade_amount:
            messages.error(request, f"Minimum trade amount is ${bank_settings.min_trade_amount}")
            return redirect('trade_investment')
        
        # Validate leverage
        if leverage > bank_settings.max_leverage:
            messages.error(request, f"Maximum leverage is {bank_settings.max_leverage}x")
            return redirect('trade_investment')
        
        # Get investment account
        try:
            account = Account.objects.get(
                customer=user,
                account_type="INVESTMENT"
            )
        except Account.DoesNotExist:
            messages.error(request, "No investment account found")
            return redirect('trade_investment')
        
        # Check sufficient balance
        margin_required = amount / leverage
        if account.balance < margin_required:
            messages.error(request, "Insufficient funds for margin requirement")
            return redirect('trade_investment')
        
        # Create trade position
        position = TradePosition.objects.create(
            user=user,
            symbol=symbol,
            trade_type=trade_type,
            amount=amount,
            leverage=leverage,
            entry_price=entry_price,
            current_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        # Update account balance (reserve margin)
        account.balance -= margin_required
        account.save()
        
        # Create transaction
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        Transaction.objects.create(
            account=account,
            transaction_id=transaction_id,
            transaction_type="TRADE",
            amount=margin_required,
            currency="GHS",
            sender_account=account,
            status="COMPLETED",
            description=f"{trade_type} position on {symbol}",
            trade_position=position
        )
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            event_type="TRADE_EXECUTED",
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info={"user_agent": request.META.get('HTTP_USER_AGENT')},
            details=f"Opened {trade_type} position on {symbol} for ${amount}"
        )
        
        messages.success(request, f"Trade opened successfully! Position ID: {position.id}")
        return redirect('trade_investment')
    
    return redirect('trade_investment')

@login_required
def close_trade(request, position_id):
    try:
        position = TradePosition.objects.get(
            id=position_id,
            user=request.user,
            status="OPEN"
        )
        
        # Calculate final profit/loss
        # In a real app, this would come from market data
        price_difference = position.current_price - position.entry_price
        if position.trade_type == "SELL":
            price_difference = -price_difference
        profit_loss = position.amount * price_difference / position.entry_price
        
        # Update position
        position.profit_loss = profit_loss
        position.status = "CLOSED"
        position.closed_at = timezone.now()
        position.save()
        
        # Get investment account
        account = Account.objects.get(
            customer=request.user,
            account_type="INVESTMENT"
        )
        
        # Calculate margin to return and profit/loss
        margin_required = position.amount / position.leverage
        amount_to_return = margin_required + profit_loss
        
        # Update account balance
        account.balance += amount_to_return
        account.save()
        
        # Create transaction
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        Transaction.objects.create(
            account=account,
            transaction_id=transaction_id,
            transaction_type="TRADE",
            amount=amount_to_return,
            currency="GHS",
            recipient_account=account,
            status="COMPLETED",
            description=f"Closed {position.get_trade_type_display()} position on {position.symbol}",
            trade_position=position
        )
        
        # Log security event
        SecurityLog.objects.create(
            user=request.user,
            event_type="TRADE_EXECUTED",
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info={"user_agent": request.META.get('HTTP_USER_AGENT')},
            details=f"Closed position {position_id}. {'Profit' if profit_loss >= 0 else 'Loss'}: ${abs(profit_loss):.2f}"
        )
        
        messages.success(request, f"Position closed. {'Profit' if profit_loss >= 0 else 'Loss'}: ${abs(profit_loss):.2f}")
        return redirect('trade_investment')
    
    except TradePosition.DoesNotExist:
        messages.error(request, "Position not found or already closed")
        return redirect('trade_investment')

@login_required
def create_investment(request):
    if request.method == 'POST':
        user = request.user
        package_id = request.POST.get('package')
        amount = Decimal(request.POST.get('amount', 0))
        
        try:
            package = InvestmentPackage.objects.get(id=package_id)
            account = Account.objects.get(
                customer=user,
                account_type="INVESTMENT"
            )
        except (InvestmentPackage.DoesNotExist, Account.DoesNotExist):
            messages.error(request, "Invalid investment request")
            return redirect('trade_investment')
        
        # Validate amount against package limits
        if amount < package.min_amount or amount > package.max_amount:
            messages.error(request, 
                f"Amount must be between ${package.min_amount} and ${package.max_amount} for this package")
            return redirect('trade_investment')
        
        # Check sufficient funds
        if account.balance < amount:
            messages.error(request, "Insufficient funds for this investment")
            return redirect('trade_investment')
        
        # Create investment
        investment = Investment.objects.create(
            account=account,
            package=package,
            amount=amount,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=package.duration_days),
            expected_return=amount * (package.roi_percentage / Decimal(100))
        )
        
        # Deduct amount from account
        account.balance -= amount
        account.save()
        
        # Create transaction
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        Transaction.objects.create(
            account=account,
            transaction_id=transaction_id,
            transaction_type="INVESTMENT",
            amount=amount,
            currency="GHS",
            sender_account=account,
            status="COMPLETED",
            description=f"Investment in {package.get_name_display()} package",
            investment=investment
        )
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            event_type="INVESTMENT_CREATED",
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info={"user_agent": request.META.get('HTTP_USER_AGENT')},
            details=f"Created {package.get_name_display()} investment for ${amount}"
        )
        
        messages.success(request, f"Investment created successfully! Expected return: ${investment.expected_return:.2f}")
        return redirect('trade_investment')
    
    return redirect('trade_investment')

@login_required
def deposit_funds(request):
    if request.method == 'POST':
        user = request.user
        from_account_id = request.POST.get('from_account')
        to_account_id = request.POST.get('to_account')
        amount = Decimal(request.POST.get('amount', 0))
        currency = request.POST.get('currency', 'BTC')
        
        try:
            from_account = Account.objects.get(id=from_account_id, customer=user)
            to_account = Account.objects.get(id=to_account_id, customer=user)
        except Account.DoesNotExist:
            messages.error(request, "Invalid account selected")
            return redirect('trade_investment')
        
        # Check sufficient funds
        if from_account.balance < amount:
            messages.error(request, "Insufficient funds in the source account")
            return redirect('trade_investment')
        
        # Get bank settings
        bank_settings = PrestigeSettings.load()
        
        # Get deposit address
        deposit_address = ""
        if currency == "BTC":
            deposit_address = bank_settings.deposit_btc_address
        elif currency == "ETH":
            deposit_address = bank_settings.deposit_eth_address
        elif currency == "USDT":
            deposit_address = bank_settings.deposit_usdt_address
        
        if not deposit_address:
            messages.error(request, "Deposit address not configured for selected currency")
            return redirect('trade_investment')
        
        # Create pending transaction
        transaction_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        transaction = Transaction.objects.create(
            account=to_account,
            transaction_id=transaction_id,
            transaction_type="DEPOSIT",
            amount=amount,
            currency=currency,
            sender_account=from_account,
            recipient_account=to_account,
            status="PENDING",
            description=f"Deposit to investment account",
            metadata={
                "deposit_address": deposit_address,
                "currency": currency,
                "expected_amount": amount
            }
        )
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            event_type="TRANSACTION",
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info={"user_agent": request.META.get('HTTP_USER_AGENT')},
            details=f"Initiated deposit of {amount} {currency} to investment account"
        )
        
        messages.info(request, 
            f"Please deposit exactly {amount} {currency} to wallet address: {deposit_address}. "
            "After deposit, contact support with your transaction ID: " + transaction_id)
        
        return redirect('trade_investment')
    
    return redirect('trade_investment')

@login_required
def get_market_data(request, symbol):
    # This would call a real market API in production
    # For now, return simulated data
    price = Decimal(random.uniform(10000, 50000)).quantize(Decimal('0.01'))
    change = Decimal(random.uniform(-5, 5)).quantize(Decimal('0.01'))
    high = price * Decimal('1.02').quantize(Decimal('0.01'))
    low = price * Decimal('0.98').quantize(Decimal('0.01'))
    volume = round(random.uniform(1000000, 50000000))
    
    return JsonResponse({
        'price': float(price),
        'change': float(change),
        'high': float(high),
        'low': float(low),
        'volume': volume
    })