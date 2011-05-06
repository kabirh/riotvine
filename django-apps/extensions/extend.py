"""
Code hooks to extend third-party django applications that
we don't want to change in-place.

This is invoked from ``website.__init__``

"""
import extensions.form_extensions
import extensions.signal_extensions
import extensions.logging_extensions

