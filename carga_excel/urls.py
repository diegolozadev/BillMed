from django.urls import path
from .views import CargaExcelView

urlpatterns = [
    path('cargar-excel/', CargaExcelView.as_view(), name='carga-excel'),
]
