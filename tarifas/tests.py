from django.test import TestCase
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from .models import Tarifa
from .forms import TarifaForm


class TarifaModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta General',
            precio=50000,
            unidad_negocio='SERVICIO MEDICO',
            registrado_por=cls.user,
        )

    def test_creacion_tarifa(self):
        self.assertEqual(self.tarifa.nombre, 'Consulta General')
        self.assertEqual(self.tarifa.precio, 50000)
        self.assertEqual(self.tarifa.unidad_negocio, 'SERVICIO MEDICO')

    def test_str_tarifa(self):
        self.assertIn('Consulta General', str(self.tarifa))
        self.assertIn('50.000', str(self.tarifa))


class TarifaFormTest(TestCase):
    def test_form_valido(self):
        form_data = {
            'nombre': 'Espirometria',
            'precio': 80000,
            'unidad_negocio': 'LAB. PULMONAR',
        }
        form = TarifaForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_campos_requeridos(self):
        form = TarifaForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('precio', form.errors)
        self.assertIn('unidad_negocio', form.errors)


class TarifaListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        for i in range(15):
            Tarifa.objects.create(
                nombre=f'Servicio {i}',
                precio=10000 * (i + 1),
                unidad_negocio='SERVICIO MEDICO' if i % 2 == 0 else 'LAB. PULMONAR',
                registrado_por=cls.user,
            )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_lista_tarifas(self):
        response = self.client.get(reverse('tarifas'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tarifas/tarifas.html')
        self.assertIn('tarifas', response.context)

    def test_busqueda_tarifa_por_nombre(self):
        response = self.client.get(reverse('tarifas'), {'q': 'Servicio 1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Servicio 1', str(response.content))

    def test_busqueda_tarifa_por_unidad_negocio(self):
        response = self.client.get(reverse('tarifas'), {'q': 'LAB. PULMONAR'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('LAB. PULMONAR', str(response.content))

    def test_paginacion_tarifas(self):
        response = self.client.get(reverse('tarifas'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['tarifas']), 10)

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse('tarifas'))
        self.assertEqual(response.status_code, 302)


class TarifaCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        content_type = ContentType.objects.get_for_model(Tarifa)
        permission = Permission.objects.get(
            content_type=content_type,
            codename='add_tarifa',
        )
        cls.user.user_permissions.add(permission)

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_crear_tarifa_get(self):
        response = self.client.get(reverse('tarifa_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tarifas/tarifa_create.html')
        self.assertIsInstance(response.context['form'], TarifaForm)

    def test_crear_tarifa_post(self):
        data = {
            'nombre': 'Nueva Tarifa',
            'precio': 75000,
            'unidad_negocio': 'PROCEDIMIENTOS',
            'descripcion': 'Descripcion de prueba',
        }
        response = self.client.post(reverse('tarifa_create'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Tarifa.objects.filter(nombre='Nueva Tarifa').exists())
        tarifa = Tarifa.objects.get(nombre='Nueva Tarifa')
        self.assertEqual(tarifa.registrado_por, self.user)

    def test_crear_tarifa_post_invalido(self):
        response = self.client.post(reverse('tarifa_create'), {'nombre': '', 'precio': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'nombre', 'Este campo es obligatorio.')

    def test_crear_tarifa_sin_permiso_403(self):
        user_sin_permiso = User.objects.create_user(username='noperm', password='testpass')
        self.client.login(username='noperm', password='testpass')
        response = self.client.get(reverse('tarifa_create'))
        self.assertEqual(response.status_code, 403)


class TarifaDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        content_type = ContentType.objects.get_for_model(Tarifa)
        permission = Permission.objects.get(
            content_type=content_type,
            codename='change_tarifa',
        )
        cls.user.user_permissions.add(permission)
        cls.tarifa = Tarifa.objects.create(
            nombre='Tarifa a editar',
            precio=60000,
            unidad_negocio='SERVICIO MEDICO',
            registrado_por=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_editar_tarifa_get(self):
        response = self.client.get(reverse('tarifa_detail', args=[self.tarifa.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tarifas/tarifa_detail.html')

    def test_editar_tarifa_post(self):
        response = self.client.post(
            reverse('tarifa_detail', args=[self.tarifa.pk]),
            {'nombre': 'Tarifa Editada', 'precio': 99999, 'unidad_negocio': 'PROCEDIMIENTOS'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.tarifa.refresh_from_db()
        self.assertEqual(self.tarifa.nombre, 'Tarifa Editada')
        self.assertEqual(self.tarifa.precio, 99999)

    def test_editar_tarifa_sin_permiso_403(self):
        user_sin_permiso = User.objects.create_user(username='noperm2', password='testpass')
        self.client.login(username='noperm2', password='testpass')
        response = self.client.get(reverse('tarifa_detail', args=[self.tarifa.pk]))
        self.assertEqual(response.status_code, 403)
