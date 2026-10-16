#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WEB_DIR=/www/routercare
CGI_DIR=/www/cgi-bin
CGI_FILE=$CGI_DIR/routercare-status
MIHOMO_CGI_FILE=$CGI_DIR/routercare-mihomo-check
BACKUP_ROOT=/root/routercare-backup
STAMP=$(date +%Y%m%d-%H%M%S)

fail() { printf 'Ошибка: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" = 0 ] || fail 'запустите установщик от root через SSH.'
[ -f "$ROOT_DIR/www/routercare/index.html" ] || fail 'не найдена страница www/routercare/index.html.'
[ -f "$ROOT_DIR/www/cgi-bin/routercare-status" ] || fail 'не найден CGI www/cgi-bin/routercare-status.'
[ -f "$ROOT_DIR/www/cgi-bin/routercare-mihomo-check" ] || fail 'не найден CGI www/cgi-bin/routercare-mihomo-check.'
[ -d /www ] || fail 'каталог /www не найден; конфигурация веб-сервера не изменялась.'
[ -d "$CGI_DIR" ] || fail 'каталог /www/cgi-bin не найден; установщик не будет менять uhttpd.'

mkdir -p "$BACKUP_ROOT/$STAMP"
if [ -e "$WEB_DIR" ]; then
    cp -R "$WEB_DIR" "$BACKUP_ROOT/$STAMP/routercare-web.previous"
fi
if [ -e "$CGI_FILE" ]; then
    cp -p "$CGI_FILE" "$BACKUP_ROOT/$STAMP/routercare-status.previous"
fi
if [ -e "$MIHOMO_CGI_FILE" ]; then
    cp -p "$MIHOMO_CGI_FILE" "$BACKUP_ROOT/$STAMP/routercare-mihomo-check.previous"
fi

mkdir -p "$WEB_DIR"
cp "$ROOT_DIR/www/routercare/index.html" "$WEB_DIR/index.html"
cp "$ROOT_DIR/www/cgi-bin/routercare-status" "$CGI_FILE"
cp "$ROOT_DIR/www/cgi-bin/routercare-mihomo-check" "$MIHOMO_CGI_FILE"
chmod 0644 "$WEB_DIR/index.html"
chmod 0755 "$CGI_FILE"
chmod 0755 "$MIHOMO_CGI_FILE"

printf 'RouterCare 0.4.4 установлена.\n'
printf 'Страница: http://<адрес-роутера>/routercare/\n'
printf 'Резервная копия заменённых файлов: %s\n' "$BACKUP_ROOT/$STAMP"
printf 'Меню, firewall, DNS и службы не менялись.\n'
