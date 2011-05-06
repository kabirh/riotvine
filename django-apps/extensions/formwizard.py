"""

FormWizard class -- implements a multi-page form, validating between each
step and storing the form's state as HTML hidden fields so that no state is
stored on the server side.

This extends ``django.contrib.formtools.wizard.FormWizard`` to add support for file fields.

"""
import logging
import cPickle as pickle

from django.http import Http404
from django.forms import BooleanField
from django.conf import settings
from django.contrib.formtools import wizard

from extensions.utils import security_hash

_log = logging.getLogger('extensions.formwizard')


class FormWizard(wizard.FormWizard):
    def get_form(self, step, data=None, files=None):
        """Helper method that returns the Form instance for the given step.

        ``step`` is zero-based.

        """
        return self.form_list[step](data, files, prefix=self.prefix_for_step(step), initial=self.initial.get(step, None))

    def __call__(self, request, *args, **kwargs):
        """
        Main method that does all the hard work, conforming to the Django view
        interface.
        """
        if 'extra_context' in kwargs:
            self.extra_context.update(kwargs['extra_context'])
        current_step = self.determine_step(request, *args, **kwargs)
        self.parse_params(request, *args, **kwargs)

        # Sanity check.
        if current_step >= self.num_steps():
            raise Http404('Step %s does not exist' % current_step)

        # For each previous step, verify the hash and process.
        # TODO: Move "hash_%d" to a method to make it configurable.
        for i in range(current_step):
            form = self.get_form(i, request.POST, request.FILES)
            posted_hash = request.POST.get("hash_%d" % i, '')
            computed_hash = self.security_hash(request, form)
            if posted_hash != computed_hash:
                _log.error("Posted hash %s does not match computed hash %s at step-0 %s", posted_hash, computed_hash, i)
                return self.render_hash_failure(request, i)
            self.process_step(request, form, i)

        # Process the current step. If it's valid, go to the next step or call
        # done(), depending on whether any steps remain.
        if request.method == 'POST':
            form = self.get_form(current_step, request.POST, request.FILES)
        else:
            form = self.get_form(current_step)
        if form.is_valid():
            self.process_step(request, form, current_step)
            next_step = current_step + 1

            # If this was the last step, validate all of the forms one more
            # time, as a sanity check, and call done().
            num = self.num_steps()
            if next_step == num:
                final_form_list = [self.get_form(i, request.POST, request.FILES) for i in range(num)]

                # Validate all the forms. If any of them fail validation, that
                # must mean the validator relied on some other input, such as
                # an external Web site.
                for i, f in enumerate(final_form_list):
                    if not f.is_valid():
                        _log.error("Revalidation failed for form %s", f)
                        return self.render_revalidation_failure(request, i, f)
                return self.done(request, final_form_list)

            # Otherwise, move along to the next step.
            else:
                form = self.get_form(next_step)
                current_step = next_step

        return self.render(form, request, current_step)
    
    def security_hash(self, request, form):
        """
        Calculates the security hash for the given HttpRequest and Form instances.

        Subclasses may want to take into account request-specific information,
        such as the IP address.
        """
        return security_hash(request, form)


