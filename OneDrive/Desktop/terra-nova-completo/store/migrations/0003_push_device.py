from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_payment_gateway'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(unique=True)),
                ('p256dh', models.CharField(max_length=200)),
                ('auth', models.CharField(max_length=80)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('user_agent', models.CharField(blank=True, max_length=240)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
