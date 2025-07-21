# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from .models import Account, Transaction, SecurityLog
from .forms import LoginForm, TransferForm, MobileMoneyForm, SecuritySettingsForm
import uuid
from datetime import datetime
from django.utils import timezone

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)
                SecurityLog.objects.create(
                    user=user,
                    event_type='LOGIN',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    device_info={'user_agent': request.META.get('HTTP_USER_AGENT')},
                    details='Standard password authentication'
                )
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid email or password")
        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = LoginForm()
    return render(request, 'auth/login.html', {'form': form})

@login_required
def logout_view(request):
    SecurityLog.objects.create(
        user=request.user,
        event_type='LOGOUT',
        ip_address=request.META.get('REMOTE_ADDR'),
        details='User initiated logout'
    )
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    accounts = Account.objects.filter(customer=request.user, status='ACTIVE')
    total_balance = sum(account.balance for account in accounts)

    recent_transactions = Transaction.objects.filter(
        Q(sender_account__customer=request.user) | 
        Q(recipient_account__customer=request.user)
    ).order_by('-timestamp')[:5]

    context = {
        'user': request.user,
        'accounts': accounts,
        'total_balance': total_balance,
        'recent_transactions': recent_transactions,
        'has_biometric': getattr(request.user, 'is_biometric_enabled', False),
    }
    return render(request, 'main/dashboard.html', context)


@login_required
def transfer_funds(request):
    form = TransferForm(user=request.user)

    if request.method == 'POST':
        form = TransferForm(request.user, request.POST)
        if form.is_valid():
            try:
               
                transaction = Transaction.objects.create(
                    transaction_id=f"TX{timezone.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
                    transaction_type='TRANSFER',
                    amount=form.cleaned_data['amount'],
                    sender_account=form.cleaned_data['from_account'],
                    recipient_account=form.cleaned_data['to_account'],
                    description=form.cleaned_data['description'],
                    status='PENDING'  # Initial status
                )
                
                # Update balances (in a real app, this would be in a transaction)
                sender_account = form.cleaned_data['from_account']
                recipient_account = form.cleaned_data['to_account']
                
                sender_account.balance -= form.cleaned_data['amount']
                sender_account.save()
                
                recipient_account.balance += form.cleaned_data['amount']
                recipient_account.save()
                
                # Update transaction status
                transaction.status = 'COMPLETED'
                transaction.save()
                
                messages.success(request, "Transfer completed successfully!")
                return redirect('transfer_funds')
                
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
                if 'transaction' in locals():
                    transaction.status = 'FAILED'
                    transaction.save()

    status_filter = request.GET.get('status', 'all')
    
    transactions = Transaction.objects.filter(
        Q(sender_account__customer=request.user) | 
        Q(recipient_account__customer=request.user)
    ).order_by('-timestamp')
    
    if status_filter != 'all':
        transactions = transactions.filter(status=status_filter.upper())
    
    accounts = Account.objects.filter(customer=request.user, status='ACTIVE')
    
    total_balance = sum(account.balance for account in accounts)
    
    context = {
        'form': form,
        'accounts': accounts,
        'total_balance': total_balance,
        'transactions': transactions,
        'status_filter': status_filter,
        'user': request.user,
    }
    
    return render(request, 'main/transfer.html', context)


@login_required
def mobile_money(request):
    if request.method == 'POST':
        form = MobileMoneyForm(request.user, request.POST)
        if form.is_valid():
            transaction = Transaction.objects.create(
                transaction_id=f"MM{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
                transaction_type='MOBILE_MONEY',
                amount=form.cleaned_data['amount'],
                sender_account=form.cleaned_data['from_account'],
                recipient_number=form.cleaned_data['mobile_number'],
                description=form.cleaned_data['description'],
                status='COMPLETED',
                metadata={
                    'network': form.cleaned_data['network'],
                    'type': 'mobile_money'
                }
            )
            
            # Update balance
            form.cleaned_data['from_account'].balance -= form.cleaned_data['amount']
            form.cleaned_data['from_account'].save()
            
            # Log security event
            SecurityLog.objects.create(
                user=request.user,
                event_type='TRANSACTION',
                ip_address=request.META.get('REMOTE_ADDR'),
                details=f"Mobile money transfer of GHS {form.cleaned_data['amount']} to {form.cleaned_data['mobile_number']}"
            )
            
            messages.success(request, "Mobile money transfer completed!")
            return redirect('dashboard')
    else:
        form = MobileMoneyForm(request.user)
    
    return render(request, 'main/dashboard.html', {'form': form})


@login_required
def security_settings(request):
    user = request.user
    accounts = Account.objects.filter(customer=user, status='ACTIVE')
    
    if request.method == 'POST':
        form = SecuritySettingsForm(user, request.POST)
        if form.is_valid():
       
            if form.cleaned_data.get('new_password'):
                user.set_password(form.cleaned_data['new_password'])
                user.last_password_change = timezone.now()
                user.save()
                
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                
                messages.success(request, "Password changed successfully!")
                SecurityLog.objects.create(
                    user=user,
                    event_type='PASSWORD_CHANGE',
                    ip_address=get_client_ip(request),
                    details='Password changed successfully'
                )
            
            new_biometric_status = form.cleaned_data.get('enable_biometric', False)
            if user.is_biometric_enabled != new_biometric_status:
                user.is_biometric_enabled = new_biometric_status
                user.save()
                
                status = "enabled" if new_biometric_status else "disabled"
                messages.success(request, f"Biometric authentication {status}!")
                SecurityLog.objects.create(
                    user=user,
                    event_type='BIOMETRIC_UPDATE',
                    ip_address=get_client_ip(request),
                    details=f'Biometric authentication {status}'
                )
            
            return redirect('security_settings')
    else:
        form = SecuritySettingsForm(user)
    
    security_logs = SecurityLog.objects.filter(user=user).order_by('-timestamp')[:10]
    
    return render(request, 'main/security.html', {
        'form': form,
        'user': user,
        'accounts': accounts,
        'security_logs': security_logs
    })

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip