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


# ---------------- TRANSFER ---------------- #

class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="From Account",
        widget=Select2Widget(attrs={
            "class": "form-control",
            "data-placeholder": "Select source account"
        })
    )
    to_account_number = forms.CharField(
        max_length=20,
        label="To Account Number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter recipient account number"
        })
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "0.00"
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_to_account_number(self):
        number = self.cleaned_data["to_account_number"]
        try:
            return Account.objects.get(account_number=number, status="ACTIVE")
        except Account.DoesNotExist:
            raise forms.ValidationError("Recipient account not found or inactive.")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance in the selected account.")
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
        widget=Select2Widget(attrs={
            "class": "form-control",
            "data-placeholder": "Select source account"
        })
    )
    mobile_number = forms.CharField(
        max_length=15,
        label="Mobile Number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "0244123456"
        })
    )
    network = forms.ChoiceField(
        choices=NETWORK_CHOICES,
        label="Mobile Network",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "0.00"
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance in the selected account.")
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
        widget=Select2Widget(attrs={
            "class": "form-control",
            "data-placeholder": "Select source account"
        })
    )
    bill_type = forms.ChoiceField(
        choices=BILL_TYPES,
        label="Bill Type",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    account_number = forms.CharField(
        max_length=20,
        label="Account Number",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter bill account number"
        })
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Amount (GHS)",
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "0.00"
        })
    )
    description = forms.CharField(
        required=False,
        label="Description",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Optional description"
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(customer=user, status="ACTIVE")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        from_account = self.cleaned_data.get("from_account")
        if from_account and amount and from_account.balance < amount:
            raise forms.ValidationError("Insufficient balance in the selected account.")
        return amount


# ---------------- SECURITY ---------------- #

class SecuritySettingsForm(forms.Form):
    enable_biometric = forms.BooleanField(
        required=False,
        label="Enable Biometric Authentication",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    current_password = forms.CharField(
        required=False,
        label="Current Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Current password",
            "autocomplete": "current-password"
        })
    )
    new_password = forms.CharField(
        required=False,
        min_length=8,
        label="New Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "New password (min 8 characters)",
            "autocomplete": "new-password"
        })
    )
    confirm_password = forms.CharField(
        required=False,
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirm new password",
            "autocomplete": "new-password"
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["enable_biometric"].initial = user.is_biometric_enabled

    def clean(self):
        data = super().clean()
        new_pw, current_pw, confirm_pw = (
            data.get("new_password"),
            data.get("current_password"),
            data.get("confirm_password"),
        )

        if new_pw:
            if not current_pw:
                raise forms.ValidationError("Current password is required.")
            if not self.user.check_password(current_pw):
                raise forms.ValidationError("Current password is incorrect.")
            if new_pw != confirm_pw:
                raise forms.ValidationError("New passwords do not match.")
            try:
                validate_password(new_pw, self.user)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)

        return data
