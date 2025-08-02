from django import forms
from django.core.exceptions import ValidationError
from bank.models import ReferalCode
import re

class RegisterUserForm(forms.Form):
    username = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'enter your username'
            }
        )
    )

    referal_code = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'enter referal code'
            }
        )
    )

    email = forms.EmailField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'enter your email'
            }
        )
    )

    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'type': 'password',
                'placeholder': 'enter your password'
            }
        )
    )

    def clean_referal_code(self):
        referal_code = self.cleaned_data.get('referal_code')

        if ReferalCode.objects.filter(code=referal_code, is_expired=True).exists():
            raise ValidationError('Referral code has already been used or is expired.')

        if not ReferalCode.objects.filter(code=referal_code).exists():
            raise ValidationError('Invalid referral code.')

        return referal_code

    def clean_password(self):
        password = self.cleaned_data.get('password')

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        

        if not re.search(r"\d", password):
            raise ValidationError("Password must contain at least one digit.")

        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError("Password must contain at least one special character.")

        return password
