# RouterCare for OpenWrt

Лёгкая русскоязычная панель диагностики OpenWrt для Xiaomi AX3000T. RouterCare использует готовые upstream-компоненты Zapret и Mihomo. Текущий режим — чтение состояния служб и безопасная проверка конфигурации Mihomo; сетевые правила автоматически не меняются.

## Состав проекта

- [Инструкция по установке](routercare-openwrt/README.md)
- [Изменения](routercare-openwrt/CHANGELOG.md)
- [Источники и этапы интеграции](routercare-openwrt/SOURCES.md)
- Панель: `routercare-openwrt/www/routercare/index.html`
- Установщик: `routercare-openwrt/install.sh`

Интерфейс не подключает сторонние CDN, аналитику или телеметрию. Не добавляйте в репозиторий URL подписок, VPN-ключи, пароли или токены.
