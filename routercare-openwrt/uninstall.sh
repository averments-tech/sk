#!/bin/sh
set -eu

[ "$(id -u)" = 0 ] || { printf 'Запустите от root.\n' >&2; exit 1; }
rm -f /www/cgi-bin/routercare-status
rm -f /www/cgi-bin/routercare-mihomo-check
rm -f /www/routercare/index.html
rm -f /www/routercare/strategy-candidates.json
rmdir /www/routercare 2>/dev/null || true
printf 'Файлы OpenWrt Zapret удалены. Резервные копии в /root/routercare-backup/ сохранены.\n'
