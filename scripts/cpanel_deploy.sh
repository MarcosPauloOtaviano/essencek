#!/usr/bin/env bash
set -Eeuo pipefail

REPO_PATH="$(pwd)"
APP_PATH="${CPANEL_APP_PATH:-$HOME/essencek_app}"
PUBLIC_PATH="${CPANEL_PUBLIC_PATH:-$HOME/public_html}"
STATIC_PUBLIC_PATH="$PUBLIC_PATH/static"
MEDIA_PUBLIC_PATH="$PUBLIC_PATH/media"

echo "==> Deploy Essence K Importados"
echo "Repo:   $REPO_PATH"
echo "App:    $APP_PATH"
echo "Public: $PUBLIC_PATH"

mkdir -p "$APP_PATH" "$STATIC_PUBLIC_PATH" "$MEDIA_PUBLIC_PATH" "$APP_PATH/tmp" "$APP_PATH/logs" "$APP_PATH/public"

SYNC_EXCLUDES=(
  --exclude='.git/'
  --exclude='.deploy_keys/'
  --exclude='.env'
  --exclude='venv/'
  --exclude='env/'
  --exclude='.venv/'
  --exclude='db.sqlite3'
  --exclude='db.sqlite3-journal'
  --exclude='media/'
  --exclude='staticfiles/'
  --exclude='*.log'
)

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "${SYNC_EXCLUDES[@]}" "$REPO_PATH/" "$APP_PATH/"
else
  echo "rsync nao encontrado; usando cp sem limpeza automatica de arquivos antigos."
  find "$REPO_PATH" -mindepth 1 -maxdepth 1 \
    ! -name '.git' \
    ! -name '.deploy_keys' \
    ! -name '.env' \
    ! -name 'venv' \
    ! -name 'env' \
    ! -name '.venv' \
    ! -name 'db.sqlite3' \
    ! -name 'db.sqlite3-journal' \
    ! -name 'media' \
    ! -name 'staticfiles' \
    ! -name '*.log' \
    -exec cp -R {} "$APP_PATH"/ \;
fi

mkdir -p "$APP_PATH/tmp" "$APP_PATH/logs" "$APP_PATH/public"

if [ ! -f "$APP_PATH/.env" ]; then
  echo "AVISO: $APP_PATH/.env nao existe."
  echo "Arquivos copiados. Crie o .env de producao no cPanel e rode Deploy HEAD Commit novamente."
  exit 0
fi

find_python() {
  if [ -n "${CPANEL_PYTHON:-}" ] && [ -x "$CPANEL_PYTHON" ]; then
    echo "$CPANEL_PYTHON"
    return 0
  fi

  for candidate in "$HOME"/virtualenv/essencek_app/*/bin/python "$HOME"/virtualenv/essencek/*/bin/python "$APP_PATH"/venv/bin/python; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERRO: Python nao encontrado. Configure CPANEL_PYTHON ou crie o app em Setup Python App."
  exit 1
fi
echo "Python: $PYTHON_BIN"

cd "$APP_PATH"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-paraguashopping.settings.production}"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" manage.py migrate --noinput
"$PYTHON_BIN" manage.py collectstatic --noinput

if [ -d "$APP_PATH/staticfiles" ]; then
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$APP_PATH/staticfiles/" "$STATIC_PUBLIC_PATH/"
  else
    rm -rf "$STATIC_PUBLIC_PATH"/*
    cp -R "$APP_PATH/staticfiles"/. "$STATIC_PUBLIC_PATH"/
  fi
fi

touch "$APP_PATH/tmp/restart.txt"
echo "Deploy finalizado."
