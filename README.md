# Essence K Importados

Loja online em Django para produtos importados: perfumes, K-beauty, skincare e eletronicos. O sistema possui vitrine com precos em USD e conversao automatica para BRL, carrinho, checkout, area do cliente, pedidos, painel administrativo, upload de fotos, estoque, marcas, variantes de produto, relatorios e estrutura de pagamentos.

## Stack

- Backend: Python / Django 4.2
- Banco em desenvolvimento: SQLite
- Banco recomendado em producao: PostgreSQL
- Frontend: templates Django, HTML, CSS e JavaScript
- Uploads: pasta `media/`
- Pagamentos: sandbox local e integracao preparada para Mercado Pago
- Frete: calculo simulado por CEP, com estrutura para integrar Melhor Envio
- Cotacao: sistema de cotacao USD/BRL com fallback manual

## Rodar localmente

```bash
cd C:\paragua
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed
python manage.py seed_demo_products
python manage.py runserver
```

Acesse:

- Loja: http://127.0.0.1:8000/
- Painel Django: http://127.0.0.1:8000/admin/
- Dashboard da loja: http://127.0.0.1:8000/painel/

## Variaveis de ambiente

Crie um arquivo `.env` a partir do `.env.example`. Nunca envie o `.env` para repositorio ou hospedagem publica.

Campos principais:

```env
SECRET_KEY=gere-uma-chave-forte-com-50-ou-mais-caracteres
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=
SITE_URL=http://127.0.0.1:8000

PAYMENT_GATEWAY=sandbox
PAYMENT_SANDBOX=True
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_USE_SANDBOX_LINK=True
MP_MAX_INSTALLMENTS=12

EXCHANGE_RATE_API_URL=https://economia.awesomeapi.com.br/json/last/USD-BRL
EXCHANGE_RATE_CACHE_SECONDS=3600
EXCHANGE_RATE_DEFAULT_USD_BRL=5.50
```

Em producao:

```env
DEBUG=False
SITE_URL=https://essencekimportados.com.br
ALLOWED_HOSTS=essencekimportados.com.br,www.essencekimportados.com.br
CSRF_TRUSTED_ORIGINS=https://essencekimportados.com.br,https://www.essencekimportados.com.br
DATABASE_URL=postgresql://usuario:senha@host:5432/banco?sslmode=require
DB_ENGINE=django.db.backends.postgresql
DB_NAME=nome_do_banco
DB_USER=usuario_do_banco
DB_PASSWORD=senha_do_banco
DB_HOST=host_do_banco
DB_PORT=5432
PAYMENT_GATEWAY=mercadopago
PAYMENT_SANDBOX=False
MP_USE_SANDBOX_LINK=False
```

## Persistencia na Vercel

Em producao na Vercel, nao use SQLite em `/tmp` para dados reais. Esse filesystem e temporario: produtos, marcas, categorias, pedidos e clientes cadastrados pelo admin podem desaparecer em cold starts ou redeploys.

Configure um banco persistente, de preferencia Neon Postgres pelo Vercel Marketplace:

```bash
vercel integration add neon --plan free_v3 -m region=gru1 -m auth=false
vercel env pull .env.production.local --environment=production --yes
```

Depois rode as migracoes no banco persistente:

```bash
$env:DJANGO_SETTINGS_MODULE="paraguashopping.settings.vercel"
# carregue DATABASE_URL/POSTGRES_URL da Vercel ou do arquivo .env.production.local
python manage.py migrate --noinput
```

As settings da Vercel usam `DATABASE_URL` ou `POSTGRES_URL`. Se essas variaveis nao existirem em ambiente Vercel, a aplicacao bloqueia o uso silencioso de SQLite temporario.

Uploads feitos pelo painel em producao tambem precisam ser persistentes. Na Vercel, `USE_DATABASE_MEDIA_STORAGE_ON_VERCEL=True` salva novos arquivos de mídia no banco persistente e evita que fotos de produtos, marcas e categorias desaparecam em cold starts.

## Precos USD / BRL

O sistema suporta precos em dolares americanos (USD) como moeda primaria. A conversao para reais (BRL) e feita automaticamente usando a cotacao armazenada no modelo `ExchangeRate`. A cotacao pode ser atualizada manualmente pelo painel ou via API.

- Produtos podem ter `price_usd` (preco em dolar) ou `price` (preco em real, legado)
- Cards e detalhes exibem preco em USD com equivalente em BRL
- O carrinho e checkout trabalham em BRL para pagamento
- Pedidos registram a cotacao usada no momento da compra

Fallback: se nao houver cotacao ativa, o sistema usa R$ 5,50 por padrao.

Em producao na Vercel, a cotacao e atualizada automaticamente todos os dias pela rota protegida `/cron/update-exchange-rate/`, configurada em `vercel.json`. A Vercel chama essa rota via Cron Job e envia `Authorization: Bearer $CRON_SECRET`; por isso `CRON_SECRET` precisa existir nas variaveis de ambiente da Vercel.

As moedas atualizadas sao definidas em `EXCHANGE_RATE_PAIRS`. O padrao e `USD-BRL`, mas a lista aceita mais pares separados por virgula quando o site passar a exibir outras moedas, por exemplo:

```env
EXCHANGE_RATE_PAIRS=USD-BRL,EUR-BRL,PYG-BRL
```

Comandos uteis:

```bash
python manage.py update_exchange_rate
python manage.py update_exchange_rate --rate 5.1763 --source "manual"
python manage.py convert_prices_to_usd
```

O comando `convert_prices_to_usd` preenche `price_usd`, `sale_price_usd` e `cost_price_usd` a partir dos valores BRL legados usando a cotacao ativa. Ele nao apaga produtos nem pedidos.

## Produtos demonstrativos

Para popular uma base visual de teste com perfumes lacrados, perfumes fracionados, marcas, volumes de 10ml a 80ml, precos em dolar e conversao para real:

```bash
python manage.py seed_demo_products
```

O comando cria ou garante:

- categorias `Perfumes`, `Perfumes Fracionados`, `Beleza Coreana` e `Eletronicos`;
- `Perfumes Fracionados` como subcategoria de `Perfumes`;
- marcas como Carolina Herrera, Dior, Paco Rabanne, Chanel, Anker, Apple, COSRX e outras;
- produtos tradicionais/lacrados;
- produtos fracionados com variacoes de volume;
- estoque por variacao;
- precos USD com BRL calculado pela cotacao ativa.

Ele pode ser executado varias vezes sem duplicar dados.

## Marcas e Variantes

- **Marcas** (`Brand`): cadastro de marcas com nome, slug, logo e descricao
- **Variantes** (`ProductVariant`): para perfumes fracionados e outras variacoes (volume, cor, tamanho), cada variante tem preco USD, estoque e GTIN proprios
- **Subcategorias**: categorias podem ter categorias pai para hierarquia (ex: Perfumes > Fracionados)

## Identificacao por produto, GTIN e codigo de barras

O painel personalizado possui busca em `Painel > Produtos > Novo produto`.

A consulta funciona em camadas:

- primeiro procura produtos e variantes ja cadastrados no banco;
- tambem aceita busca por nome, marca ou termo, como `Good Girl`, `serum`, `creme` ou `Sauvage`;
- depois consulta um catalogo local de apoio para codigos conhecidos;
- depois consulta bases abertas como Open Food Facts e Open Beauty Facts;
- se `COSMOS_API_TOKEN` estiver configurado no `.env`, consulta tambem a API Cosmos/Bluesoft.

Configure o token, se tiver:

```env
COSMOS_API_TOKEN=seu-token-cosmos
```

Os codigos sao normalizados antes de salvar: espacos, tracos e caracteres nao numericos sao removidos. O sistema aceita GTIN/EAN com 8, 12, 13 ou 14 digitos.

Se um codigo for lido pela camera mas nao existir nas bases configuradas, o painel cria uma sugestao de rascunho com o codigo preenchido para a administradora completar manualmente. Depois de salvo uma vez, o mesmo codigo passa a ser encontrado localmente.

Para imagens demonstrativas coerentes com nome, marca e categoria, use:

```bash
python manage.py sync_product_images
```

O comando cria imagens locais principais sem apagar fotos antigas. Fotos reais da administradora podem substituir essas imagens pelo painel.

## Pagamentos

O app `payments` possui dois modos:

- `sandbox`: modo de teste. Cria pagamento simulado, nao cobra dinheiro e nao confirma pagamento automaticamente.
- `mercadopago`: modo real preparado para Pix, cartao/link de pagamento, parcelamento e webhook.

### Mercado Pago

Para pagamento real, a administradora deve criar a propria conta Mercado Pago. O dinheiro das vendas cai na conta dela. O site usa apenas credenciais de API da plataforma, nunca senha bancaria.

Configure no `.env`:

```env
PAYMENT_GATEWAY=mercadopago
PAYMENT_SANDBOX=False
MP_ACCESS_TOKEN=APP_USR-...
MP_PUBLIC_KEY=APP_USR-...
MP_WEBHOOK_SECRET=uma-chave-secreta-criada-para-validar-webhook
MP_USE_SANDBOX_LINK=False
MP_MAX_INSTALLMENTS=12
SITE_URL=https://essencekimportados.com.br
```

Configure o webhook no painel do Mercado Pago:

```text
https://essencekimportados.com.br/pagamento/webhook/mercadopago/
```

### Pagamento pendente e nova tentativa

Quando o cliente cria um pedido e nao paga (ex: gera Pix mas nao conclui), o pedido fica como "aguardando pagamento". Na pagina "Meus Pedidos > Ver detalhes", o cliente pode:

- **Continuar pagamento**: reutiliza ou cria nova preferencia no Mercado Pago para o mesmo pedido.
- **Alterar forma de pagamento**: permite trocar de Pix para cartao (ou vice-versa) sem criar novo pedido.

O sistema suporta multiplas tentativas de pagamento por pedido. Ao criar nova tentativa, as anteriores sao desativadas (`is_active=False`). Quando o webhook confirma pagamento aprovado, todas as outras tentativas pendentes sao canceladas e o estoque baixa uma unica vez.

**Regras:**
- O valor enviado ao Mercado Pago sempre vem do banco (nunca do frontend).
- O estoque so baixa apos pagamento aprovado via webhook ou aprovacao manual no painel.
- O pedido nao e cancelado automaticamente se o Pix expirar — a tentativa expira, mas o pedido continua acessivel.
- O cliente so pode tentar pagar novamente enquanto o pedido estiver em status `created` ou `awaiting_payment` com `payment_status=pending`.

**Testar no sandbox:**
1. Criar pedido com Pix.
2. Nao pagar — voltar para "Meus Pedidos".
3. Abrir detalhes do pedido.
4. Clicar "Continuar pagamento" ou "Alterar forma de pagamento".
5. Confirmar que nao criou novo pedido e que o pagamento redireciona ao Mercado Pago.

### O que o site nao faz

- Nao salva numero de cartao.
- Nao salva CVV.
- Nao processa cartao diretamente no servidor.
- Nao deve exibir tokens no frontend.
- Nao deve marcar pedido como pago sem confirmacao real do gateway, exceto acao manual consciente da administradora no painel.

## Estoque e status do pedido

O estoque de produtos de pronta entrega baixa somente quando o pagamento e confirmado. A confirmacao usa uma regra centralizada para evitar baixa duplicada caso o webhook chegue mais de uma vez ou alguem clique novamente em confirmar.

Pedidos que dependem de contato manual ficam aguardando combinacao direta com a loja.

## Imagens

Uploads de produto sao salvos em:

```text
media/products/
```

Formatos aceitos:

- JPG/JPEG
- PNG
- WEBP
- HEIC/HEIF, com `pillow-heif`

O painel personalizado converte fotos de produto para JPEG otimizado e limita tamanho/resolucao. Se uma imagem estiver ausente no disco, o site usa fallback por categoria:

- perfumes: `static/img/defaults/default-perfumes.jpg`
- beleza coreana: `static/img/defaults/default-beleza-coreana.jpg`
- eletronicos: `static/img/defaults/default-eletronicos.jpg`
- generico: `static/img/defaults/default-default.jpg`

Em desenvolvimento, `paraguashopping/urls.py` serve `MEDIA_URL` quando `DEBUG=True`. Em producao, configure o servidor/hospedagem para servir os arquivos de `media/`.

## Frete

O frete atual e simulado por regiao de CEP em `shipping/utils.py`. Para frete real, integre Melhor Envio ou outro provedor usando token no `.env`:

```env
MELHORENVIO_TOKEN=seu-token
MELHORENVIO_ENV=production
```

## Seguranca

- `.env`, `db.sqlite3` e `media/` estao no `.gitignore`.
- Senhas de usuarios sao armazenadas pelo sistema de hash do Django.
- Formularios usam CSRF.
- Dashboard personalizado usa `staff_member_required`.
- Clientes so acessam os proprios pedidos.
- Preco de custo, lucro e margem ficam apenas no dashboard/admin.
- Tokens de API (Mercado Pago, Melhor Envio) ficam apenas no `.env`, nunca no frontend.
- GTIN e codigos de barras sao consultados apenas no backend.
- `production.py` exige `SECRET_KEY` forte, `ALLOWED_HOSTS` e `SITE_URL` publico.
- Cookies seguros e HTTPS sao configurados no settings de producao.

Antes de publicar:

```bash
python manage.py check --deploy --settings=paraguashopping.settings.production
python manage.py test
```

## Estrutura

```text
paragua/
├── accounts/          usuarios, login, cadastro, perfil e pedidos do cliente
├── cart/              carrinho com suporte a variantes
├── core/              home, paginas, configuracoes e cotacao USD/BRL
├── dashboard/         painel administrativo personalizado
├── orders/            checkout, pedidos com USD/BRL e cotacao registrada
├── payments/          sandbox e gateway Mercado Pago
├── products/          produtos, categorias, marcas, variantes e imagens
├── shipping/          calculo de frete
├── templates/         HTML
├── static/            CSS, JS, logo SVG e imagens padrao
└── media/             uploads locais
```
