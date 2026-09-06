from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='pix_txid',
            field=models.CharField(max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='pix_payload',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='gateway',
            field=models.CharField(default='local', max_length=32),
        ),
        migrations.AddField(
            model_name='order',
            name='gateway_payment_id',
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name='order',
            name='gateway_order_id',
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name='order',
            name='gateway_status',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='order',
            name='ticket_url',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='qr_base64',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='order',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PaymentEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gateway', models.CharField(max_length=32)),
                ('event_type', models.CharField(max_length=80)),
                ('external_id', models.CharField(blank=True, max_length=80)),
                ('payload', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='events', to='store.order')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
