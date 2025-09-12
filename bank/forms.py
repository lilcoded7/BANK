from django import forms
from django.core.validators import MinValueValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_select2.forms import Select2Widget
from .models import Account


# ---------------- AUTH ---------------- #

class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your email",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password",
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )


# ---------------- BANK TRANSFER ---------------- #

class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="From Account",
        widget=Select2Widget(attrs={"class": "form-control"})
    )
    to_account_number = forms.CharField(
        max_length=20,
        label="Recipient Account Number",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_to_account_number(self):
        number = self.cleaned_data["to_account_number"]
        try:
            return Account.objects.get(account_number=number, status="ACTIVE")
        except Account.DoesNotExist:
            raise forms.ValidationError("Recipient account not found.")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance.")
        return amount


# ---------------- MOBILE MONEY ---------------- #

class MobileMoneyForm(forms.Form):
    NETWORK_CHOICES = [
        ("MTN", "MTN Mobile Money"),
        ("VODAFONE", "Vodafone Cash"),
        ("AIRTELTIGO", "AirtelTigo Money"),
    ]

    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="From Account",
        widget=Select2Widget(attrs={"class": "form-control"})
    )
    mobile_number = forms.CharField(
        max_length=15,
        label="Mobile Number",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    network = forms.ChoiceField(
        choices=NETWORK_CHOICES,
        label="Network",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance.")
        return amount


# ---------------- BILL PAYMENT ---------------- #

class BillPaymentForm(forms.Form):
    BILL_TYPES = [
        ("ELECTRICITY", "Electricity"),
        ("WATER", "Water"),
        ("TV", "TV License"),
        ("INTERNET", "Internet"),
    ]

    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="From Account",
        widget=Select2Widget(attrs={"class": "form-control"})
    )
    bill_type = forms.ChoiceField(
        choices=BILL_TYPES,
        label="Bill Type",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    account_number = forms.CharField(
        max_length=20,
        label="Bill Account Number",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    description = forms.CharField(
        required=False,
        label="Description",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance.")
        return amount


# ---------------- DEPOSIT ---------------- #

class DepositForm(forms.Form):
    to_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="To Account",
        widget=Select2Widget(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        label="Amount (GHS)",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")


# ---------------- WITHDRAWAL ---------------- #

class WithdrawalForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="From Account",
        widget=Select2Widget(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        label="Amount (GHS)",
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance.")
        return amount


# ---------------- SECURITY ---------------- #

class SecuritySettingsForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your current password'
        }), 
        required=False
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a new password'
        }), 
        required=False,
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password'
        }), 
        required=False
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        current_password = cleaned_data.get("current_password")

        if new_password:
            if not current_password:
                self.add_error("current_password", "Current password is required to set a new password")
            elif not self.user.check_password(current_password):
                self.add_error("current_password", "Current password is incorrect")
            elif new_password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match")
                
        return cleaned_data