from decimal import Decimal
from django.conf import settings
import random
import string
import requests


def generate_reference():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def initialize_transaction(transaction, callback_url):
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    amount = transaction.amount * 100
    
    data = {
        "email": 'wealthcoprestige@gmail.com',
        "amount": int(amount),
        "currency": 'GHS',
        "reference": transaction.transaction_id,
        "callback_url": callback_url,
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()


def confirm_transaction(reference):
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }
    response = requests.get(url, headers=headers)
    return response.json()