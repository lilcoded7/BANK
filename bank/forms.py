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


from django import forms
from .models import Transaction, Account


class BankTransferForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["sender_account", "recipient_account", "amount", "description"]

    sender_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
    )
    recipient_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=True,
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )


class MobileMoneyForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["sender_account", "recipient_number", "network", "amount", "description"]

    sender_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    recipient_number = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    network = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )


class DepositForm(forms.Form):
    to_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )


class WithdrawalForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )


class BillPaymentForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["sender_account", "bill_type", "recipient_account_number", "amount", "description"]

    sender_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(status="ACTIVE"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    bill_type = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    recipient_account_number = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=False,
    )
