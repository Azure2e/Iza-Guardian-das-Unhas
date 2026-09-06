from .models import PushDevice
from . import webpush


def send_to_devices(devices, title, body, url='/m/'):
    sent, gone = 0, 0
    payload = {'title': title, 'body': body, 'url': url}
    for device in devices:
        try:
            status, _ = webpush.send_web_push(device.as_subscription(), payload)
        except Exception:
            continue
        if status in (404, 410):
            device.active = False
            device.save(update_fields=['active'])
            gone += 1
        elif status in (201, 200):
            sent += 1
    return sent, gone


def notify_all(title, body, url='/m/'):
    return send_to_devices(PushDevice.objects.filter(active=True), title, body, url)


def notify_email(email, title, body, url='/m/'):
    if not email:
        return 0, 0
    return send_to_devices(PushDevice.objects.filter(active=True, email__iexact=email), title, body, url)
