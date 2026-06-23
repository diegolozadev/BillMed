from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse_lazy
from medicos.forms import MedicoForm
from .models import Medico, Produccion, Tarifa
from django.views.generic import DeleteView, ListView, DetailView, UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count # Importante para buscar por varios campos
from datetime import datetime
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Sum, Count, F, Max, Min
import openpyxl

# Create your views here.

# view para listar los médicos
class MedicoListView(LoginRequiredMixin, ListView):
    model = Medico
    template_name = 'medicos/medico_list.html'
    context_object_name = 'medicos'
    paginate_by = 12
    
    
    def get_queryset(self):
        # Usamos prefetch_related para traer los servicios de un solo golpe
        queryset = Medico.objects.prefetch_related('servicios')
        
        # Lógica de búsqueda por medicos
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q) | 
                Q(numero_documento__icontains=q)
            )
        
        return queryset.order_by('nombre')
    
    def get_context_data(self, **kwargs):
        # primero obtenemos el contexto basico de la ListView
        context = super().get_context_data(**kwargs)
        
        #Obtenemos el queryset filtrado (sin paginar)
        queryset_filtrado = self.get_queryset()
        
        # Agregamos el conteo total al contexto
        context['total_medicos'] = queryset_filtrado.count()
        
        return context

# view para mostrar el detalle de un médico y permitir su edición
class MedicoDetailView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Medico
    form_class = MedicoForm # Importante: asignar formulario
    template_name = 'medicos/medico_detail.html'
    context_object_name = 'medico'
    success_message = "¡Médico %(nombre)s actualizado con éxito!"
    
    # 1. HEREDAMOS DE PermissionRequiredMixin (arriba)
    # 2. DEFINIMOS EL PERMISO (app.permiso en minúsculas)
    permission_required = 'medicos.change_medico'

    # 3. Si no tiene permiso, muestra el error 403 (Prohibido)
    raise_exception = True

    # A dónde redirigir tras guardar con éxito
    success_url = reverse_lazy('medico-list')

# view para crear un nuevo médico
class MedicoCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Medico
    form_class = MedicoForm # Importante: asignar formulario
    template_name = 'medicos/medico_create.html'
    context_object_name = 'medico'
    success_message = "¡Médico %(nombre)s creado con éxito!"
    
    # 1. HEREDAMOS DE PermissionRequiredMixin (arriba)
    # 2. DEFINIMOS EL PERMISO (app.permiso en minúsculas)
    permission_required = 'medicos.add_medico'

    # 3. Si no tiene permiso, muestra el error 403 (Prohibido)
    raise_exception = True
    
    # A dónde redirigir tras guardar con éxito
    success_url = reverse_lazy('medico-list')
    
    def form_valid(self, form):
        # El objeto 'form.instance' es el médico que se está creando
        # Le asignamos el usuario que está navegando (self.request.user)
        form.instance.registrado_por = self.request.user
        
        # Luego llamamos al método original para que guarde todo
        return super().form_valid(form)
    

# view para cargar producciones (servicios realizados por un médico) de forma masiva
@login_required
def cargar_produccion_medico(request, medico_id):
    """
    Registra de forma masiva la producción mensual de un médico.
    Captura el precio actual de la tarifa y lo guarda permanentemente
    en cada registro para evitar cambios históricos.
    """
    # 1. Obtener datos iniciales
    medico = get_object_or_404(Medico, pk=medico_id)
    # Traemos los servicios del médico para el formulario
    servicios = medico.servicios.all()
    hoy = timezone.now().date()

    if request.method == 'POST':
        fecha_labor = request.POST.get('fecha_labor')
        # Obtenemos las listas enviadas desde los múltiples inputs del HTML
        servicios_ids = request.POST.getlist('servicio_id')
        cantidades = request.POST.getlist('cantidad')

        # OPTIMIZACIÓN: Traemos todos los objetos de Tarifa de una vez
        # Así evitamos hacer una consulta a la DB por cada fila de la tabla
        tarifas_dict = {str(t.id): t for t in Tarifa.objects.filter(id__in=servicios_ids)}
        
        registros_a_crear = []

        # 2. Procesar las entradas del formulario
        for servicio_id, cant in zip(servicios_ids, cantidades):
            try:
                # Validamos que la cantidad sea un número entero y positivo
                valor = int(cant) if cant and int(cant) > 0 else 0
            except ValueError:
                valor = 0
            
            if valor > 0:
                # Obtenemos el objeto tarifa desde nuestro diccionario en memoria
                servicio_obj = tarifas_dict.get(servicio_id)
                
                if servicio_obj:
                    # Creamos la instancia en memoria (sin guardar aún)
                    registros_a_crear.append(
                        Produccion(
                            medico=medico,
                            servicio=servicio_obj,
                            cantidad=valor,
                            fecha_labor=fecha_labor,
                            registrado_por=request.user,
                            # PUNTO CLAVE: "Congelamos" el precio actual aquí
                            precio_aplicado=servicio_obj.precio, # Esto protege el histórico si la tarifa sube después
                            sede_momento=medico.sede, # Viene del modelo Medico
                            unidad_negocio_momento=servicio_obj.unidad_negocio, # Viene de Tarifa
                            subunidad_momento=servicio_obj.subunidad_procedimientos
                        )
                    )

        # 3. Validaciones de negocio
        if not registros_a_crear:
            messages.error(request, "¡Atención! No se ingresó ninguna cantidad válida. Intente de nuevo.")
            return render(request, 'medicos/cargar_produccion.html', {
                'medico': medico,
                'servicios': servicios,
                'hoy': hoy,
                'fecha_seleccionada': fecha_labor, # Mantenemos la fecha para comodidad del usuario
            })

        # 4. Carga masiva
        try:
            # bulk_create inserta todos los registros en una sola sentencia SQL
            Produccion.objects.bulk_create(registros_a_crear)
            messages.success(request, f"Se registraron nuevos servicios para el médico {medico.nombre} con éxito.")
            return redirect('medico-list')
        except Exception as e:
            # Manejo de errores por si algo falla en la base de datos
            messages.error(request, f"Hubo un error al guardar: {str(e)}")

    # Respuesta para método GET
    return render(request, 'medicos/cargar_produccion.html', {
        'medico': medico,
        'servicios': servicios,
        'hoy': hoy
    })

# view para listar las producciones de todos los médicos
class ProduccionListView(LoginRequiredMixin, ListView):
    model = Produccion
    template_name = 'medicos/produccion_list.html'
    context_object_name = 'producciones'
    paginate_by = 10
    
    def get_queryset(self):
        # Mantenemos la lógica de filtrado para la tabla
        queryset = super().get_queryset().select_related('medico', 'servicio')
        
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        medico_id = self.request.GET.get('medico')

        if fecha_inicio and fecha_fin:
            queryset = queryset.filter(fecha_labor__range=[fecha_inicio, fecha_fin])
        
        if medico_id:
            queryset = queryset.filter(medico_id=medico_id)
            
        return queryset.order_by('-fecha_labor', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # TOTAL GLOBAL: Este contador ignora los filtros del queryset
        # Muestra absolutamente todo lo que hay en la tabla Produccion
        context['total_general'] = Produccion.objects.count()
        
        context['medicos'] = Medico.objects.all()
        return context


# view para exportar a Excel la producción filtrada (con los campos congelados en el momento de la carga)
@login_required
def exportar_produccion_excel(request):
    # 1. Capturamos los filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    medico_id = request.GET.get('medico')

    # 2. Aplicamos filtros (Optimizado: solo traemos medico para nombre/documento)
    queryset = Produccion.objects.all().select_related('medico')
    
    if fecha_inicio and fecha_fin:
        queryset = queryset.filter(fecha_labor__range=[fecha_inicio, fecha_fin])
    if medico_id:
        queryset = queryset.filter(medico_id=medico_id)

    # 3. Libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado Producción"

    # Encabezados (11 columnas)
    headers = [
        'Fecha', 'Documento', 'Especialidad', 'Médico', 
        'C. Operación', 'Servicio', 'U. Negocio', 'Sub-Unidad', 
        'Cantidad', 'Precio Aplicado', 'Subtotal'
    ]
    ws.append(headers)

    # 4. Llenamos las filas usando los campos "_momento"
    total_general = 0
    for p in queryset:
        valor_subtotal = p.subtotal 
        total_general += valor_subtotal
        
        ws.append([
            p.fecha_labor.strftime('%d/%m/%Y') if p.fecha_labor else '—',
            p.medico.numero_documento,
            p.medico.especialidad,
            p.medico.nombre,
            p.sede_momento,            # Dato guardado en Produccion
            p.servicio.nombre,         # Nombre del servicio
            p.unidad_negocio_momento,  # Dato guardado en Produccion
            p.subunidad_momento or '—', # Dato guardado en Produccion
            p.cantidad,
            p.precio_aplicado,         # Dato guardado en Produccion
            valor_subtotal
        ])

    # Fila final de Total
    ws.append(['', '', '', '', '', '', '', '', 'TOTAL GENERAL:', '', total_general])

    # 5. Configuración de respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="Reporte_Produccion.xlsx"'
    
    wb.save(response)
    return response


# view para preparar el recibo (pantalla de selección de fechas y resumen) y luego imprimirlo (pantalla limpia para impresión)
@login_required
def preparar_recibo(request, medico_id):
    medico = get_object_or_404(Medico, pk=medico_id)
    
    # Obtenemos las fechas del filtro GET
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    producciones = None
    total = 0

    if fecha_inicio and fecha_fin:
        # Filtramos la producción del médico en el rango de fechas
        qs = Produccion.objects.filter(
            medico=medico,
            fecha_labor__range=[fecha_inicio, fecha_fin]
        )

        # Agrupamos los servicios para que no aparezcan duplicados
        producciones = qs.values(
            'servicio__nombre', 
            'servicio__precio',
            'servicio__unidad_negocio'
        ).annotate(
            # Min trae la fecha más antigua de ese grupo de servicios
            antigua_fecha=Min('fecha_labor'),
            # Max trae la fecha más reciente de ese grupo de servicios
            ultima_fecha=Max('fecha_labor'), 
            # Sumamos las cantidades totales del servicio
            cantidad_total=Sum('cantidad'),
            # Calculamos el subtotal acumulado (precio * cantidad)
            subtotal_agrupado=Sum(F('precio_aplicado') * F('cantidad'))
        ).order_by('-cantidad_total')
        
        # Calculamos el gran total de toda la liquidación
        resultado_total = qs.aggregate(
            total_general=Sum(F('precio_aplicado') * F('cantidad'))
        )
        total = resultado_total['total_general'] or 0

    return render(request, 'medicos/preparar_recibo.html', {
        'medico': medico,
        'producciones': producciones,
        'total': total,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })

# view para mostrar el recibo en formato limpio para impresión
@login_required
def imprimir_recibo(request, medico_id):
    medico = get_object_or_404(Medico, pk=medico_id)
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    
    # Convertimos los strings a objetos date
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        fecha_inicio = None
        fecha_fin = None

    producciones = None
    total = 0

    # Filtramos y agrupamos solo si tenemos las fechas
    if fecha_inicio and fecha_fin:
        qs = Produccion.objects.filter(
            medico=medico,
            fecha_labor__range=[fecha_inicio, fecha_fin]
        )

        # Aplicamos la misma lógica de agrupación que en preparar_recibo
        producciones = qs.values(
            'servicio__nombre', 
            'servicio__precio',
            'servicio__unidad_negocio'
        ).annotate(
            cantidad_total=Sum('cantidad'),
            subtotal_agrupado=Sum(F('precio_aplicado') * F('cantidad'))
        ).order_by('-cantidad_total')
        
        # Cálculo del total general
        resultado_total = qs.aggregate(
            total_general=Sum(F('precio_aplicado') * F('cantidad'))
        )
        total = resultado_total['total_general'] or 0
    else:
        producciones = []

    return render(request, 'medicos/recibo_impresion_final.html', {
        'medico': medico,
        'producciones': producciones,
        'total': total,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'hoy': timezone.now()
    })
    
# Vista para editar un registro de producción específico (en caso de que se necesite corregir algo manualmente)
class ProduccionUpdateView(SuccessMessageMixin, UpdateView):
    model = Produccion
    fields = ['fecha_labor', 'cantidad', 'medico', 'servicio']
    template_name = 'medicos/produccion_update.html'
    success_url = reverse_lazy('produccion-list')
    success_message = "¡Registro de producción actualizado con éxito!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Inyectamos clases de Bootstrap a los select
        form.fields['medico'].widget.attrs.update({'class': 'form-select border-0 bg-light'})
        form.fields['servicio'].widget.attrs.update({'class': 'form-select border-0 bg-light'})
        return form


# Vista para eliminar un registro de producción específico (en caso de que se necesite eliminar un error)
class ProduccionDeleteView(SuccessMessageMixin, DeleteView):
    model = Produccion
    template_name = 'medicos/produccion_confirm_delete.html'
    success_url = reverse_lazy('produccion-list')
    success_message = "¡Registro de producción eliminado con éxito!"