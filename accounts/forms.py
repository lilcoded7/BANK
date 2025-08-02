from django import forms
from django.core.exceptions import ValidationError
import re

class RegisterUser(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.TextInput(
            attrs={'class': 'form-control'}
        )
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={'class': 'form-control'}
        )
    )

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
