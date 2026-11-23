from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_appointments, name='my_appointments'),
    path('agendar/', views.book_appointment, name='book_appointment'),
    path('agendar/<int:service_id>/', views.book_appointment, name='book_service'),
    path('cancelar/<int:pk>/', views.cancel_appointment, name='cancel_appointment'),
]
