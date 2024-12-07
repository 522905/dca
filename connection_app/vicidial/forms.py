from django import forms
from django.core.exceptions import ValidationError
import re


def validate_no_special_characters(value):
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        raise ValidationError("Special characters are not allowed in this field.")


def validate_only_digits(value):
    if not value.isdigit():

        raise ValidationError("Only digits are allowed.")


class VicidialDeliveryBoyForm(forms.Form):
    agent_fullname = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name',
            'required': True,
            'id': 'fullname'
        }),
        label="Full Name",
        validators=[validate_no_special_characters]
    )

    agent_user = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'readonly': True,
            'required': True,
            'id': 'username'
        }),
        label="Username",
        help_text="Username should be alphanumeric without special characters."
    )

    agent_pass = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'required': True,
            'id': 'user-pass'
        }),
        label="Password",
        help_text="Enter a secure password."
    )

    phone_number = forms.CharField(
        min_length=10,
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number',
            'required': True,
            'id': 'phone_number'
        }),
        label="Phone Number",
        validators=[validate_only_digits],
        help_text="Phone number must be exactly 10 digits."
    )

    phone_login = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone ID',
            'required': True,
            'id': 'phone_login'
        }),
        label="Phone ID",
        validators=[validate_no_special_characters],
        help_text="Phone ID should not contain special characters."
    )

    phone_pass = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Password',
            'required': True,
            'id': 'phone_pass'
        }),
        label="Phone Password",
        help_text="Enter the phone password."
    )
