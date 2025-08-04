from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import (
    Account,
    InvestmentPackage,
    Investment,
    PrestigeSettings,
    SupportTicket,
    
)

User = get_user_model()

class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "Enter your email",
            "class": "form-control"
        }),
        label="Email Address"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Enter your password",
            "class": "form-control"
        }),
        label="Password"
    )

class DepositForm(forms.Form):
    CURRENCY_CHOICES = [
        ("BTC", "Bitcoin (BTC)"),
        ("ETH", "Ethereum (ETH)"),
        ("USDT", "Tether (USDT)"),
    ]

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Currency"
    )
    amount = forms.DecimalField(
        min_value=10,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Enter amount",
            "step": "1"
        }),
        label="Amount",
        validators=[MinValueValidator(10)]
    )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < 10:
            raise ValidationError("Minimum deposit amount is $10")
        return amount

class InvestmentForm(forms.ModelForm):
    amount = forms.DecimalField(
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = Investment
        fields = ["amount", "package"]

class OpenTradeForm(forms.Form):
    SYMBOL_CHOICES = [
        ("BTCUSDT", "BTC/USDT"),
        ("ETHUSDT", "ETH/USDT"),
        ("BNBUSDT", "BNB/USDT"),
        ("SOLUSDT", "SOL/USDT"),
        ("XRPUSDT", "XRP/USDT"),
    ]
    TRADE_TYPE_CHOICES = [
        ("BUY", "Buy (Long)"),
        ("SELL", "Sell (Short)")
    ]

    symbol = forms.ChoiceField(
        choices=SYMBOL_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="BTCUSDT"
    )
    trade_type = forms.ChoiceField(
        choices=TRADE_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        initial="BUY"
    )
    amount = forms.DecimalField(
        min_value=10,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Enter amount"
        })
    )
    leverage = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Leverage"
        }),
        initial=10
    )
    take_profit = forms.DecimalField(
        min_value=0.1,
        max_value=100,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        initial=5.0
    )
    stop_loss = forms.DecimalField(
        min_value=0.1,
        max_value=100,
        decimal_places=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        initial=2.0
    )
    entry_price = forms.DecimalField(
        widget=forms.HiddenInput(),
        required=False,
        initial=0
    )

    def __init__(self, *args, user=None, bank_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.bank_settings = bank_settings or PrestigeSettings.load()
        self.fields["amount"].min_value = float(self.bank_settings.min_trade_amount)
        self.fields["leverage"].max_value = self.bank_settings.max_leverage

    def clean(self):
        cleaned_data = super().clean()
        if self.user:
            try:
                account = Account.objects.get(
                    customer=self.user,
                    account_type="INVESTMENT"
                )
                amount = cleaned_data.get("amount")
                leverage = cleaned_data.get("leverage")
                
                if amount and leverage:
                    margin_required = amount / leverage
                    if account.balance < margin_required:
                        raise ValidationError("Insufficient funds for this trade")
            except Account.DoesNotExist:
                raise ValidationError("No investment account found")
        return cleaned_data

class SecuritySettingsForm(forms.Form):
    enable_biometric = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(),
        label="Enable Biometric Authentication"
    )
    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Current password"
        }),
        label="Current Password"
    )
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            "placeholder": "New password (min 8 characters)"
        }),
        min_length=8,
        label="New Password"
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm new password"
        }),
        label="Confirm Password"
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields["enable_biometric"].initial = user.is_biometric_enabled

    def clean(self):
        cleaned_data = super().clean()
        if self.user and cleaned_data.get("new_password"):
            if not cleaned_data.get("current_password"):
                raise ValidationError("Current password is required")
            if not self.user.check_password(cleaned_data["current_password"]):
                raise ValidationError("Current password is incorrect")
            if cleaned_data["new_password"] != cleaned_data["confirm_password"]:
                raise ValidationError("Passwords do not match")
        return cleaned_data
