from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
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


class EmailForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class':'form-control',
                'placeholder':'enter email'
            }
        )
    )


class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={
                'autofocus': True,
                'class': 'form-control mb-3',
                'placeholder': _('Enter your email'),
            }
        )
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control mb-3',
                'placeholder': _('Enter your password'),
            }
        )
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'form-check-input me-2',
            }
        ),
        label=_("Remember me"),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
        # Apply consistent styling for labels
        for visible_field in self.visible_fields():
            if not isinstance(visible_field.field.widget, forms.CheckboxInput):
                visible_field.field.widget.attrs['class'] += ' form-control'

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_("Invalid email or password."))
        return self.cleaned_data

    def get_user(self):
        return self.user_cache




class ResetPasswordForm(forms.Form):
    code = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class':'form-control',
                'placeholder':'enter code'
            }
        )
    )
    new_password = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class':'form-control',
                'placeholder':'enter new password'
            }
        )
    )