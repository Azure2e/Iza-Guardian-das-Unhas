from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from store.models import Category, Product, Discount


class Command(BaseCommand):
    help = 'Popula a loja TERRA NOVA com categorias, produtos e cupom demo.'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                'admin', 'iris.p@example.org', 'TerraNova@2026',
                first_name='Marina', last_name='Terra',
            )
            self.stdout.write(self.style.SUCCESS('Admin criado: admin / TerraNova@2026'))

        catalog = {
            'Alimentação': '🥣',
            'Higiene': '🛁',
            'Saúde': '💊',
            'Acessórios': '🧸',
            'Farmácia clínica': '🩺',
        }
        cats = {}
        for name, icon in catalog.items():
            cats[name], _ = Category.objects.get_or_create(name=name, defaults={'icon': icon})

        products = [
            ('Alimentação', 'Ração Premium Cães Adultos 15kg', 'Fórmula completa com proteínas de alta digestibilidade, ômega 3 e 6 para pelagem. Indicada para cães a partir de 12 meses.', '189.90', 24, True, '🐕'),
            ('Alimentação', 'Ração Gatos Indoor 7,5kg', 'Controle de bolas de pelo, taurina extra e croquete menor para felinos que vivem em apartamento.', '142.50', 18, True, '🐈'),
            ('Alimentação', 'Petisco Natural de Fígado 200g', 'Snack desidratado sem conservantes artificiais. Treino e reforço positivo.', '29.90', 40, False, '🦴'),
            ('Higiene', 'Shampoo Hipoalergênico 500ml', 'pH balanceado para peles sensíveis. Uso veterinário, fragrância suave de capim-limão.', '47.00', 30, False, '🧴'),
            ('Higiene', 'Tapete Higiênico 30 un.', 'Camada absorvente extra e gel que prende odores. 80x60 cm.', '64.90', 22, False, '🧻'),
            ('Saúde', 'Antipulgas Spot-On Cães 10-25kg', 'Proteção mensal contra pulgas, carrapatos e sarnas. Aplicação tópica.', '89.90', 16, True, '💧'),
            ('Saúde', 'Vermífugo Comprimido Cães/Gatos', 'Amplo espectro. Dose conforme peso. Consulte o veterinário TERRA NOVA.', '36.00', 50, False, '💊'),
            ('Saúde', 'Suplemento Articular 60 cap.', 'Glicosamina, condroitina e MSM para cães idosos ou atletas.', '118.00', 12, True, '🦴'),
            ('Acessórios', 'Coleira Refletiva Ajustável', 'Nylon resistente, fivela de segurança e costura reforçada. Várias cores.', '39.90', 35, False, '🦮'),
            ('Acessórios', 'Cama Ortopédica M', 'Espuma de alta densidade e capa removível. Alívio para articulações.', '219.00', 8, True, '🛏️'),
            ('Farmácia clínica', 'Soro Fisiológico Estéril 250ml', 'Uso clínico e limpeza de feridas. Embalagem hospitalar.', '14.50', 60, False, '🧪'),
            ('Farmácia clínica', 'Kit Primeiros Socorros Pet', 'Gaze, atadura, antisséptico e tesoura ponta romba. Para casa e viagem.', '79.90', 14, True, '🧰'),
            ('Higiene', 'Escova Dental + Enzimática', 'Reduz tártaro e mau hálito. Cerdas macias e gel sabor frango.', '32.90', 28, False, '🦷'),
            ('Alimentação', 'Ração Filhotes Mini 3kg', 'DHA para desenvolvimento cognitivo e cálcio calibrado para raças pequenas.', '72.40', 20, False, '🐶'),
        ]
        created = 0
        for cat, name, desc, price, stock, feat, emoji in products:
            _, was = Product.objects.get_or_create(
                name=name,
                defaults={
                    'category': cats[cat],
                    'description': desc,
                    'price': Decimal(price),
                    'stock': stock,
                    'featured': feat,
                    'emoji': emoji,
                },
            )
            created += int(was)
        Discount.objects.get_or_create(
            code='TERRA10',
            defaults={'kind': Discount.KIND_PERCENT, 'value': Decimal('10'), 'max_uses': 200},
        )
        Discount.objects.get_or_create(
            code='CANA20',
            defaults={'kind': Discount.KIND_FIXED, 'value': Decimal('20'), 'max_uses': 80},
        )
        self.stdout.write(self.style.SUCCESS(f'Seed ok. Novos produtos: {created}'))
