from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Appointment
from catalog.models import Service

@login_required
def my_appointments(request):
    appointments = Appointment.objects.filter(user=request.user).select_related('service')
    return render(request, 'appointments/my_appointments.html', {'appointments': appointments})

@login_required
def book_appointment(request, service_id=None):
    services = Service.objects.all()
    selected_service = None
    if service_id:
        selected_service = get_object_or_404(Service, pk=service_id)

    if request.method == 'POST':
        service_id = request.POST.get('service')
        date = request.POST.get('date')
        time = request.POST.get('time')
        notes = request.POST.get('notes', '')

        if service_id and date and time:
            service = get_object_or_404(Service, pk=service_id)
            Appointment.objects.create(
                user=request.user,
                service=service,
                date=date,
                time=time,
                notes=notes,
            )
            messages.success(request, 'Agendamento realizado com sucesso! Aguarde a confirmação.')
            return redirect('my_appointments')
        else:
            messages.error(request, 'Preencha todos os campos obrigatórios.')

    context = {
        'services': services,
        'selected_service': selected_service,
        'today': timezone.now().date(),
    }
    return render(request, 'appointments/book.html', context)

@login_required
def cancel_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, user=request.user)
    if appointment.status in ['pending', 'confirmed']:
        appointment.status = 'cancelled'
        appointment.save()
        messages.success(request, 'Agendamento cancelado.')
    return redirect('my_appointments')
