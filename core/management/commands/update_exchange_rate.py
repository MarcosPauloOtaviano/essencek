from django.core.management.base import BaseCommand, CommandError

from core.services import save_usd_brl_rate, update_usd_brl_rate_from_api


class Command(BaseCommand):
    help = 'Atualiza a cotação USD/BRL pela API ou por valor manual.'

    def add_arguments(self, parser):
        parser.add_argument('--rate', help='Cotação manual, exemplo: 5.1688')
        parser.add_argument('--source', default='manual', help='Fonte da cotação manual')

    def handle(self, *args, **options):
        try:
            if options.get('rate'):
                rate = save_usd_brl_rate(options['rate'], source=options['source'])
            else:
                rate = update_usd_brl_rate_from_api()
        except Exception as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'Cotação ativa: 1 USD = R$ {rate.rate} ({rate.source})'))
