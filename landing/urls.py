from django.urls import path
from .views import LandingView, PruebasView

urlpatterns = [
    path('', LandingView.as_view(), name='landing'),
    path('pruebas/', PruebasView.as_view(), name='pruebas'),
]
