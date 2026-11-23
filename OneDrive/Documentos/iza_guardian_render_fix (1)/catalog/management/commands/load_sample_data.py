from django.core.management.base import BaseCommand
from catalog.models import Category, Service
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Carrega dados de exemplo para o app Iza Guardian'

    def handle(self, *args, **options):
        # Categorias
        cat_francesinha, _ = Category.objects.get_or_create(name='Francesinha')
        cat_floral, _ = Category.objects.get_or_create(name='Floral')
        cat_geometrica, _ = Category.objects.get_or_create(name='Geométrica')
        cat_glitter, _ = Category.objects.get_or_create(name='Glitter')
        cat_classica, _ = Category.objects.get_or_create(name='Clássica')
        cat_minimalista, _ = Category.objects.get_or_create(name='Minimalista')
        cat_chrome, _ = Category.objects.get_or_create(name='Chrome')

        services_data = [
            {
                'name': 'Franchesinha Dourada',
                'price': 70.00,
                'is_featured': True,
                'category': cat_francesinha,
                'image': 'ZTIRl.jpg',
                'description': 'Francesinha elegante com pontas douradas e brilho sutil.'
            },
            {
                'name': 'Florais Delicados',
                'price': 85.00,
                'is_featured': True,
                'category': cat_floral,
                'image': '1f00i.jpg',
                'description': 'Arte floral delicada com flores rosas e detalhes dourados.'
            },
            {
                'name': 'Design Geométrico',
                'price': 90.00,
                'is_featured': True,
                'category': cat_geometrica,
                'image': 'kfgoe.jpg',
                'description': 'Design moderno com linhas geométricas abstratas.'
            },
            {
                'name': 'Clássica Francesinha',
                'price': 60.00,
                'is_featured': False,
                'category': cat_classica,
                'image': 'Q20Dv.jpg',
                'description': 'Francesinha clássica, limpa e atemporal.'
            },
            {
                'name': 'Glitter Rosa',
                'price': 75.00,
                'is_featured': False,
                'category': cat_glitter,
                'image': 'utn16.jpg',
                'description': 'Unhas brilhantes com glitter rosa delicado.'
            },
            {
                'name': 'Minimalista',
                'price': 65.00,
                'is_featured': False,
                'category': cat_minimalista,
                'image': '58MHa.jpg',
                'description': 'Design minimalista com linhas finas e detalhes dourados.'
            },
            {
                'name': 'Vermelho Chrome',
                'price': 88.00,
                'is_featured': False,
                'category': cat_chrome,
                'image': 'X6iJ3.jpg',
                'description': 'Vermelho chrome brilhante e sofisticado.'
            },
        ]

        media_path = settings.MEDIA_ROOT
        for data in services_data:
            image_name = data.pop('image')
            service, created = Service.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            if created or not service.image:
                # Copy image if exists
                src = os.path.join(media_path, image_name)
                if os.path.exists(src):
                    service.image = f'services/{image_name}'
                    # Ensure services dir
                    os.makedirs(os.path.join(media_path, 'services'), exist_ok=True)
                    import shutil
                    shutil.copy(src, os.path.join(media_path, 'services', image_name))
                    service.save()
                    self.stdout.write(self.style.SUCCESS(f'Criado: {service.name}'))
                else:
                    service.save()
                    self.stdout.write(self.style.SUCCESS(f'Criado sem imagem: {service.name}'))

        self.stdout.write(self.style.SUCCESS('Dados de exemplo carregados com sucesso!'))
