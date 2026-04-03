# World — контекст для Claude Code

## Текущий фокус
- **Статус:** active — основной сайт msolo.me, деплоится через Vercel
- **Сейчас:** /news секция (daily news updates), тёмная тема, медиа карточки
- **Дальше:** neurogate лендинг updates, news автогенерация из OneStep pipeline
- **Обновлено:** 2026-03-31

## Что это
Статический сайт msolo.me. HTML/CSS/JS, без фреймворка.

## Деплой
- GitHub repo: mkultraaaa/world
- git push → Vercel → msolo.me
- Каждая подпапка = отдельная страница (msolo.me/neurogate/, msolo.me/mu/ и т.д.)

## Правила
- Не удалять и не менять структуру подпапок без подтверждения
- `<base href>` обязателен для Vercel в подпапках — не убирать
- mu/index.html — зашифрован AES-256-GCM, генерируется скриптом, не редактировать вручную
