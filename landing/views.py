from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class LandingView(TemplateView):
    template_name = 'landing/landing.html'


class PruebasView(LoginRequiredMixin, TemplateView):
    template_name = 'landing/pruebas.html'


class ManualView(LoginRequiredMixin, TemplateView):
    template_name = 'landing/manual.html'
