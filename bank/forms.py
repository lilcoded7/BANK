from django import forms
from django.core.validators import MinValueValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_select2.forms import Select2Widget
from bank.models import *


# ---------------- AUTH ---------------- #


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "form-control",
        "placeholder": "Enter your email"
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-control",
        "placeholder": "Enter your password"
    }))

class ResetPasswordForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter OTP code",
            "required": True,
        }),
        label="OTP Code"
    )
    password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter new password",
            "required": True,
        }),
        label="New Password"
    )

    password_confirm = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirm new password",
            "required": True,
        }),
        label="Confirm Password"
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


User = get_user_model()

class EmailForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your email",
            "required": True,
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No user is associated with this email.")
        return email
   

class CodeForm(forms.Form):
    code = forms.CharField(widget=forms.TextInput(attrs={
        "class": "form-control",
        "placeholder": "Enter your code"
    }))

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if User.objects.filter(code=code).exists():
            return code
        raise forms.ValidationError('invalide code ')
   
class BankTransferForm(forms.Form):
    sender_account = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "sender_account account number"}),
    )
    
    recipient_account = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Recipient account number"}),
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0.01"}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

  
    def clean(self):
        cleaned_data = super().clean()
        sender = cleaned_data.get("sender_account")
        recipient_number = cleaned_data.get("recipient_account")
        amount = cleaned_data.get("amount")

        if sender and recipient_number and sender.strip() == recipient_number.strip():
            raise forms.ValidationError("Sender and recipient accounts cannot be the same.")

        if recipient_number and not Account.objects.filter(
            account_number=recipient_number.strip(), status="ACTIVE"
        ).exists():
            raise forms.ValidationError("Recipient account does not exist or is inactive.")

        if sender and not Account.objects.filter(
            account_number=sender.strip(), status="ACTIVE"
        ).exists():
            raise forms.ValidationError("Sender account does not exist or is inactive.")

        # Optional: check balance here instead of in the view
        sender_acc = Account.objects.filter(account_number=sender.strip(), status="ACTIVE").first()
        if sender_acc and amount and sender_acc.balance < amount:
            raise forms.ValidationError("Insufficient funds in sender account.")

        return cleaned_data



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


from django.contrib.auth import get_user_model


User = get_user_model()


class CustomerCreateForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    full_name = forms.CharField(max_length=100)
    username = forms.CharField(max_length=100)  # For Customer model
    id_card = forms.CharField(required=False)
    image = forms.ImageField(required=False)
    account_type = forms.ChoiceField(choices=Account.ACCOUNT_TYPES)

    def save(self):
        from accounts.models import User  # import your custom user

        # ✅ Create user (custom manager only needs email + password)
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"]
        )
        

        # ✅ Create Customer linked to User
        customer = Customer.objects.create(
            user=user,
            username=self.cleaned_data["username"],   
            full_name=self.cleaned_data["full_name"],
            id_card=self.cleaned_data.get("id_card"),
            image=self.cleaned_data.get("image"),
        )
        user.username=customer.username
        user.full_name=customer.full_name
        user.save()

        # ✅ Create Account for Customer
        Account.objects.create(
            customer=customer,
            account_type=self.cleaned_data["account_type"]
        )

        return customer
