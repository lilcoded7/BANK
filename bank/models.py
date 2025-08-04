from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from setup.basemodel import TimeBaseModel
from decimal import Decimal
import uuid

User = get_user_model()


from django.contrib.auth import get_user_model

User = get_user_model()


class PrestigeSettings(TimeBaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # Use SET_NULL instead of CASCADE for admin user
        null=True,
        blank=True,
        verbose_name="Admin User",
    )
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
        existing = PrestigeSettings.objects.first()

        if existing and existing.pk != self.pk:
            self.pk = existing.pk

        super().save(*args, **kwargs)

        PrestigeSettings.objects.exclude(pk=self.pk).delete()

    @classmethod
    def load(cls, admin_user=None):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(pk=1)
            if admin_user:
                obj.user = admin_user
                obj.save()
        return obj

    def __str__(self):
        return "Prestige Settings"
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
        last_seq = (
            int(latest.account_number[-4:]) if latest and latest.account_number else 0
        )
        return f"{self.BIN}{str(last_seq + 1).zfill(4)}"


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
    features = models.JSONField(default=list)

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

    hidden = models.BooleanField(default=False)

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
        Account,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sent_transactions",
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
    wallet_address = models.CharField(max_length=225, null=True, blank=True)

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
        return f"Trade Info for {self.trade_position.symbol}"


class ReferalCode(TimeBaseModel):
    name = models.CharField(max_length=100, null=True, blank=True)
    code = models.CharField(max_length=100, null=True, blank=True)
    is_expired = models.BooleanField(default=False)

    def __str__(self):
        return f"Name: {self.name} Code: {self.code}"

    def save(self, *args, **kwargs):
        if not self.code:
            unique_code = uuid.uuid4().hex[:8].upper()

            while ReferalCode.objects.filter(code=unique_code).exists():
                unique_code = uuid.uuid4().hex[:8].upper()

            self.code = unique_code

        super().save(*args, **kwargs)





class SupportTicket(TimeBaseModel):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=200)
    priority = models.CharField(max_length=100, default="Medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"


class SupportMessage(TimeBaseModel):
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    receiver = models.ForeignKey(
        PrestigeSettings, on_delete=models.CASCADE, null=True, blank=True
    )
    message = models.TextField()
    image = models.ImageField(blank=True, null=True)
    file = models.FileField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} for ticket #{self.ticket.id}"


class UserStatus(TimeBaseModel):
    STATUS_CHOICES = [
        ("ONLINE", "Online"),
        ("OFFLINE", "Offline"),
        ("AWAY", "Away"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="status")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OFFLINE")
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} is {self.get_status_display()}"

    @classmethod
    async def update_user_status(cls, user, status):
        await cls.objects.aupdate_or_create(user=user, defaults={"status": status})
