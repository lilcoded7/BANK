from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from setup.basemodel import TimeBaseModel
import uuid

User = get_user_model()


class Customer(TimeBaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile", null=True, blank=True)
    username = models.CharField(max_length=100)
    full_name = models.CharField(max_length=100)
    id_card = models.CharField(max_length=100, null=True, blank=True)
    image = models.ImageField(null=True, blank=True)
    is_biometric_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.username

class Account(TimeBaseModel):
    ACCOUNT_TYPES = [
        ("SAVINGS", "Savings Account"),
        ("CHECKING", "Checking Account"),
        ("FIXED", "Fixed Deposit"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DORMANT", "Dormant"),
        ("CLOSED", "Closed"),
    ]

    BIN = "123456"
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="GHS")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACTIVE")
    date_opened = models.DateTimeField(default=timezone.now)
    is_interoperable = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date_opened"]

    def __str__(self):
        return f"{self.account_number} - {self.get_account_type_display()}"

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)

    def generate_account_number(self):
        latest = (
            Account.objects.filter(account_number__startswith=self.BIN)
            .order_by("-account_number")
            .first()
        )
        if latest and latest.account_number:
            last_seq = int(latest.account_number[-4:])
        else:
            last_seq = 0
        new_seq = str(last_seq + 1).zfill(4)
        return f"{self.BIN}{new_seq}"


class Transaction(TimeBaseModel):
    TRANSACTION_TYPES = [
        ("TRANSFER", "Bank Transfer"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("DEPOSIT", "Deposit"),
        ("WITHDRAWAL", "Withdrawal"),
        ("BILL_PAYMENT", "Bill Payment"),
    ]

    STATUS_CHOICES = [
        ("pending", "pending"),
        ("success", "success"),
        ("failed", "Failed"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=True, blank=True
    )
    transaction_id = models.CharField(
        max_length=30, unique=True, null=True, blank=True
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default="GHS")

    sender_account = models.ForeignKey(
        Account, on_delete=models.PROTECT,
        related_name="sent_transactions",
        null=True, blank=True
    )
    recipient_account = models.ForeignKey(
        Account, on_delete=models.PROTECT,
        related_name="received_transactions",
        null=True, blank=True,
    )

    # Mobile Money
    recipient_number = models.CharField(max_length=20, null=True, blank=True)
    network = models.CharField(max_length=50, null=True, blank=True)

    # Bill Payment
    bill_type = models.CharField(max_length=100, null=True, blank=True)
    recipient_account_number = models.CharField(max_length=50, null=True, blank=True)

    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="COMPLETED")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} {self.currency}"


class SecurityLog(TimeBaseModel):
    EVENT_TYPES = [
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("PASSWORD_CHANGE", "Password Change"),
        ("TRANSACTION", "Transaction"),
        ("BIOMETRIC_UPDATE", "Biometric Update"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField()
    device_info = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField()

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.email} - {self.get_event_type_display()}"
    

class ChatMessage(models.Model):
    SENDER_CHOICES = (
        ('customer', 'Customer'),
        ('support', 'Support'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.sender} - {self.message[:30]}"
