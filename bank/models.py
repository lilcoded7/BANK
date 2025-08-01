# models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from setup.basemodel import TimeBaseModel
from decimal import Decimal
import uuid

User = get_user_model()


class PrestigeSettings(TimeBaseModel):
    """Singleton model for bank-wide settings"""

    deposit_btc_address = models.CharField(max_length=100, blank=True)
    deposit_eth_address = models.CharField(max_length=100, blank=True)
    deposit_usdt_address = models.CharField(max_length=100, blank=True)
    trading_enabled = models.BooleanField(default=True)
    min_trade_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=100.00
    )
    max_leverage = models.PositiveIntegerField(default=50)

    class Meta:
        verbose_name_plural = "Prestige Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class Account(TimeBaseModel):
    ACCOUNT_TYPES = [
        ("SAVINGS", "Savings Account"),
        ("CHECKING", "Checking Account"),
        ("FIXED", "Fixed Deposit"),
        ("INVESTMENT", "Investment Account"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DORMANT", "Dormant"),
        ("CLOSED", "Closed"),
    ]

    BIN = "123456"
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=20, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="GHS")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACTIVE")
    date_opened = models.DateTimeField(default=timezone.now)
    is_interoperable = models.BooleanField(default=True)

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


class InvestmentPackage(TimeBaseModel):
    PACKAGE_TYPES = [
        ("STARTER", "Starter"),
        ("PREMIUM", "Premium"),
        ("VIP", "VIP"),
    ]

    name = models.CharField(max_length=20, choices=PACKAGE_TYPES)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    roi_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    features = models.JSONField(default=list)  # Store list of features

    def __str__(self):
        return self.get_name_display()


class Investment(TimeBaseModel):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    package = models.ForeignKey(InvestmentPackage, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    expected_return = models.DecimalField(max_digits=15, decimal_places=2)
    actual_return = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timezone.timedelta(
                days=self.package.duration_days
            )
        if not self.expected_return:
            self.expected_return = self.amount * (
                self.package.roi_percentage / Decimal(100)
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account.customer.email} - {self.package.name}"


class TradePosition(TimeBaseModel):
    TRADE_TYPES = [
        ("BUY", "Buy (Long)"),
        ("SELL", "Sell (Short)"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
        ("PENDING", "Pending"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20)
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    leverage = models.PositiveIntegerField(default=1)
    entry_price = models.DecimalField(max_digits=15, decimal_places=6)
    current_price = models.DecimalField(
        max_digits=15, decimal_places=6, null=True, blank=True
    )
    take_profit = models.DecimalField(max_digits=5, decimal_places=2)
    stop_loss = models.DecimalField(max_digits=5, decimal_places=2)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OPEN")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def calculate_profit_loss(self):
        if not self.current_price:
            return Decimal("0.00")

        price_difference = self.current_price - self.entry_price
        if self.trade_type == "SELL":
            price_difference = -price_difference

        self.profit_loss = self.amount * price_difference / self.entry_price
        return self.profit_loss

    def save(self, *args, **kwargs):
        if not self.current_price:
            self.current_price = self.entry_price
        self.calculate_profit_loss()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.symbol} {self.get_trade_type_display()}"


class Transaction(TimeBaseModel):
    TRANSACTION_TYPES = [
        ("TRANSFER", "Bank Transfer"),
        ("BTC", "BTC"),
        ("DEPOSIT", "Deposit"),
        ("WITHDRAWAL", "Withdrawal"),
        ("BILL_PAYMENT", "Bill Payment"),
        ("INVESTMENT", "Investment"),
        ("TRADE", "Trade"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=30, unique=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default="BTC")
    sender_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="sent_transactions"
    )
    recipient_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="received_transactions",
        null=True,
        blank=True,
    )
    recipient_number = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    investment = models.ForeignKey(
        Investment, on_delete=models.SET_NULL, null=True, blank=True
    )
    trade_position = models.ForeignKey(
        TradePosition, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.transaction_id} - {self.get_transaction_type_display()}"


class SecurityLog(TimeBaseModel):
    EVENT_TYPES = [
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("PASSWORD_CHANGE", "Password Change"),
        ("TRANSACTION", "Transaction"),
        ("BIOMETRIC_UPDATE", "Biometric Update"),
        ("TRADE_EXECUTED", "Trade Executed"),
        ("INVESTMENT_CREATED", "Investment Created"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField()
    device_info = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField()

    def __str__(self):
        return f"{self.user.email} - {self.get_event_type_display()}"


class FingerPrint(TimeBaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="user_bio")
    template_data = models.BinaryField(null=True, blank=True)
    image = models.ImageField(null=True, blank=True)

    def __str__(self):
        return f"FingerPrint: {self.user.username}"


class TradeInfo(TimeBaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    trade_position = models.ForeignKey(TradePosition, on_delete=models.CASCADE)
    current_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    volume_price = models.FloatField()

    def __str__(self):
        return f"Trade: "


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="support_tickets",
    )
    reference_id = models.UUIDField(default=uuid.uuid4, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    priority = models.CharField(
        max_length=10, null=True, blank=True, choices=PRIORITY_CHOICES, default="MEDIUM"
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, null=True, blank=True, default="OPEN"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.reference_id} - {self.subject}"


class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="support_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message for {self.ticket.reference_id} by {self.user.username}"
