from django import forms
from django.utils.translation import ugettext_lazy as _

from rdutils.text import slugify
from common.forms import ValidatingModelForm
from siteconfig.models import SiteConfig


class SiteConfigForm(ValidatingModelForm):
    class Meta:
        model = SiteConfig

    def clean_name(self):
        name = slugify(self.cleaned_data['name'])
        try:
            s = SiteConfig.objects.all()
            if self.instance.pk:
                s = s.exclude(pk=self.instance.pk)
            s.get(name__iexact=name)
        except SiteConfig.DoesNotExist:
            return name
        raise forms.ValidationError(_("That configuration parameter name already exists."))

