"""
Custom validators for Ujjwala V3 Application

This module provides Django validators for various fields like Aadhaar number,
IFSC code, mobile number, pincode, etc.
"""

import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def validate_aadhaar_number(value: str) -> None:
    """
    Validate Indian Aadhaar number.

    Rules:
    - Must be exactly 12 digits
    - Cannot start with 0 or 1
    - Must contain only numeric characters

    Args:
        value: Aadhaar number string

    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError('Aadhaar number is required.')

    # Remove any spaces or hyphens
    clean_value = re.sub(r'[\s-]', '', value)

    if len(clean_value) != 12:
        raise ValidationError('Aadhaar number must be exactly 12 digits.')

    if not clean_value.isdigit():
        raise ValidationError('Aadhaar number must contain only digits.')

    if clean_value[0] in ('0', '1'):
        raise ValidationError('Aadhaar number cannot start with 0 or 1.')


def validate_mobile_number(value: str) -> None:
    """
    Validate Indian mobile number.

    Rules:
    - Must be exactly 10 digits
    - Must start with 6, 7, 8, or 9

    Args:
        value: Mobile number string

    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError('Mobile number is required.')

    # Remove any spaces, hyphens, or +91
    clean_value = re.sub(r'[\s\-+]', '', value)
    clean_value = clean_value.removeprefix('91')

    if len(clean_value) != 10:
        raise ValidationError('Mobile number must be exactly 10 digits.')

    if not clean_value.isdigit():
        raise ValidationError('Mobile number must contain only digits.')

    if clean_value[0] not in ('6', '7', '8', '9'):
        raise ValidationError('Mobile number must start with 6, 7, 8, or 9.')


def validate_ifsc_code(value: str) -> None:
    """
    Validate Indian IFSC code.

    Format: 4 letters (bank code) + 0 + 6 alphanumeric (branch code)
    Example: SBIN0001234

    Args:
        value: IFSC code string

    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError('IFSC code is required.')

    value = value.upper().strip()

    ifsc_pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    if not re.match(ifsc_pattern, value):
        raise ValidationError(
            'Invalid IFSC code format. '
            'Format: 4 letters + 0 + 6 alphanumeric characters (e.g., SBIN0001234)'
        )


def validate_pincode(value: str) -> None:
    """
    Validate Indian pincode.

    Rules:
    - Must be exactly 6 digits
    - Cannot start with 0

    Args:
        value: Pincode string

    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError('Pincode is required.')

    clean_value = value.strip()

    if len(clean_value) != 6:
        raise ValidationError('Pincode must be exactly 6 digits.')

    if not clean_value.isdigit():
        raise ValidationError('Pincode must contain only digits.')

    if clean_value[0] == '0':
        raise ValidationError('Pincode cannot start with 0.')


def validate_bank_account_number(value: str) -> None:
    """
    Validate bank account number.

    Rules:
    - Length between 9 to 18 characters
    - Alphanumeric only

    Args:
        value: Account number string

    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError('Bank account number is required.')

    clean_value = value.strip()

    if len(clean_value) < 9 or len(clean_value) > 18:
        raise ValidationError('Bank account number must be between 9 and 18 characters.')

    if not clean_value.isalnum():
        raise ValidationError('Bank account number must be alphanumeric.')


def validate_adult_dob(value: date) -> None:
    """
    Validate that the date of birth indicates an adult (>= 18 years).

    Args:
        value: Date of birth

    Raises:
        ValidationError: If person is below 18 years
    """
    if not value:
        raise ValidationError('Date of birth is required.')

    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

    if age < 18:
        raise ValidationError(
            f'Applicant must be at least 18 years old. Current age: {age} years.'
        )

    # Also check for unreasonably old ages (e.g., > 120 years)
    if age > 120:
        raise ValidationError(
            f'Invalid date of birth. Age cannot exceed 120 years. Current age: {age} years.'
        )


def validate_future_date(value: date) -> None:
    """
    Validate that the date is not in the future.

    Args:
        value: Date to validate

    Raises:
        ValidationError: If date is in future
    """
    if not value:
        return

    if value > date.today():
        raise ValidationError('Date cannot be in the future.')


def validate_alphanumeric_with_spaces(value: str) -> None:
    """
    Validate that string contains only alphanumeric characters and spaces.

    Used for names, addresses, etc.

    Args:
        value: String to validate

    Raises:
        ValidationError: If contains special characters
    """
    if not value:
        return

    # Allow letters (any script), numbers, spaces, hyphens, and periods
    pattern = r'^[\w\s\.\-]+$'
    if not re.match(pattern, value, re.UNICODE):
        raise ValidationError(
            'Only alphanumeric characters, spaces, hyphens, and periods are allowed.'
        )


def validate_name(value: str) -> None:
    """
    Validate person name.

    Rules:
    - Cannot be empty or only whitespace
    - Minimum 2 characters
    - Maximum 100 characters
    - No special characters except spaces, hyphens, periods

    Args:
        value: Name string

    Raises:
        ValidationError: If validation fails
    """
    if not value or not value.strip():
        raise ValidationError('Name cannot be empty.')

    clean_value = value.strip()

    if len(clean_value) < 2:
        raise ValidationError('Name must be at least 2 characters long.')

    if len(clean_value) > 100:
        raise ValidationError('Name cannot exceed 100 characters.')

    # Allow letters (any script), spaces, hyphens, periods, and apostrophes
    pattern = r"^[a-zA-Z\s\.\-']+$"
    if not re.match(pattern, clean_value):
        raise ValidationError(
            'Name can only contain letters, spaces, hyphens, periods, and apostrophes.'
        )


# Regex validators for common patterns
name_validator = RegexValidator(
    regex=r"^[a-zA-Z\s\.\-']+$",
    message='Only letters, spaces, hyphens, periods, and apostrophes are allowed.',
    code='invalid_name'
)

alphanumeric_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9\s]+$',
    message='Only alphanumeric characters and spaces are allowed.',
    code='invalid_alphanumeric'
)
