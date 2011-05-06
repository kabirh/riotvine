"""
Extend various django.contrib and third-party forms.
"""
from django.utils.translation import ugettext as _
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm, SetPasswordForm, PasswordChangeForm

from messages.forms import ComposeForm


AuthenticationForm.base_fields['username'].label = _('Username or Email')
AuthenticationForm.base_fields['username'].max_length = 125

UserCreationForm.base_fields['username'].label = _('Username')
UserCreationForm.base_fields['username'].min_length = 4
UserCreationForm.base_fields['username'].help_text = _('Between 4 and 30 alphanumeric characters (letters, digits and underscores).')

UserCreationForm.base_fields['password1'].min_length = 5
UserCreationForm.base_fields['password1'].help_text = _('Must be at least 5 characters (English letters and digits).')

UserCreationForm.base_fields['password2'].min_length = 5
UserCreationForm.base_fields['password2'].label = _('Re-enter Password')

PasswordResetForm.base_fields['email'].label = _('Email')

