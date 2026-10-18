# FRAME

Закрытая панель Telegram-публикаций: Next.js, React, MongoDB.

```sh
npm install
npm run dev
npm run build
vercel deploy --prod --yes
```

Переменные в .env.local и production Environment Variables Vercel:
MONGODB_URI, MONGODB_DATABASE, DASHBOARD_PASSWORD, DASHBOARD_SECRET.
Секреты не передаются клиенту. API проверяет подписанную HttpOnly-сессию.
Вход ограничен по числу попыток; изменение сессии требует того же Origin.

Используется существующая manhwa_telegram. Панель не запускает воркер на Vercel.
Исторические просмотры и счётчик комментариев недоступны через Bot API.
Тёмная тема основная, выбор светлой сохраняется в браузере.
