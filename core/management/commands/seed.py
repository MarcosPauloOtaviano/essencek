"""
Usage: python manage.py seed
Creates initial categories, products, store settings and a next trip entry.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from decimal import Decimal


class Command(BaseCommand):
    help = 'Popula o banco de dados com dados iniciais de exemplo'

    def handle(self, *args, **kwargs):
        from core.models import StoreSettings, NextTrip
        from products.models import Category, Product
        import datetime

        self.stdout.write('Criando configurações da loja...')
        store, _ = StoreSettings.objects.get_or_create(pk=1)
        store.store_name = 'Essence K Importados'
        store.whatsapp = '5511999999999'
        store.instagram = 'shopparaguai'
        store.home_headline = 'Importados selecionados com curadoria'
        store.home_subheadline = 'Perfumes, K-beauty e skincare com pronta entrega e encomendas mensais.'
        store.order_mode_active = True
        store.shipping_active = True
        store.save()
        self.stdout.write(self.style.SUCCESS('  OK: Configuracoes salvas'))

        self.stdout.write('Criando categorias...')
        cats = [
            ('Perfumes', 'perfumes', 'Perfumes internacionais importados selecionados.', 1),
            ('Beleza Coreana', 'beleza-coreana', 'Produtos de beleza e skincare coreanos.', 2),
            ('Eletrônicos', 'eletronicos', 'Eletrônicos e acessórios tech importados.', 3),
        ]
        category_objs = {}
        for name, slug, desc, order in cats:
            cat, created = Category.objects.get_or_create(slug=slug, defaults={
                'name': name, 'description': desc, 'is_active': True, 'order': order
            })
            category_objs[slug] = cat
            action = 'Criada' if created else 'Já existe'
            self.stdout.write(f'  {action}: {name}')

        self.stdout.write('Criando produtos...')
        products_data = [
            # Perfumes
            {
                'name': 'Perfume Importado Premium', 'brand': 'Maison Luxe',
                'category': 'perfumes', 'price': Decimal('389.90'), 'cost_price': Decimal('180.00'),
                'stock': 5, 'status': 'available', 'is_featured': True, 'is_active': True,
                'short_description': 'Fragrância amadeirada e floral com longa duração.',
                'description': 'Um perfume elegante com notas de baunilha, sândalo e flores brancas. Importado diretamente da Europa. Duração de 8h na pele.',
            },
            {
                'name': 'Body Splash Luxo', 'brand': 'Aqua Belle',
                'category': 'perfumes', 'price': Decimal('159.90'), 'sale_price': Decimal('129.90'),
                'cost_price': Decimal('60.00'), 'stock': 8, 'status': 'available',
                'is_on_sale': True, 'is_active': True,
                'short_description': 'Refrescante e suave, ideal para o dia a dia.',
                'description': 'Body splash com fragrância floral e cítrica. Embalagem de 250ml. Fórmula não oleosa.',
            },
            {
                'name': 'Perfume Feminino Elegance', 'brand': 'Noir Paris',
                'category': 'perfumes', 'price': Decimal('540.00'), 'cost_price': Decimal('240.00'),
                'stock': 2, 'status': 'low_stock', 'is_featured': True, 'is_active': True,
                'short_description': 'Sofisticado e marcante, para ocasiões especiais.',
                'description': 'Perfume feminino importado com notas de rosa, almíscar e patchouli. 100ml EDP.',
            },
            # Beleza Coreana
            {
                'name': 'Sérum Facial Coreano', 'brand': 'K-Beauty Lab',
                'category': 'beleza-coreana', 'price': Decimal('129.90'), 'cost_price': Decimal('55.00'),
                'stock': 12, 'status': 'available', 'is_featured': True, 'is_active': True,
                'short_description': 'Hidratação profunda com ácido hialurônico e centella.',
                'description': 'Sérum concentrado com 3% de ácido hialurônico e extrato de centella asiática. Textura leve, absorção rápida. 30ml.',
            },
            {
                'name': 'Máscara Facial Hidratante', 'brand': 'Seoul Glow',
                'category': 'beleza-coreana', 'price': Decimal('79.90'), 'sale_price': Decimal('59.90'),
                'cost_price': Decimal('28.00'), 'stock': 20, 'status': 'available',
                'is_on_sale': True, 'is_active': True,
                'short_description': 'Kit com 5 máscaras para hidratação intensiva.',
                'description': 'Máscaras de tecido com soro hidratante. Ideal para peles secas e sensíveis. Pack com 5 unidades.',
            },
            {
                'name': 'Creme Clareador Coreano', 'brand': 'White Purity',
                'category': 'beleza-coreana', 'price': Decimal('189.90'), 'cost_price': Decimal('80.00'),
                'stock': 0, 'status': 'pre_order', 'is_pre_order': True, 'is_active': True,
                'short_description': 'Creme clareador com niacinamida e ácido kójico.',
                'description': 'Creme facial clareador importado com fórmula coreana de dupla ação. Reduz manchas e uniformiza o tom da pele. 50g.',
            },
            # Eletrônicos
            {
                'name': 'Fone Bluetooth Premium', 'brand': 'SoundMax',
                'category': 'eletronicos', 'price': Decimal('349.90'), 'cost_price': Decimal('150.00'),
                'stock': 7, 'status': 'available', 'is_featured': True, 'is_active': True,
                'short_description': 'Cancelamento de ruído ativo, 30h de bateria.',
                'description': 'Fone over-ear com ANC (cancelamento de ruído ativo), conexão Bluetooth 5.3, até 30 horas de bateria e microfone integrado.',
                'weight': Decimal('0.250'), 'height': Decimal('20'), 'width': Decimal('18'), 'length': Decimal('8'),
            },
            {
                'name': 'Smartwatch Ultra', 'brand': 'TechPro',
                'category': 'eletronicos', 'price': Decimal('589.90'), 'sale_price': Decimal('499.90'),
                'cost_price': Decimal('220.00'), 'stock': 4, 'status': 'available',
                'is_on_sale': True, 'is_featured': True, 'is_active': True,
                'short_description': 'Monitor cardíaco, GPS, resistente à água.',
                'description': 'Smartwatch com tela AMOLED 1.8", monitor cardíaco, GPS integrado, resistência 5ATM e bateria de 7 dias. Compatível com Android e iOS.',
                'weight': Decimal('0.060'), 'height': Decimal('5'), 'width': Decimal('5'), 'length': Decimal('3'),
            },
            {
                'name': 'Caixa de Som Portátil', 'brand': 'BoomBlast',
                'category': 'eletronicos', 'price': Decimal('259.90'), 'cost_price': Decimal('110.00'),
                'stock': 0, 'status': 'pre_order', 'is_pre_order': True, 'is_active': True,
                'short_description': 'Som 360°, à prova d\'água, 20h de bateria.',
                'description': 'Caixa de som portátil com tecnologia de som 360°, resistência IPX7, 20 horas de bateria e True Wireless Stereo (TWS).',
                'weight': Decimal('0.400'), 'height': Decimal('15'), 'width': Decimal('8'), 'length': Decimal('8'),
            },
        ]

        for data in products_data:
            cat_slug = data.pop('category')
            cat = category_objs.get(cat_slug)
            name = data['name']
            product, created = Product.objects.get_or_create(
                slug=slugify(name),
                defaults={**data, 'category': cat}
            )
            action = 'Criado' if created else 'Já existe'
            self.stdout.write(f'  {action}: {name}')

        self.stdout.write('Criando próxima viagem...')
        import datetime
        today = datetime.date.today()
        trip_date = today.replace(day=1) + datetime.timedelta(days=32)
        trip_date = trip_date.replace(day=15)
        deadline = trip_date - datetime.timedelta(days=7)
        NextTrip.objects.get_or_create(
            trip_date=trip_date,
            defaults={
                'order_deadline': deadline,
                'message': 'Aproveite! Encomendas abertas para a próxima viagem.',
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  OK: Viagem em {trip_date}, limite {deadline}'))

        self.stdout.write(self.style.SUCCESS('\nSeed concluido! Dados de exemplo criados com sucesso.'))
        self.stdout.write('Crie um superusuário com: python manage.py createsuperuser')
