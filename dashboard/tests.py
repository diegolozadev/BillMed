from django.test import TestCase
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal
from medicos.models import Medico, Produccion
from tarifas.models import Tarifa


class DashboardViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta General', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Dashboard', numero_documento='88888888',
            especialidad='Neumología Adulto', email='dash@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        for i in range(3):
            Produccion.objects.create(
                medico=cls.medico,
                servicio=cls.tarifa,
                precio_aplicado=cls.tarifa.precio,
                cantidad=i + 1,
                fecha_labor=date(2026, 6, 15),
                sede_momento='Principal',
                unidad_negocio_momento='SERVICIO MEDICO',
                registrado_por=cls.user,
            )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_dashboard_loads(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/dashboard.html')

    def test_dashboard_tarjetas_resumen(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['total_medicos'], 1)
        self.assertEqual(response.context['total_tarifas'], 1)
        self.assertEqual(response.context['total_registros'], 3)

    def test_dashboard_produccion_total(self):
        response = self.client.get(reverse('dashboard'))
        esperado = Decimal('50000') * Decimal('6')
        self.assertEqual(response.context['produccion_total'], esperado)

    def test_dashboard_graficos_context(self):
        response = self.client.get(reverse('dashboard'))
        self.assertIn('labels_json', response.context)
        self.assertIn('valores_json', response.context)
        self.assertIn('esp_labels_json', response.context)
        self.assertIn('esp_valores_json', response.context)
        self.assertIn('un_labels_json', response.context)
        self.assertIn('un_valores_json', response.context)
        self.assertIn('sede_labels_json', response.context)
        self.assertIn('sede_valores_json', response.context)

    def test_dashboard_producciones_recientes(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(len(response.context['recientes']), 3)

    def test_dashboard_sin_datos(self):
        Medico.objects.all().delete()
        Produccion.objects.all().delete()
        Tarifa.objects.all().delete()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_medicos'], 0)
        self.assertEqual(response.context['total_tarifas'], 0)
        self.assertEqual(response.context['total_registros'], 0)
        self.assertEqual(response.context['produccion_total'], 0)

    def test_dashboard_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
