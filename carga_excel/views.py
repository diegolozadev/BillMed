from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class CargaExcelView(LoginRequiredMixin, TemplateView):
    template_name = 'carga_excel/carga_excel.html'
