import unicodedata
from django.test import TestCase
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from datetime import date, timedelta
from decimal import Decimal
from .models import Medico, Produccion
from tarifas.models import Tarifa
from .forms import MedicoForm, ProduccionForm


class MedicoModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.medico = Medico.objects.create(
            nombre='Dr. Perez',
            numero_documento='12345678',
            especialidad='Neumología Adulto',
            email='drperez@test.com',
            telefono='555-1234',
            sede='Principal',
            registrado_por=cls.user,
        )

    def test_creacion_medico(self):
        self.assertEqual(self.medico.nombre, 'Dr. Perez')
        self.assertEqual(self.medico.numero_documento, '12345678')
        self.assertEqual(self.medico.especialidad, 'Neumología Adulto')

    def test_str_medico(self):
        self.assertIn('Dr. Perez', str(self.medico))

    def test_documento_unico(self):
        with self.assertRaises(Exception):
            Medico.objects.create(
                nombre='Otro',
                numero_documento='12345678',
                especialidad='Cardiología',
                email='otro@test.com',
            )

    def test_email_unico(self):
        with self.assertRaises(Exception):
            Medico.objects.create(
                nombre='Otro',
                numero_documento='87654321',
                especialidad='Cardiología',
                email='drperez@test.com',
            )


class ProduccionModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta General', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Perez', numero_documento='12345678',
            especialidad='Neumología Adulto', email='drperez@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        cls.produccion = Produccion.objects.create(
            medico=cls.medico,
            servicio=cls.tarifa,
            precio_aplicado=cls.tarifa.precio,
            cantidad=3,
            fecha_labor=date.today(),
            sede_momento=cls.medico.sede,
            unidad_negocio_momento=cls.tarifa.unidad_negocio,
            registrado_por=cls.user,
        )

    def test_creacion_produccion(self):
        self.assertEqual(self.produccion.cantidad, 3)
        self.assertEqual(self.produccion.precio_aplicado, 50000)
        self.assertEqual(self.produccion.medico, self.medico)
        self.assertEqual(self.produccion.servicio, self.tarifa)

    def test_subtotal_property(self):
        self.assertEqual(self.produccion.subtotal, Decimal('150000'))

    def test_str_produccion(self):
        self.assertIn('Dr. Perez', str(self.produccion))
        self.assertIn('Consulta General', str(self.produccion))


class MedicoFormTest(TestCase):
    def test_form_valido(self):
        data = {
            'nombre': 'Dr. Test',
            'numero_documento': '111111',
            'especialidad': 'Cardiología',
            'email': 'drtest@test.com',
            'telefono': '555-0000',
            'sede': 'Principal',
        }
        form = MedicoForm(data=data)
        self.assertTrue(form.is_valid())

    def test_form_campos_requeridos(self):
        form = MedicoForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('numero_documento', form.errors)
        self.assertIn('email', form.errors)


class ProduccionFormTest(TestCase):
    def test_cantidad_negativa_invalida(self):
        form = ProduccionForm(data={'fecha_labor': '2024-01-15', 'cantidad': -5})
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad', form.errors)

    def test_cantidad_valida(self):
        form = ProduccionForm(data={'fecha_labor': '2024-01-15', 'cantidad': 5})
        self.assertTrue(form.is_valid())


class MedicoListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        for i in range(15):
            Medico.objects.create(
                nombre=f'Dr. Medico {i}',
                numero_documento=f'{i:08d}',
                especialidad='Neumología Adulto',
                email=f'medico{i}@test.com',
                sede='Principal',
                registrado_por=cls.user,
            )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_lista_medicos(self):
        response = self.client.get(reverse('medico-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/medico_list.html')
        self.assertIn('medicos', response.context)

    def test_busqueda_medico_por_nombre(self):
        response = self.client.get(reverse('medico-list'), {'q': 'Medico 1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Medico 1', str(response.content))

    def test_busqueda_medico_por_documento(self):
        response = self.client.get(reverse('medico-list'), {'q': '00000005'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('00000005', str(response.content))

    def test_paginacion_medicos(self):
        response = self.client.get(reverse('medico-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['medicos']), 12)

    def test_lista_requiere_login(self):
        self.client.logout()
        response = self.client.get(reverse('medico-list'))
        self.assertEqual(response.status_code, 302)


class MedicoCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        content_type = ContentType.objects.get_for_model(Medico)
        permission = Permission.objects.get(
            content_type=content_type,
            codename='add_medico',
        )
        cls.user.user_permissions.add(permission)

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_crear_medico_get(self):
        response = self.client.get(reverse('medico-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/medico_create.html')

    def test_crear_medico_post(self):
        data = {
            'nombre': 'Dr. Nuevo',
            'numero_documento': '99999999',
            'especialidad': 'Cardiología',
            'email': 'nuevo@test.com',
            'telefono': '555-9999',
            'sede': 'Cabecera',
        }
        response = self.client.post(reverse('medico-create'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Medico.objects.filter(numero_documento='99999999').exists())
        medico = Medico.objects.get(numero_documento='99999999')
        self.assertEqual(medico.registrado_por, self.user)

    def test_crear_medico_sin_permiso_403(self):
        user_sin = User.objects.create_user(username='noperm', password='testpass')
        self.client.login(username='noperm', password='testpass')
        response = self.client.get(reverse('medico-create'))
        self.assertEqual(response.status_code, 403)


class MedicoDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        content_type = ContentType.objects.get_for_model(Medico)
        permission = Permission.objects.get(
            content_type=content_type,
            codename='change_medico',
        )
        cls.user.user_permissions.add(permission)
        cls.medico = Medico.objects.create(
            nombre='Dr. Editable',
            numero_documento='11111111',
            especialidad='Alergología',
            email='editable@test.com',
            sede='Principal',
            registrado_por=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_editar_medico_get(self):
        response = self.client.get(reverse('medico-detail', args=[self.medico.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/medico_detail.html')

    def test_editar_medico_post(self):
        response = self.client.post(
            reverse('medico-detail', args=[self.medico.pk]),
            {
                'nombre': 'Dr. Editado',
                'numero_documento': '11111111',
                'especialidad': 'Cardiología',
                'email': 'editado@test.com',
                'telefono': '555-1111',
                'sede': 'Prado',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.medico.refresh_from_db()
        self.assertEqual(self.medico.nombre, 'Dr. Editado')
        self.assertEqual(self.medico.especialidad, 'Cardiología')

    def test_editar_medico_sin_permiso_403(self):
        user_sin = User.objects.create_user(username='noperm2', password='testpass')
        self.client.login(username='noperm2', password='testpass')
        response = self.client.get(reverse('medico-detail', args=[self.medico.pk]))
        self.assertEqual(response.status_code, 403)


class CargarProduccionViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa1 = Tarifa.objects.create(
            nombre='Consulta General', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.tarifa2 = Tarifa.objects.create(
            nombre='Espirometria', precio=80000,
            unidad_negocio='LAB. PULMONAR', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Produccion', numero_documento='22222222',
            especialidad='Neumología Adulto', email='prod@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        cls.medico.servicios.add(cls.tarifa1, cls.tarifa2)

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_cargar_produccion_get(self):
        response = self.client.get(
            reverse('cargar-produccion-medico', args=[self.medico.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/cargar_produccion.html')

    def test_cargar_produccion_post_masiva(self):
        data = {
            'fecha_labor': '2024-06-15',
            'servicio_id': [str(self.tarifa1.pk), str(self.tarifa2.pk)],
            'cantidad': ['3', '2'],
        }
        response = self.client.post(
            reverse('cargar-produccion-medico', args=[self.medico.pk]),
            data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Produccion.objects.count(), 2)
        p1 = Produccion.objects.get(servicio=self.tarifa1)
        self.assertEqual(p1.cantidad, 3)
        self.assertEqual(p1.precio_aplicado, 50000)
        self.assertEqual(p1.sede_momento, 'Principal')
        self.assertEqual(p1.unidad_negocio_momento, 'SERVICIO MEDICO')

    def test_cargar_produccion_sin_cantidades(self):
        data = {
            'fecha_labor': '2024-06-15',
            'servicio_id': [str(self.tarifa1.pk)],
            'cantidad': ['0'],
        }
        response = self.client.post(
            reverse('cargar-produccion-medico', args=[self.medico.pk]),
            data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Produccion.objects.count(), 0)
        messages_list = list(response.context['messages'])
        self.assertEqual(len(messages_list), 1)
        msg_text = unicodedata.normalize('NFC', str(messages_list[0]))
        expected = unicodedata.normalize('NFC', '¡Atención! No se ingresó ninguna cantidad válida. Intente de nuevo.')
        self.assertEqual(msg_text, expected)

    def test_cargar_produccion_requiere_login(self):
        self.client.logout()
        response = self.client.get(
            reverse('cargar-produccion-medico', args=[self.medico.pk])
        )
        self.assertEqual(response.status_code, 302)


class ProduccionListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. List', numero_documento='33333333',
            especialidad='Neumología Adulto', email='list@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        for i in range(5):
            Produccion.objects.create(
                medico=cls.medico,
                servicio=cls.tarifa,
                precio_aplicado=cls.tarifa.precio,
                cantidad=i + 1,
                fecha_labor=date(2024, 6, 15),
                sede_momento='Principal',
                unidad_negocio_momento='SERVICIO MEDICO',
                registrado_por=cls.user,
            )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_lista_producciones(self):
        response = self.client.get(reverse('produccion-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/produccion_list.html')

    def test_filtro_producciones_por_fecha(self):
        response = self.client.get(reverse('produccion-list'), {
            'fecha_inicio': '2024-06-01', 'fecha_fin': '2024-06-30',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['producciones']), 5)

    def test_filtro_producciones_fuera_de_rango(self):
        response = self.client.get(reverse('produccion-list'), {
            'fecha_inicio': '2024-01-01', 'fecha_fin': '2024-01-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['producciones']), 0)

    def test_filtro_producciones_por_medico(self):
        response = self.client.get(reverse('produccion-list'), {
            'medico': self.medico.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['producciones']), 5)


class ExportarProduccionExcelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Excel', numero_documento='44444444',
            especialidad='Neumología Adulto', email='excel@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        Produccion.objects.create(
            medico=cls.medico, servicio=cls.tarifa,
            precio_aplicado=cls.tarifa.precio, cantidad=2,
            fecha_labor=date(2024, 6, 15),
            sede_momento='Principal',
            unidad_negocio_momento='SERVICIO MEDICO',
            registrado_por=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_exportar_excel(self):
        response = self.client.get(reverse('exportar-produccion-excel'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('Reporte_Produccion.xlsx', response['Content-Disposition'])


class ReciboViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Recibo', numero_documento='55555555',
            especialidad='Neumología Adulto', email='recibo@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        for i in range(3):
            Produccion.objects.create(
                medico=cls.medico, servicio=cls.tarifa,
                precio_aplicado=cls.tarifa.precio, cantidad=i + 1,
                fecha_labor=date(2024, 6, 15),
                sede_momento='Principal',
                unidad_negocio_momento='SERVICIO MEDICO',
                registrado_por=cls.user,
            )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_preparar_recibo_sin_fechas(self):
        response = self.client.get(
            reverse('preparar-recibo', args=[self.medico.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/preparar_recibo.html')

    def test_preparar_recibo_con_fechas(self):
        response = self.client.get(
            reverse('preparar-recibo', args=[self.medico.pk]),
            {'fecha_inicio': '2024-06-01', 'fecha_fin': '2024-06-30'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['producciones'])
        self.assertEqual(response.context['total'], 300000)

    def test_imprimir_recibo_con_fechas(self):
        response = self.client.get(
            reverse('imprimir-recibo', args=[self.medico.pk]),
            {'fecha_inicio': '2024-06-01', 'fecha_fin': '2024-06-30'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'medicos/recibo_impresion_final.html')

    def test_imprimir_recibo_sin_fechas(self):
        response = self.client.get(
            reverse('imprimir-recibo', args=[self.medico.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['producciones'], [])


class ProduccionUpdateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Update', numero_documento='66666666',
            especialidad='Neumología Adulto', email='update@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        cls.produccion = Produccion.objects.create(
            medico=cls.medico, servicio=cls.tarifa,
            precio_aplicado=cls.tarifa.precio, cantidad=2,
            fecha_labor=date(2024, 6, 15),
            sede_momento='Principal',
            unidad_negocio_momento='SERVICIO MEDICO',
            registrado_por=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_editar_produccion_post(self):
        response = self.client.post(
            reverse('produccion-update', args=[self.produccion.pk]),
            {
                'fecha_labor': '2024-07-20',
                'cantidad': 10,
                'medico': self.medico.pk,
                'servicio': self.tarifa.pk,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.cantidad, 10)
        self.assertEqual(self.produccion.fecha_labor.isoformat(), '2024-07-20')


class ProduccionDeleteViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass')
        cls.tarifa = Tarifa.objects.create(
            nombre='Consulta', precio=50000,
            unidad_negocio='SERVICIO MEDICO', registrado_por=cls.user,
        )
        cls.medico = Medico.objects.create(
            nombre='Dr. Delete', numero_documento='77777777',
            especialidad='Neumología Adulto', email='delete@test.com',
            sede='Principal', registrado_por=cls.user,
        )
        cls.produccion = Produccion.objects.create(
            medico=cls.medico, servicio=cls.tarifa,
            precio_aplicado=cls.tarifa.precio, cantidad=2,
            fecha_labor=date(2024, 6, 15),
            sede_momento='Principal',
            unidad_negocio_momento='SERVICIO MEDICO',
            registrado_por=cls.user,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_eliminar_produccion_post(self):
        pk = self.produccion.pk
        response = self.client.post(
            reverse('produccion-delete', args=[pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produccion.objects.filter(pk=pk).exists())
