# forms.py
from django import forms
from django.core.validators import MinValueValidator
from .models import Account
from django_select2.forms import Select2Widget
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


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
        widget=forms.CheckboxInput(),
        label="Enable Biometric Authentication"
    )
    
    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Current password',
            'autocomplete': 'current-password'
        }),
        label="Current Password"
    )
    
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'New password (min 8 characters)',
            'autocomplete': 'new-password'
        }),
        label="New Password",
        min_length=8
    )
    
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        }),
        label="Confirm Password"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Set initial biometric status
        self.fields['enable_biometric'].initial = user.is_biometric_enabled

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        current_password = cleaned_data.get('current_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # Password change validation
        if new_password:
            if not current_password:
                raise forms.ValidationError("Current password is required to change password.")
            
            if not self.user.check_password(current_password):
                raise forms.ValidationError("Current password is incorrect.")
            
            if new_password != confirm_password:
                raise forms.ValidationError("New passwords must match.")
            
            try:
                validate_password(new_password, self.user)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        
        return cleaned_data