# Deploy na HostGator com cPanel — essencekimportados.com

## Pre-requisitos

- Plano HostGator com cPanel e acesso SSH
- Dominio `essencekimportados.com` apontado para a HostGator
- Python 3.11+ disponivel no cPanel (Setup Python App)

## 1. Acessar o cPanel

Acesse `https://essencekimportados.com/cpanel` ou o link direto fornecido pela HostGator.

## 2. Criar banco MySQL

1. Abra **MySQL Databases** no cPanel
2. Crie um banco: `mar04335_essencek`
3. Crie um usuario MySQL: `mar04335_essencek` com senha forte
4. Associe o usuario ao banco com **ALL PRIVILEGES**
5. Anote: banco, usuario e senha

## 3. Criar Python App

1. No cPanel, abra **Setup Python App**
2. Clique em **Create Application**
3. Preencha:
   - Python version: **3.11** (ou a mais recente disponivel)
   - Application root: `essencek_app`
   - Application URL: dominio principal (sem subpasta)
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
4. Clique em **Create**
5. Anote o comando para ativar o virtualenv (ex: `source /home/usuario/virtualenv/essencek_app/3.11/bin/activate`)

## 4. Conectar repositorio Git

1. No cPanel, abra **Git Version Control**
2. Clique **Create**
3. Preencha:
   - Clone URL: `https://github.com/MarcosPauloOtaviano/essencek.git`
   - Repository Path: `repositories/essencek`
   - Repository Name: `essencek`
4. Apos clonar, clique em **Manage** > **Pull or Deploy** > **Deploy HEAD Commit**

**Na primeira execucao** o script apenas copiara os arquivos e pedira para criar o `.env`.

## 5. Criar .env de producao

Acesse via SSH:

```bash
ssh mar04335@essencekimportados.com
```

Crie o arquivo `.env`:

```bash
cd ~/essencek_app
nano .env
```

Cole o conteudo abaixo (substituindo os valores):

```env
DJANGO_SETTINGS_MODULE=paraguashopping.settings.production
SECRET_KEY=GERE-UMA-CHAVE-FORTE-COM-50-CARACTERES-OU-MAIS
DEBUG=False
ALLOWED_HOSTS=essencekimportados.com,www.essencekimportados.com
CSRF_TRUSTED_ORIGINS=https://essencekimportados.com,https://www.essencekimportados.com
SITE_URL=https://essencekimportados.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=mar04335_essencek
DB_USER=mar04335_essencek
DB_PASSWORD=senha-forte-do-banco
DB_HOST=localhost
DB_PORT=3306

FERNET_KEY=GERE-COM-COMANDO-ABAIXO

STATIC_ROOT=/home1/mar04335/essencek_app/staticfiles
MEDIA_ROOT=/home1/mar04335/public_html/media

PAYMENT_GATEWAY=mercadopago
PAYMENT_SANDBOX=False
MP_ACCESS_TOKEN=seu-access-token-producao
MP_PUBLIC_KEY=sua-public-key-producao
MP_WEBHOOK_SECRET=seu-webhook-secret
MP_USE_SANDBOX_LINK=False
MP_MAX_INSTALLMENTS=12

COSMOS_API_TOKEN=
FRENET_TOKEN=
FRENET_SENDER_CEP=85851130
```

Gere a SECRET_KEY:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Gere a FERNET_KEY:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 6. Rodar deploy novamente

Volte ao cPanel > **Git Version Control** > **Manage** > **Deploy HEAD Commit**

O script `cpanel_deploy.sh` vai:
- Copiar arquivos para `~/essencek_app`
- Instalar dependencias
- Rodar `migrate`
- Rodar `collectstatic`
- Copiar estaticos para `~/public_html/static`
- Reiniciar o app

## 7. Criar superusuario

Via SSH:

```bash
cd ~/essencek_app
source ~/virtualenv/essencek_app/3.11/bin/activate
export DJANGO_SETTINGS_MODULE=paraguashopping.settings.production
python manage.py createsuperuser
```

## 8. Configurar SSL/HTTPS

No cPanel:
1. Abra **SSL/TLS Status**
2. Selecione `essencekimportados.com` e `www.essencekimportados.com`
3. Clique em **Run AutoSSL** (Let's Encrypt gratuito)

## 9. Configurar dominio

Se o dominio ainda nao aponta para a HostGator:
1. No registro do dominio, aponte os nameservers para os da HostGator
2. Ou configure os registros DNS:
   - `A` apontando para o IP do servidor HostGator
   - `CNAME` de `www` para `essencekimportados.com`

## 10. Verificar

Acesse `https://essencekimportados.com` — o site deve carregar.

Se der erro 500, verifique os logs:

```bash
cat ~/essencek_app/logs/error.log
cat ~/logs/essencekimportados.com/error.log
```

## Atualizacoes futuras

1. Faca `git push` para o GitHub
2. No cPanel > Git Version Control > Pull or Deploy > **Update from Remote** > **Deploy HEAD Commit**

Ou via SSH:

```bash
cd ~/repositories/essencek
git pull origin main
bash scripts/cpanel_deploy.sh
```

## Estrutura no servidor

```
~/
  repositories/essencek/    # clone do Git (cPanel gerencia)
  essencek_app/             # app Django (copia de trabalho)
    .env                    # variaveis de producao
    passenger_wsgi.py       # entry point Passenger
    manage.py
    paraguashopping/
    ...
    staticfiles/            # collectstatic output
    tmp/restart.txt         # restart Passenger
    logs/
  public_html/
    static/                 # arquivos estaticos publicos
    media/                  # uploads de imagens
  virtualenv/essencek_app/  # virtualenv criado pelo cPanel
```
