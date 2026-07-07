# Documentacao completa para IA - Essence K Importados

Atualizado em: 2026-07-02

Este arquivo foi criado para outra IA, desenvolvedor ou agente de codigo entender rapidamente o que existe no projeto, como ele funciona, onde estao as principais regras e quais cuidados tomar antes de alterar qualquer coisa.

Importante: este documento nao contem senha, token real, chave de API real, dados bancarios ou credenciais privadas. Nunca adicionar segredos neste arquivo.

---

## 1. Resumo do projeto

O projeto e uma loja online Django chamada **Essence K Importados**.

O foco comercial do site e:

- perfumes importados;
- perfumes fracionados;
- K-beauty e skincare;
- cosmeticos e produtos de cuidado pessoal;
- eletronicos selecionados como categoria secundaria.

O sistema possui:

- vitrine publica;
- categorias e subcategorias;
- marcas;
- produtos com preco em dolar e conversao para real;
- variantes de produto, principalmente volumes de perfumes fracionados;
- carrinho;
- checkout;
- pedidos;
- area do cliente;
- painel administrativo personalizado;
- Django Admin;
- upload local de fotos;
- imagens demonstrativas locais;
- identificacao por codigo de barras, GTIN, nome, marca ou termo;
- estrutura de pagamento sandbox e Mercado Pago;
- estrutura de webhook;
- frete simulado;
- relatorios;
- configuracoes da loja;
- proxima viagem e produtos sob encomenda.

O objetivo do projeto e ser uma loja pratica para a administradora cadastrar produtos, vender, controlar estoque e acompanhar pedidos.

---

## 2. Stack tecnica

Backend:

- Python
- Django 4.2.16
- SQLite em desenvolvimento
- PostgreSQL recomendado em producao

Frontend:

- Django Templates
- HTML
- CSS proprio em `static/css/style.css`
- JavaScript inline em alguns templates
- Font Awesome para icones
- `widget_tweaks` e `crispy_forms` para formularios

Imagens:

- uploads em `media/`
- imagens padrao em `static/img/defaults/`
- logos em `static/img/brand/`
- processamento com Pillow e pillow-heif

Pagamentos:

- modo sandbox local
- integracao preparada com Mercado Pago
- Pix, cartao/link de pagamento e webhook estruturados

Frete:

- calculo simulado por regiao de CEP
- estrutura para Melhor Envio via token

Cotacao:

- USD/BRL via modelo `ExchangeRate`
- API configuravel por `EXCHANGE_RATE_API_URL`
- fallback manual configuravel por `EXCHANGE_RATE_DEFAULT_USD_BRL`

---

## 3. Como rodar localmente

Projeto principal no computador:

```powershell
cd C:\paragua
```

Instalar dependencias, caso precise:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Rodar migracoes:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

Subir servidor local:

```powershell
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

URLs locais:

- Loja: `http://127.0.0.1:8000/`
- Admin Django: `http://127.0.0.1:8000/admin/`
- Painel personalizado: `http://127.0.0.1:8000/painel/`

Nao usar:

```powershell
python app.py
```

Este projeto nao e Flask nem arquivo unico. Ele e Django e sobe por `manage.py`.

---

## 4. Dependencias principais

Arquivo: `requirements.txt`

Dependencias atuais:

- `Django==4.2.16`
- `Pillow==10.4.0`
- `pillow-heif==0.18.0`
- `python-decouple==3.8`
- `whitenoise==6.7.0`
- `psycopg2-binary==2.9.9`
- `django-crispy-forms==2.3`
- `crispy-bootstrap5==2024.2`
- `django-widget-tweaks==1.5.0`
- `requests==2.32.3`
- `qrcode==7.4.2`

---

## 5. Estrutura de pastas

```text
C:\paragua
├── accounts/          usuarios, login, cadastro, perfil e pedidos do cliente
├── cart/              carrinho com suporte a variantes
├── core/              home, paginas, configuracoes, cotacao e comandos auxiliares
├── dashboard/         painel administrativo personalizado
├── orders/            checkout, pedidos, itens e servico de confirmacao de pagamento
├── payments/          pagamentos sandbox e Mercado Pago
├── products/          produtos, categorias, marcas, variantes, imagens e identificacao
├── reports/           app reservado/estrutura de relatorios
├── shipping/          calculo de frete simulado
├── paraguashopping/   settings, urls e wsgi
├── templates/         templates Django
├── static/            CSS, logos, imagens padrao
├── media/             uploads e imagens geradas localmente
├── manage.py
├── README.md
├── .env.example
└── requirements.txt
```

---

## 6. Apps Django

Apps instalados em `paraguashopping/settings/base.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    'core',
    'accounts',
    'products',
    'cart',
    'orders',
    'payments',
    'shipping',
    'dashboard',
    'reports',
]
```

Usuario customizado:

```python
AUTH_USER_MODEL = 'accounts.User'
```

---

## 7. Configuracoes

Settings principais:

- `paraguashopping/settings/base.py`
- `paraguashopping/settings/development.py`
- `paraguashopping/settings/production.py`

`manage.py` usa por padrao:

```python
DJANGO_SETTINGS_MODULE = 'paraguashopping.settings.development'
```

Em desenvolvimento:

- `DEBUG=True`
- banco SQLite em `db.sqlite3`
- `ALLOWED_HOSTS` inclui localhost e `.trycloudflare.com`
- `CSRF_TRUSTED_ORIGINS` inclui `https://*.trycloudflare.com`
- email via console
- pagamento em sandbox por padrao
- frete em sandbox

Em producao:

- `DEBUG=False`
- exige `ALLOWED_HOSTS`
- exige `SITE_URL` publico HTTPS
- exige `SECRET_KEY` forte
- usa PostgreSQL por variaveis de ambiente
- ativa HTTPS, cookies seguros, HSTS e headers de seguranca
- pagamento real via Mercado Pago se configurado

---

## 8. Variaveis de ambiente

Arquivo modelo:

```text
.env.example
```

Nunca commitar `.env`.

Principais variaveis:

```env
SECRET_KEY=
DEBUG=
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=
SITE_URL=

DB_ENGINE=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

STORE_PHONE=
STORE_INSTAGRAM=
STORE_EMAIL=
STORE_CEP_ORIGEM=

EXCHANGE_RATE_API_URL=
EXCHANGE_RATE_CACHE_SECONDS=
EXCHANGE_RATE_DEFAULT_USD_BRL=

COSMOS_API_TOKEN=

PAYMENT_GATEWAY=
PAYMENT_SANDBOX=
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_USE_SANDBOX_LINK=
MP_MAX_INSTALLMENTS=

MELHORENVIO_TOKEN=
MELHORENVIO_ENV=
```

Seguranca:

- tokens ficam apenas no backend;
- nunca expor token em template;
- nunca colocar token neste documento;
- nunca salvar senha bancaria;
- nunca salvar numero completo de cartao ou CVV.

---

## 9. URLs principais

Arquivo raiz:

```text
paraguashopping/urls.py
```

Mapeamento:

```text
/admin/       -> Django Admin
/             -> core.urls
/conta/       -> accounts.urls
/produtos/    -> products.urls
/carrinho/    -> cart.urls
/checkout/    -> orders.urls
/pagamento/   -> payments.urls
/painel/      -> dashboard.urls
```

Em desenvolvimento, `MEDIA_URL` e `STATIC_URL` sao servidos pelo Django quando `DEBUG=True`.

---

## 10. Modelos principais

### accounts.User

Arquivo:

```text
accounts/models.py
```

Extende `AbstractUser`.

Campos importantes:

- `email` unico
- `full_name`
- `cpf` unico opcional
- `whatsapp` unico (campo tecnico usado como telefone)
- endereco: `address`, `address_number`, `address_complement`, `neighborhood`, `city`, `state`, `cep`

Regras:

- email normalizado para lowercase;
- CPF normalizado para digitos;
- telefone normalizado para digitos;
- username sincronizado com email;
- validacoes em `accounts/validators.py`;
- formularios impedem duplicidade de email, CPF e telefone.

Objetivo:

- evitar que a mesma pessoa crie varias contas usando o mesmo email, CPF ou telefone.

### products.Brand

Arquivo:

```text
products/models.py
```

Campos:

- `name`
- `slug`
- `description`
- `logo`
- `is_active`

### products.Category

Campos:

- `name`
- `slug`
- `description`
- `image`
- `is_active`
- `order`
- `parent`

Permite hierarquia:

```text
Perfumes
  └── Perfumes Fracionados
Beleza Coreana
Eletronicos
```

### products.Product

Campos principais:

- `name`
- `slug`
- `brand` texto legado
- `brand_fk` FK para `Brand`
- `category`
- `short_description`
- `description`
- `price`
- `sale_price`
- `cost_price`
- `price_usd`
- `sale_price_usd`
- `cost_price_usd`
- `gtin`
- `is_fractioned`
- `has_variants`
- `stock`
- `status`
- `is_active`
- `is_featured`
- `is_on_sale`
- `is_pre_order`
- `weight`
- `height`
- `width`
- `length`
- `internal_notes`

Status publicos:

- `available`
- `low_stock`
- `pre_order`
- `out_of_stock`

Propriedades importantes:

- `current_price`
- `display_price_usd`
- `display_sale_price_usd`
- `price_brl`
- `sale_price_brl`
- `current_price_usd`
- `current_price_brl`
- `display_brand`
- `discount_percent`
- `gross_profit`
- `margin_percent`
- `main_image`
- `display_image_url`
- `can_add_to_cart`

### products.ProductImage

Campos:

- `product`
- `image`
- `alt_text`
- `is_main`
- `order`

Regras:

- processa imagem no `save`;
- converte upload para JPEG otimizado;
- garante apenas uma imagem principal por produto;
- se arquivo sumir do disco, usa fallback por categoria.

### products.ProductVariant

Usado principalmente em perfumes fracionados.

Campos:

- `product`
- `name`
- `volume_ml`
- `color`
- `size`
- `price_usd`
- `promotional_price_usd`
- `cost_price_usd`
- `stock`
- `sku`
- `gtin`
- `is_active`
- `order`

Regras:

- GTIN normalizado para digitos;
- cada variante pode ter estoque proprio;
- cada variante pode ter preco USD proprio;
- carrinho e pedido preservam a variante escolhida.

### cart.Cart e cart.CartItem

Campos:

- `Cart.user`
- `Cart.session_key`
- `CartItem.cart`
- `CartItem.product`
- `CartItem.variant`
- `CartItem.quantity`

Regras:

- suporta usuario logado e sessao anonima;
- merge de carrinho usa produto + variante;
- limita quantidade pelo estoque do produto ou da variante;
- subtotal em BRL e USD.

### orders.Order

Campos importantes:

- `customer`
- `order_number`
- dados snapshot do cliente
- endereco
- `subtotal`
- `shipping_cost`
- `total`
- `subtotal_usd`
- `total_usd`
- `exchange_rate`
- `payment_method`
- `payment_status`
- `payment_link`
- `gateway_payment_id`
- `status`
- rastreio
- timestamps

Status:

- `created`
- `awaiting_payment`
- `payment_confirmed`
- `partial_confirmed`
- `separating`
- `partial_shipped`
- `shipped`
- `completed`
- `cancelled`

Metodos de pagamento atuais no modelo:

- `pix`
- `credit_card`

Observacao: ja existiram fluxos por contato externo em templates/README, mas o modelo atual de choices esta com Pix e Cartao. Se reativar contato manual como metodo de pagamento, atualizar modelo, form, migration, views, templates e testes juntos.

### orders.OrderItem

Campos:

- `order`
- `product`
- `variant`
- `product_name`
- `product_brand`
- `unit_price`
- `quantity`
- `variant_name`
- `variant_volume_ml`
- `unit_price_usd`
- `product_category`
- `is_pre_order`
- `item_status`

Preserva dados no momento da compra.

### orders.PreOrderRequest

Controle de encomendas.

Campos:

- cliente opcional
- nome
- telefone
- produto opcional
- nome do produto
- status
- preco combinado
- link de pagamento
- notas
- viagem

### core.StoreSettings

Configuracoes da loja:

- nome da loja
- telefone da loja
- Instagram
- email
- CEP de origem
- gateway de pagamento
- logo

### core.NextTrip

Pagina/proxima viagem:

- destination
- departure_date
- return_date
- order_deadline
- notes
- is_active

### core.ExchangeRate

Cotacao USD/BRL:

- currency_pair
- rate
- source
- is_active
- fetched_at

Metodo:

- `ExchangeRate.get_usd_brl()`

### payments.Payment

Registra pagamento criado/processado:

- order
- gateway
- gateway_payment_id
- preference_id
- status
- payment_method
- amount
- amount_usd
- external_reference
- checkout_url
- qr_code
- qr_code_base64
- raw_response
- timestamps

### shipping.ShippingRate

Tabela de frete basica, mas hoje o fluxo principal usa simulacao por `shipping/utils.py`.

---

## 11. Fluxo publico da loja

### Home

Arquivo:

```text
core/views.py
templates/home.html
```

Mostra:

- destaque da loja;
- categorias;
- produtos em destaque;
- cotacao dolar/real;
- produtos e links de navegacao.

### Lista de produtos

Arquivos:

```text
products/views.py
templates/products/list.html
templates/products/_card.html
```

Funcionalidades:

- busca por nome, marca e GTIN;
- filtro por categoria;
- filtro por marca hierarquico;
- filtro por volume;
- filtro por status;
- promocao;
- destaque;
- paginacao;
- breadcrumb.

Hierarquia atual de filtros:

```text
Perfumes
  ├── Perfumes Fracionados
  ├── marcas de perfume
  └── volumes 10ml a 80ml

Beleza Coreana
  └── Beauty of Joseon, COSRX, Laneige

Eletronicos
  └── Anker, Apple, Samsung
```

O filtro de marca/volume aparece dentro da categoria aberta, nao solto no mesmo nivel.

### Detalhe do produto

Arquivo:

```text
templates/products/detail.html
```

Mostra:

- imagem principal;
- galeria;
- marca;
- categoria;
- preco USD;
- equivalente BRL;
- status;
- variantes se existirem;
- seletor de volume;
- adicionar ao carrinho;
- comprar agora;
- descricao;
- produtos relacionados.

Para produtos com variantes:

- usuario precisa escolher variante;
- preco e estoque mudam conforme variante;
- carrinho recebe `variant_id`.

---

## 12. Carrinho

Arquivos:

```text
cart/models.py
cart/utils.py
cart/views.py
templates/cart/cart.html
```

Funcionalidades:

- adicionar produto;
- adicionar variante;
- alterar quantidade;
- remover item;
- calcular frete simulado;
- selecionar frete;
- subtotal USD;
- subtotal BRL;
- mostrar volume/variante escolhida.

Regras:

- nao permite quantidade invalida;
- nao permite quantidade maior que estoque;
- se produto tem variantes, exige variante;
- estoque de variante limita carrinho;
- carrinho anonimo usa session;
- carrinho logado usa usuario.

---

## 13. Checkout e pedidos

Arquivos:

```text
orders/views.py
orders/forms.py
orders/models.py
orders/services.py
templates/checkout/checkout.html
templates/checkout/success.html
templates/accounts/orders.html
templates/accounts/order_detail.html
```

Fluxo:

1. usuario precisa estar logado;
2. carrinho nao pode estar vazio;
3. valida estoque do produto/variante;
4. formulario coleta dados de entrega;
5. calcula subtotal e total;
6. salva cotacao USD/BRL usada no pedido;
7. cria `Order`;
8. cria `OrderItem` com snapshot;
9. salva variante, nome da variante e volume;
10. limpa carrinho;
11. redireciona para sucesso ou pagamento.

Dados normalizados:

- email;
- telefone;
- CEP;
- UF.

Seguranca:

- cliente so ve os proprios pedidos;
- admin/staff pode acessar mais dados;
- URL de pedido filtra por usuario.

Estoque:

- nao baixa no checkout;
- baixa somente quando pagamento e confirmado por `orders/services.py`;
- a confirmacao evita baixa duplicada.

---

## 14. Pagamentos

Arquivos principais:

```text
payments/models.py
payments/services.py
payments/views.py
payments/gateways/base.py
payments/gateways/sandbox.py
payments/gateways/mercadopago.py
templates/checkout/pix.html
templates/checkout/payment_link.html
```

Modos:

### Sandbox

- usado em desenvolvimento;
- nao cobra dinheiro;
- cria pagamento simulado;
- deixa claro que e teste;
- util para validar fluxo sem credenciais reais.

### Mercado Pago

Preparado para:

- Pix;
- cartao/link de pagamento;
- checkout preference;
- webhook;
- validacao de assinatura;
- idempotencia;
- buscar pagamento no gateway;
- atualizar status.

Variaveis:

```env
PAYMENT_GATEWAY=mercadopago
PAYMENT_SANDBOX=False
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_USE_SANDBOX_LINK=False
MP_MAX_INSTALLMENTS=12
SITE_URL=https://dominio-real.com
```

Webhook esperado:

```text
/pagamento/webhook/mercadopago/
```

Ponto critico:

- sem credenciais reais, cliente nao paga de verdade;
- nao inventar token falso;
- para ativar real, administradora precisa criar conta propria no Mercado Pago;
- dinheiro deve cair na conta dela;
- nao pedir senha bancaria;
- pedir apenas credenciais/API/token da plataforma.

---

## 15. Frete

Arquivo:

```text
shipping/utils.py
```

O frete e simulado por regiao de CEP.

Funcoes:

- `get_cep_region`
- `calculate_shipping`

O carrinho chama rotas:

```text
/carrinho/calcular-frete/
/carrinho/selecionar-frete/
```

Futuro:

- integrar Melhor Envio ou outro provedor real usando `MELHORENVIO_TOKEN`.

---

## 16. Painel administrativo personalizado

Arquivos:

```text
dashboard/views.py
dashboard/urls.py
templates/dashboard/
```

Todas as views principais usam:

```python
@staff_member_required
```

Rotas:

```text
/painel/
/painel/produtos/
/painel/produtos/novo/
/painel/produtos/<id>/editar/
/painel/produtos/<id>/excluir/
/painel/produtos/imagem/<id>/principal/
/painel/produtos/imagem/<id>/excluir/
/painel/pedidos/
/painel/pedidos/<id>/
/painel/clientes/
/painel/encomendas/
/painel/proxima-viagem/
/painel/configuracoes/
/painel/relatorios/
/painel/categorias/
/painel/api/gtin/
```

Funcionalidades:

- dashboard com metricas;
- listar produtos;
- cadastrar produto;
- editar produto;
- upload de fotos;
- definir imagem principal;
- excluir imagem por POST;
- listar pedidos;
- alterar status;
- confirmar pagamento manualmente;
- inserir rastreio;
- listar clientes;
- listar encomendas;
- editar proxima viagem;
- editar configuracoes;
- relatorios;
- categorias;
- identificacao por produto/codigo.

---

## 17. Django Admin

Arquivo:

```text
products/admin.py
orders/admin.py
payments/admin.py
core/admin.py
```

O admin permite gerenciar:

- categorias;
- marcas;
- produtos;
- variantes;
- imagens;
- pedidos;
- pagamentos;
- configuracoes;
- cotacao.

Produto no admin:

- busca por nome;
- marca;
- descricao;
- GTIN;
- GTIN de variantes.

Variantes tambem possuem admin proprio.

---

## 18. Imagens

Arquivos:

```text
products/image_utils.py
products/models.py
core/management/commands/sync_product_images.py
static/img/defaults/
media/products/
```

Uploads:

- aceitos: JPG, JPEG, PNG, WEBP, HEIC, HEIF;
- limite: 15 MB por foto;
- limite de pixels: 24 megapixels;
- salva JPEG otimizado;
- tamanho maximo armazenado: 1800px;
- preserva orientacao EXIF;
- remove transparencia com fundo branco;
- caminho por produto: `media/products/<slug>/`.

Fallbacks:

- perfumes: `static/img/defaults/default-perfumes.jpg`
- beleza coreana: `static/img/defaults/default-beleza-coreana.jpg`
- eletronicos: `static/img/defaults/default-eletronicos.jpg`
- generico: `static/img/defaults/default-default.jpg`

Imagem demonstrativa:

Comando:

```powershell
.\venv\Scripts\python.exe manage.py sync_product_images
```

O comando:

- gera imagens locais coerentes por produto;
- usa nome, marca e categoria;
- nao apaga fotos antigas;
- marca a imagem gerada como principal;
- atualiza imagens geradas existentes;
- deixa fotos reais antigas no banco;
- fotos reais podem ser substituidas pelo painel.

Estado atual do banco em 2026-07-02:

- produtos: 33
- imagens: 42
- imagens principais demonstrativas: 33
- produtos sem imagem: 0

---

## 19. Identificacao por produto, GTIN, codigo de barras e busca por termo

Arquivos:

```text
products/gtin_service.py
products/gtin_catalog.py
dashboard/views.py
templates/dashboard/product_form.html
products/forms.py
products/models.py
```

Endpoint:

```text
/painel/api/gtin/?code=<valor>
```

Apesar do nome da rota ainda ser `gtin`, a tecnologia agora funciona como identificacao geral:

- codigo de barras;
- GTIN/EAN;
- nome de produto;
- marca;
- termo descritivo.

Exemplos que devem funcionar:

```text
7500435135030
Good Girl
creme
serum
Sauvage
Carolina Herrera
```

Ordem de busca:

1. se for codigo numerico valido, procura produto/variante local por GTIN;
2. procura no catalogo local `products/gtin_catalog.py`;
3. consulta Open Food Facts;
4. consulta Open Beauty Facts;
5. se houver `COSMOS_API_TOKEN`, consulta Cosmos/Bluesoft;
6. se for texto, procura produtos locais por nome, marca, descricao e variantes;
7. se codigo foi lido mas nao existe, retorna rascunho para preencher manualmente.

Codigo conhecido no catalogo local:

```text
7500435135030 -> Antitranspirante Refrescante Old Spice 150ml Spray
```

Referencia publica:

```text
https://cosmos.bluesoft.com.br/produtos/7500435135030-antitranspirante-refrescante-old-spice-150ml-spray
```

Regras de GTIN:

- salva somente digitos;
- aceita 8, 12, 13 ou 14 digitos;
- remove espacos, tracos e caracteres nao numericos;
- produto e variante podem ter GTIN proprio;
- depois que um codigo for salvo em produto/variante, ele e encontrado localmente.

Frontend:

- em `templates/dashboard/product_form.html`;
- campo de busca separado do campo GTIN salvo;
- camera usa `BarcodeDetector` quando o navegador suporta;
- se encontrar produto existente, mostra link para editar;
- se encontrar varios por termo, lista opcoes;
- se encontrar produto novo por catalogo, preenche nome, marca, descricao e GTIN.

Limitacao:

- bases publicas nem sempre possuem perfumes, cremes ou importados;
- para melhor acerto, alimentar catalogo local ou configurar `COSMOS_API_TOKEN`;
- para produtos importados especificos, muitas vezes sera necessario cadastrar manualmente uma vez.

---

## 20. Categorias, marcas e produtos demonstrativos

Comando:

```powershell
.\venv\Scripts\python.exe manage.py seed_demo_products
```

Estado atual:

- categorias: 4
- marcas: 14
- produtos: 33
- variantes: 39

Categorias:

```text
Perfumes
  └── Perfumes Fracionados
Beleza Coreana
Eletronicos
```

Marcas principais:

```text
Carolina Herrera
Paco Rabanne
Dior
Lancome
Yves Saint Laurent
Chanel
Jean Paul Gaultier
Lattafa
Samsung
Apple
Anker
Beauty of Joseon
COSRX
Laneige
```

Perfumes fracionados:

- Good Girl - Fracionado
- 212 VIP Rose - Fracionado
- Lady Million - Fracionado
- Sauvage - Fracionado
- La Vie Est Belle - Fracionado
- Libre - Fracionado
- Scandal - Fracionado

Volumes:

```text
10ml, 20ml, 30ml, 40ml, 50ml, 60ml, 70ml, 80ml
```

Cada variante tem:

- nome;
- volume;
- preco USD;
- promocao opcional;
- custo USD;
- estoque;
- SKU;
- GTIN opcional.

---

## 21. Cotacao dolar/real

Arquivos:

```text
core/models.py
core/services.py
core/context_processors.py
core/templatetags/money.py
core/management/commands/update_exchange_rate.py
products/management/commands/convert_prices_to_usd.py
```

Comandos:

```powershell
.\venv\Scripts\python.exe manage.py update_exchange_rate
.\venv\Scripts\python.exe manage.py update_exchange_rate --rate 5.1763 --source "manual"
.\venv\Scripts\python.exe manage.py convert_prices_to_usd
```

Estado atual:

```text
Cotacao ativa: 5.1763
```

Exibicao:

- cards mostram USD e BRL;
- detalhe mostra USD e BRL;
- carrinho mostra subtotal USD e BRL;
- checkout registra cotacao do momento.

---

## 22. Templates principais

Base:

```text
templates/base.html
```

Home:

```text
templates/home.html
```

Produtos:

```text
templates/products/list.html
templates/products/detail.html
templates/products/_card.html
```

Carrinho:

```text
templates/cart/cart.html
```

Checkout:

```text
templates/checkout/checkout.html
templates/checkout/success.html
templates/checkout/pix.html
templates/checkout/payment_link.html
templates/checkout/whatsapp.html
```

Conta:

```text
templates/accounts/login.html
templates/accounts/register.html
templates/accounts/profile.html
templates/accounts/orders.html
templates/accounts/order_detail.html
templates/accounts/_sidebar.html
```

Dashboard:

```text
templates/dashboard/base_dashboard.html
templates/dashboard/index.html
templates/dashboard/products.html
templates/dashboard/product_form.html
templates/dashboard/orders.html
templates/dashboard/order_detail.html
templates/dashboard/reports.html
templates/dashboard/settings.html
templates/dashboard/categories.html
templates/dashboard/category_form.html
templates/dashboard/customers.html
templates/dashboard/pre_orders.html
templates/dashboard/next_trip.html
```

Paginas institucionais:

```text
templates/pages/about.html
templates/pages/contact.html
templates/pages/next_trip.html
templates/pages/payment_methods.html
templates/pages/pre_order_terms.html
templates/pages/privacy.html
templates/pages/returns.html
templates/pages/shipping_policy.html
```

---

## 23. CSS e identidade visual

Arquivo principal:

```text
static/css/style.css
```

Identidade:

- marca: Essence K Importados;
- estilo clean, delicado e premium;
- foco em K-beauty, perfumes, skincare e importados;
- cores principais:
  - rosa blush `#f8c8dc`
  - marfim `#fff9f4`
  - preto `#111111`

Logos:

```text
static/img/brand/essence-k-logo-horizontal.svg
static/img/brand/essence-k-logo-horizontal-light.svg
static/img/brand/essence-k-logo-short.svg
static/img/brand/essence-k-logo-stacked.svg
static/img/brand/essence-k-mark.svg
static/img/brand/essence-k-favicon.svg
```

Componentes visuais:

- header com logo;
- vitrine em grid;
- cards de produto;
- painel de cotacao;
- filtros sanfona hierarquicos;
- botoes e badges;
- dashboard administrativo.

Cuidados:

- nao mudar visual sem pedido;
- nao transformar o site em landing page;
- manter foco em loja usavel;
- cards devem continuar legiveis em mobile;
- texto nao pode sobrepor botoes ou imagens.

---

## 24. Testes

Testes existentes:

```text
accounts/tests.py
cart/tests.py
orders/tests.py
payments/tests.py
products/tests.py
```

Rodar todos:

```powershell
.\venv\Scripts\python.exe manage.py test
```

Ultimo estado conhecido:

```text
31 tests OK
```

Tambem rodar:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Testes cobrem:

- cadastro e duplicidade de email/CPF/telefone;
- seguranca de redirect;
- upload local de imagem;
- validacao de preco promocional;
- fallback de imagem;
- GTIN e busca por termo;
- carrinho e estoque;
- frete selecionado;
- checkout;
- acesso de pedido por dono/admin;
- baixa de estoque uma unica vez;
- pagamento sandbox.

---

## 25. Comandos de gerenciamento

Core:

```text
python manage.py seed
python manage.py seed_demo_products
python manage.py update_exchange_rate
python manage.py sync_product_images
python manage.py generate_images
python manage.py download_product_images
```

Products:

```text
python manage.py convert_prices_to_usd
```

Recomendados para ambiente de teste:

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed
.\venv\Scripts\python.exe manage.py seed_demo_products
.\venv\Scripts\python.exe manage.py sync_product_images
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Nao rodar comandos destrutivos sem autorizacao:

- nao apagar banco;
- nao resetar migrations;
- nao deletar `media/`;
- nao usar `git reset --hard`;
- nao apagar produtos/pedidos/clientes.

---

## 26. Estado atual do banco local

Em 2026-07-02:

```text
Categorias: 4
Marcas: 14
Produtos: 33
Variantes: 39
Imagens de produto: 42
Imagens principais geradas: 33
Pedidos: 3
Itens de pedido: 3
Usuarios: 3
Pagamentos: 1
Cotacao ativa USD/BRL: 5.1763
```

Categorias:

```text
Perfumes (slug: perfumes)
Perfumes Fracionados (slug: perfumes-fracionados, pai: perfumes)
Beleza Coreana (slug: beleza-coreana)
Eletronicos (slug: eletronicos)
```

Observacao:

- pedidos e usuarios locais podem incluir dados de teste;
- nao apagar sem autorizacao.

---

## 27. Seguranca

Ja implementado:

- `.env` no `.gitignore`;
- `db.sqlite3` no `.gitignore`;
- `media/` no `.gitignore`;
- senhas por hash do Django;
- CSRF ativo;
- dashboard com `staff_member_required`;
- cliente so ve os proprios pedidos;
- dados internos aparecem apenas no admin/dashboard;
- preco de custo, lucro e margem nao aparecem na vitrine;
- upload de imagem validado;
- GTIN/codigo consultado no backend;
- tokens nao expostos no frontend;
- `production.py` exige configuracoes fortes;
- redirects de login/cadastro protegidos contra URL externa.

Cuidados ao alterar:

- nao colocar token no HTML;
- nao salvar numero de cartao;
- nao salvar CVV;
- nao marcar pedido como pago sem confirmacao real ou acao manual consciente;
- nao liberar painel para usuario comum;
- nao desativar CSRF;
- nao deixar `DEBUG=True` em producao;
- nao usar `ALLOWED_HOSTS=['*']` em producao.

---

## 28. Fluxo de publicacao e link temporario

O projeto pode ser visualizado localmente em:

```text
http://127.0.0.1:8000/
```

Para mostrar no celular, foi usado Cloudflare quick tunnel via:

```text
C:\paragua\.preview-tools\cloudflared.exe
```

Esse link e temporario:

- funciona enquanto o PC estiver ligado;
- funciona enquanto o servidor Django estiver rodando;
- funciona enquanto `cloudflared` estiver rodando;
- nao e hospedagem definitiva;
- o dominio muda quando reinicia o tunel.

Para producao real, precisa hospedagem, dominio, banco de dados persistente, media storage e variaveis reais.

---

## 29. Pontos parcialmente implementados ou simulados

### Pagamento real

Preparado, mas depende de credenciais reais.

Falta para producao:

- conta Mercado Pago da administradora;
- `MP_ACCESS_TOKEN`;
- `MP_PUBLIC_KEY`;
- `MP_WEBHOOK_SECRET`;
- `SITE_URL` publico HTTPS;
- webhook configurado no Mercado Pago;
- testes em sandbox oficial;
- homologacao antes de cobrar real.

### Frete real

Hoje e simulado.

Falta:

- escolher provedor;
- configurar token;
- calcular peso/dimensoes reais;
- tratar servicos, prazos e valores reais.

### Catalogo GTIN

Funciona localmente e por bases abertas, mas nem todo produto importado existe nessas bases.

Melhorias futuras:

- configurar `COSMOS_API_TOKEN`;
- alimentar `products/gtin_catalog.py` com produtos frequentes;
- criar tela para cadastrar catalogo local sem editar codigo;
- permitir associar codigo escaneado a produto existente direto pelo painel.

### Imagens reais

Atualmente existem imagens demonstrativas locais coerentes.

Falta para loja real:

- administradora subir fotos reais dos produtos;
- substituir demonstrativas por fotos reais;
- manter imagens demonstrativas apenas como fallback.

---

## 30. Regras importantes para qualquer IA continuar o projeto

1. Leia o codigo antes de alterar.
2. Nao apague produtos, clientes, pedidos, imagens ou banco.
3. Nao resetar banco sem autorizacao.
4. Nao criar credenciais falsas como se fossem reais.
5. Nao expor senha, token, chave de API ou dados bancarios.
6. Manter o nome atual da loja: **Essence K Importados**.
7. Manter foco em funcionamento real, seguranca e facilidade para a administradora.
8. Para imagens, preservar uploads existentes e usar fallback seguro.
9. Para pagamento, manter sandbox funcionando sem credenciais.
10. Para estoque, baixar apenas com pagamento confirmado.
11. Para variantes, preservar `variant_id` no carrinho e pedido.
12. Para GTIN, normalizar codigos e buscar local antes de APIs externas.
13. Para filtros, manter hierarquia categoria -> marca/volume.
14. Sempre rodar testes apos alteracoes importantes.
15. Usar `.env.example` para documentar variaveis, nunca `.env`.

---

## 31. Arquivos que uma IA deve ler primeiro

Ordem recomendada:

```text
README.md
DOCUMENTACAO_COMPLETA_PARA_IA.md
paraguashopping/settings/base.py
paraguashopping/settings/development.py
paraguashopping/settings/production.py
paraguashopping/urls.py
products/models.py
products/views.py
products/forms.py
products/gtin_service.py
dashboard/views.py
templates/dashboard/product_form.html
cart/models.py
cart/views.py
orders/models.py
orders/views.py
orders/services.py
payments/services.py
payments/gateways/mercadopago.py
shipping/utils.py
static/css/style.css
```

---

## 32. Checklist antes de entregar qualquer alteracao

Rodar:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test
```

Testar manualmente quando mexer em produto/carrinho:

```text
Abrir home
Abrir lista de produtos
Abrir produto individual
Escolher variante
Adicionar ao carrinho
Alterar quantidade
Remover item
Fazer checkout teste
Ver pedido em Meus Pedidos
Abrir painel
Cadastrar produto
Subir foto
Buscar por codigo/GTIN/nome
Editar estoque
Confirmar pagamento teste/manual
Ver baixa de estoque
```

Testar manualmente quando mexer em admin/painel:

```text
Usuario comum nao acessa painel
Staff acessa painel
Formulario mostra erros claros
Uploads rejeitam arquivo invalido
Dados internos nao aparecem na vitrine
```

---

## 33. Observacoes finais

Este projeto ja tem uma boa base funcional, mas ainda e um ambiente de desenvolvimento/local.

Para virar loja real em producao, os pontos mais importantes sao:

- hospedagem definitiva;
- dominio;
- banco PostgreSQL;
- storage/media persistente;
- `DEBUG=False`;
- `SECRET_KEY` forte;
- `ALLOWED_HOSTS` correto;
- `CSRF_TRUSTED_ORIGINS` correto;
- gateway de pagamento real da administradora;
- webhook real;
- frete real;
- fotos reais dos produtos;
- politica de privacidade/termos revisados;
- testes finais em mobile.

Nunca tratar o tunel Cloudflare temporario como hospedagem oficial.
