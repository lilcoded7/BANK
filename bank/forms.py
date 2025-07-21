# forms.py
from django import forms
from django.core.validators import MinValueValidator
from .models import Account
from django_select2.forms import Select2Widget

class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Enter your email',
        'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter your password',
        'class': 'form-control'
    }))

class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=Select2Widget(attrs={
            'class': 'form-control',
            'data-placeholder': 'Select source account'
        }),
        label="From Account"
    )
    to_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=Select2Widget(attrs={
            'class': 'form-control',
            'data-placeholder': 'Select recipient account'
        }),
        label="To Account"
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00'
        }),
        label="Amount (GHS)"
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description'
        }),
        label="Description"
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = Account.objects.filter(customer=user, status='ACTIVE')
        self.fields['to_account'].queryset = Account.objects.filter(status='ACTIVE')

class MobileMoneyForm(forms.Form):
    from_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=Select2Widget(attrs={
            'class': 'form-control',
            'data-placeholder': 'Select source account'
        }),
        label="From Account"
    )
    mobile_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0244123456'
        }),
        label="Mobile Number"
    )
    network = forms.ChoiceField(
        choices=[
            ('MTN', 'MTN Mobile Money'),
            ('VODAFONE', 'Vodafone Cash'),
            ('AIRTELTIGO', 'AirtelTigo Money')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label="Mobile Network"
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00'
        }),
        label="Amount (GHS)"
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description'
        }),
        label="Description"
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = Account.objects.filter(customer=user, status='ACTIVE')

class SecuritySettingsForm(forms.Form):
    enable_biometric = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Enable Biometric Authentication"
    )
    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current password'
        }),
        label="Current Password"
    )
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password'
        }),
        label="New Password"
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label="Confirm Password"
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password'):
            if not cleaned_data.get('current_password'):
                raise forms.ValidationError("Current password is required to change password.")
            if not self.user.check_password(cleaned_data['current_password']):
                raise forms.ValidationError("Current password is incorrect.")
            if cleaned_data['new_password'] != cleaned_data['confirm_password']:
                raise forms.ValidationError("New passwords must match.")
        return cleaned_data