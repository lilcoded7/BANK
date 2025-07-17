from django.db import models
from setup.basemodel import TimeBaseModel
from django.contrib.auth import get_user_model
# Create your models here.

Customer = get_user_model()

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('S', 'Savings'),
        ('C', 'Checking'),
        ('B', 'Business'),
        ('O', 'Other'),
    ]
    owner_name = models.ForeignKey(Customer, related_name='customer', on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True)
    account_type = models.CharField(max_length=1, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    def __str__(self):
        return f"{self.owner_name}'s {self.get_account_type_display()} Account"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('D', 'Deposit'),
        ('W', 'Withdrawal'),
        ('T', 'Transfer'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    account = models.ForeignKey(Account, related_name='transactions', on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} on {self.timestamp}"