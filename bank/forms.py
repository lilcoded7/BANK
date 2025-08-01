# forms.py
from django import forms
from django.core.validators import MinValueValidator
from .models import Account, InvestmentPackage, PrestigeSettings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from bank.models import *

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"placeholder": "Enter your email", "class": "form-control"}
        ),
        label="Email Address",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Enter your password", "class": "form-control"}
        ),
        label="Password",
    )


class DepositForm(forms.Form):
    CURRENCY_CHOICES = [
        ("BTC", "Bitcoin (BTC)"),
        ("ETH", "Ethereum (ETH)"),
        ("USDT", "Tether (USDT)"),
    ]

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_currency"}),
        label="Currency",
    )
    amount = forms.DecimalField(
        min_value=10,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter amount",
                "step": "1",
                "id": "id_amount",
            }
        ),
        label="Amount",
        validators=[MinValueValidator(10)],
    )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < 10:
            raise ValidationError("Minimum deposit amount is $10")
        return amount


class InvestmentForm(forms.ModelForm):
    amount = forms.DecimalField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"})
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

    TRADE_TYPE_CHOICES = [("BUY", "Buy (Long)"), ("SELL", "Sell (Short)")]

    symbol = forms.ChoiceField(
        choices=SYMBOL_CHOICES,
        widget=forms.Select(attrs={"class": "form-control", "id": "tradeSymbol"}),
        label="Symbol",
        initial="BTCUSDT",
    )
    trade_type = forms.ChoiceField(
        choices=TRADE_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control", "id": "tradeType"}),
        label="Trade Type",
        initial="BUY",
    )
    amount = forms.DecimalField(
        min_value=10,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter amount",
                "step": "10",
                "id": "tradeAmount",
            }
        ),
        label="Amount ($)",
    )
    leverage = forms.IntegerField(
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Leverage", "id": "leverage"}
        ),
        label="Leverage",
        initial=10,
    )
    take_profit = forms.DecimalField(
        min_value=0.1,
        max_value=100,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "e.g. 5", "id": "takeProfit"}
        ),
        label="Take Profit (%)",
        initial=5.0,
    )
    stop_loss = forms.DecimalField(
        min_value=0.1,
        max_value=100,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "e.g. 2", "id": "stopLoss"}
        ),
        label="Stop Loss (%)",
        initial=2.0,
    )
    entry_price = forms.DecimalField(
        widget=forms.HiddenInput(attrs={"id": "entryPrice"}), required=False, initial=0
    )

    def __init__(self, *args, user=None, bank_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.bank_settings = bank_settings or PrestigeSettings.load()

        # Set min trade amount based on bank settings
        self.fields["amount"].min_value = float(self.bank_settings.min_trade_amount)
        self.fields["leverage"].max_value = self.bank_settings.max_leverage

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < self.bank_settings.min_trade_amount:
            raise ValidationError(
                f"Minimum trade amount is ${self.bank_settings.min_trade_amount}"
            )
        return amount

    def clean_leverage(self):
        leverage = self.cleaned_data["leverage"]
        if leverage > self.bank_settings.max_leverage:
            raise ValidationError(
                f"Maximum leverage is {self.bank_settings.max_leverage}x"
            )
        return leverage

    def clean(self):
        cleaned_data = super().clean()
        user = self.user

        if user:
            try:
                account = Account.objects.get(customer=user, account_type="INVESTMENT")
            except Account.DoesNotExist:
                raise ValidationError("No investment account found")

            amount = cleaned_data.get("amount")
            leverage = cleaned_data.get("leverage")

            if amount and leverage:
                margin_required = amount / leverage
                if account.balance < margin_required:
                    raise ValidationError(
                        "Insufficient funds for Deposit amount to your account"
                    )

        return cleaned_data


class SecuritySettingsForm(forms.Form):
    enable_biometric = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"id": "enableBiometric"}),
        label="Enable Biometric Authentication",
    )

    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Current password",
                "autocomplete": "current-password",
                "id": "currentPassword",
            }
        ),
        label="Current Password",
    )

    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "New password (min 8 characters)",
                "autocomplete": "new-password",
                "id": "newPassword",
            }
        ),
        label="New Password",
        min_length=8,
    )

    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
                "id": "confirmPassword",
            }
        ),
        label="Confirm Password",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Set initial biometric status
        if user:
            self.fields["enable_biometric"].initial = user.is_biometric_enabled

    def clean(self):
        cleaned_data = super().clean()
        user = self.user

        if not user:
            return cleaned_data

        new_password = cleaned_data.get("new_password")
        current_password = cleaned_data.get("current_password")
        confirm_password = cleaned_data.get("confirm_password")

        # Password change validation
        if new_password:
            if not current_password:
                raise ValidationError(
                    "Current password is required to change password."
                )

            if not user.check_password(current_password):
                raise ValidationError("Current password is incorrect.")

            if new_password != confirm_password:
                raise ValidationError("New passwords must match.")

            # Validate password strength
            if len(new_password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")

        return cleaned_data
