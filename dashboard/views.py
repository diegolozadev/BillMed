from django.db.models import Sum, F, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
import json
from medicos.models import Medico, Produccion
from tarifas.models import Tarifa
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # --- Summary Cards ---
        context['total_medicos'] = Medico.objects.count()
        context['total_tarifas'] = Tarifa.objects.count()

        produccion_total = Produccion.objects.aggregate(
            total=Sum(F('precio_aplicado') * F('cantidad'))
        )['total'] or 0
        context['produccion_total'] = produccion_total

        produccion_mes = Produccion.objects.filter(
            fecha_labor__gte=first_of_month
        ).aggregate(
            total=Sum(F('precio_aplicado') * F('cantidad'))
        )['total'] or 0
        context['produccion_mes'] = produccion_mes

        total_registros = Produccion.objects.count()
        context['total_registros'] = total_registros

        # --- Monthly trend (last 6 months) ---
        datos_raw = Produccion.objects.annotate(
            mes=TruncMonth('fecha_labor')
        ).values('mes').annotate(
            total=Sum(F('precio_aplicado') * F('cantidad'))
        ).order_by('mes')[:6]

        labels = [d['mes'].strftime('%b %Y') if d['mes'] else 'S/F' for d in datos_raw]
        valores = [float(d['total']) if d['total'] else 0 for d in datos_raw]

        context['labels_json'] = json.dumps(labels)
        context['valores_json'] = json.dumps(valores)

        # --- Production by specialty ---
        esp_raw = Produccion.objects.values(
            'medico__especialidad'
        ).annotate(
            total=Sum(F('precio_aplicado') * F('cantidad'))
        ).order_by('-total')[:8]

        esp_labels = [e['medico__especialidad'] or 'Sin especificar' for e in esp_raw]
        esp_valores = [float(e['total']) for e in esp_raw]

        context['esp_labels_json'] = json.dumps(esp_labels)
        context['esp_valores_json'] = json.dumps(esp_valores)

        # --- Production by business unit ---
        un_raw = Produccion.objects.values(
            'unidad_negocio_momento'
        ).annotate(
            total=Sum(F('precio_aplicado') * F('cantidad'))
        ).order_by('-total')

        un_labels = [u['unidad_negocio_momento'] or 'Sin unidad' for u in un_raw]
        un_valores = [float(u['total']) for u in un_raw]

        context['un_labels_json'] = json.dumps(un_labels)
        context['un_valores_json'] = json.dumps(un_valores)

        # --- Recent productions (last 10) ---
        recientes = Produccion.objects.select_related(
            'medico', 'servicio'
        ).order_by('-fecha_registro')[:10]

        context['recientes'] = recientes

        # --- Distribution by sede ---
        sede_raw = Medico.objects.values('sede').annotate(
            total=Count('id')
        ).order_by('-total')

        sede_labels = [s['sede'] or 'Sin sede' for s in sede_raw]
        sede_valores = [s['total'] for s in sede_raw]

        context['sede_labels_json'] = json.dumps(sede_labels)
        context['sede_valores_json'] = json.dumps(sede_valores)

        return context
