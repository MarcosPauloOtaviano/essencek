# Deploy na HostGator com cPanel + GitHub

Este projeto esta preparado para deploy via cPanel Git Version Control.

## Caminhos usados

- Repositorio clonado pelo cPanel: escolha `~/repositories/essencek`
- Aplicacao Python/Django: `~/essencek_app`
- Arquivos publicos: `~/public_html`
- Static files: `~/public_html/static`
- Uploads/media: `~/public_html/media`

## cPanel Python App

Use estes valores na tela **Setup Python App**:

- Python: 3.11, se disponivel
- Application root: `essencek_app`
- Application URL: dominio principal, sem subpasta
- Startup file: `passenger_wsgi.py`
- Entry point: `application`

Depois de criar o app, crie um arquivo `.env` dentro de `~/essencek_app`.

## Variaveis essenciais no .env de producao

```env
DJANGO_SETTINGS_MODULE=paraguashopping.settings.production
SECRET_KEY=troque-por-uma-chave-forte-com-50-ou-mais-caracteres
DEBUG=False
ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br
CSRF_TRUSTED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br
SITE_URL=https://seudominio.com.br

DB_ENGINE=django.db.backends.mysql
DB_NAME=usuario_cpanel_essencek
DB_USER=usuario_cpanel_essencek
DB_PASSWORD=senha-forte-do-banco
DB_HOST=localhost
DB_PORT=3306

FERNET_KEY=gere-com-python-cryptography-fernet

STATIC_ROOT=/home/usuario_cpanel/essencek_app/staticfiles
MEDIA_ROOT=/home/usuario_cpanel/public_html/media

PAYMENT_GATEWAY=sandbox
PAYMENT_SANDBOX=True
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
MP_WEBHOOK_SECRET=
MP_USE_SANDBOX_LINK=True
MP_MAX_INSTALLMENTS=12
```

Gere a `FERNET_KEY` com:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Deploy

O arquivo `.cpanel.yml` chama `scripts/cpanel_deploy.sh`.

O script:

- copia o repositorio para `~/essencek_app`;
- preserva `.env`, `media/`, banco local e arquivos sensiveis;
- instala `requirements.txt`;
- roda `migrate`;
- roda `collectstatic`;
- copia os estaticos gerados para `~/public_html/static`;
- cria `~/public_html/media`;
- reinicia o app via `tmp/restart.txt`.

Se o `.env` ainda nao existir, o script apenas copia os arquivos e pede para criar o `.env`; depois rode **Deploy HEAD Commit** novamente.
