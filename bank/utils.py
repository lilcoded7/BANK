
from datetime import datetime, timedelta
import uuid


def generate_transaction_id():
    return f"TX{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def get_device_info(request):
    # Simplified - in real implementation would gather more device details
    return {
        'user_agent': request.META.get('HTTP_USER_AGENT'),
        'device': request.user_agent.device.family if hasattr(request, 'user_agent') else 'Unknown'
    }

def get_geolocation(request):
    # Simplified - would use IP geolocation service in real implementation
    return "Ghana"  # Default for this implementation

def verify_biometric(user, biometric_data):
    # Simplified - would verify against stored biometric template in real implementation
    return True  # Always return true for this example


from django.db import transaction as db_transaction

@db_transaction.atomic
def credit_bank_transfer(tx):
    """Handle bank transfer between accounts."""
    if tx.status == "success":  # Idempotency check
        return "Already processed"

    tx.sender_account.balance -= tx.amount
    tx.recipient_account.balance += tx.amount
    tx.sender_account.save()
    tx.recipient_account.save()
    tx.status = "success"
    tx.save()
    return "Bank transfer successful"


@db_transaction.atomic
def credit_deposit(tx):
    """Handle deposit into account."""
    if tx.status == "success":
        return "Already processed"

    tx.recipient_account.balance += tx.amount
    tx.recipient_account.save()
    tx.status = "success"
    tx.save()
    return "Deposit successful"


@db_transaction.atomic
def process_withdrawal(tx):
    """Handle withdrawals from account."""
    if tx.status == "success":
        return "Already processed"

    if tx.sender_account.balance < tx.amount:
        tx.status = "failed"
        tx.save()
        return "Insufficient funds"

    tx.sender_account.balance -= tx.amount
    tx.sender_account.save()
    tx.status = "success"
    tx.save()
    return "Withdrawal successful"


@db_transaction.atomic
def process_bill_payment(tx):
    """Handle bill payments."""
    if tx.status == "success":
        return "Already processed"

    if tx.sender_account.balance < tx.amount:
        tx.status = "failed"
        tx.save()
        return "Insufficient funds"

    tx.sender_account.balance -= tx.amount
    tx.sender_account.save()
    tx.status = "success"
    tx.save()
    return f"Bill payment for {tx.bill_type} successful"


@db_transaction.atomic
def process_mobile_money(tx):
    """Handle mobile money transaction."""
    if tx.status == "success":
        return "Already processed"

    if tx.sender_account and tx.sender_account.balance < tx.amount:
        tx.status = "failed"
        tx.save()
        return "Insufficient funds"

    if tx.sender_account:
        tx.sender_account.balance -= tx.amount
        tx.sender_account.save()

    tx.status = "success"
    tx.save()
    return "Mobile money transaction successful"



from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404


class EmailSender:
    def send_email(self, data):
        email = EmailMessage(
            subject    = data['email_subject'],
            body       = data['email_body'],
            to         = [data['to_email']],
        )
        email.content_subtype = 'html'
        email.send()

    def send_otp(self, user):
        message = render_to_string('mails/send_otp.html', {'user':user})
        data = {
            'email_subject':'OTP CODE',
            'email_body': message,
            'to_email':user.email
            }
        self.send_email(data)

    def send_reset_password_success_message(self, user):
        message = render_to_string('mails/reset_pws_success.html', {'user':user})
        data = {
            'email_subject':'Verification Code',
            'email_body': message,
            'to_email':user.email
            }
        self.send_email(data)