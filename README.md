
![OTAIBot - OTAI Telegram Bot Plugin](OTAIBot.png)

##  О проекте

**OTAIB** - плагин для [Open Tess AI (OTAI)](https://github.com/Tessachok12/Open-Tess-AI), добавляющий поддержку Telegram Bot API. Позволяет общаться с OTAI через Telegram, используя словарь, шаблоны и response bank.

---

##  Возможности

-  **Общение в Telegram** - асинхронная обработка
-  **Умная генерация** - словарь, шаблоны, response bank
-  **Статистика** - метрики использования
-  **Асинхронное обучение** - без блокировки бота
-  **Экспорт диалогов** - в JSON
-  **Интерактивные кнопки** - удобный интерфейс

---

##  Установка

```bash
pip install python-telegram-bot
export TELEGRAM_BOT_TOKEN="ваш_токен"
```

### Структура файлов

```
Open Tess AI/
├── plugins/
│   ├── telegram_bot/
│   │   └── plugin.py          # OTAI Bot Plugin 
│   └── dictionary_and_templates/(ВАЖНО ИМЕТЬ ДЛЯ РАБОТЫ ПЛАГИНА)
│       ├── dictionary.json    # Словарь который использует OTAIB
│       ├── templates.json     # Шаблоны который использует OTAIB
│       └── response_bank.py   # Response bank который использует 
├── core.py                    # Сам OTAI
├── config.py
├── model.py
├── plugin_loader.py
├── trainer.py
└── utils.py
```

---

##  Использование

```python
from plugins.telegram_bot.plugin import init_telegram_bot

# Запуск бота
bot = init_telegram_bot(core_bot)
```

---

##  Команды

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/help` | Справка |
| `/train` | Обучение |
| `/stats` | Статистика |
| `/status` | Состояние задач |
| `/export` | Экспорт |
| `/clear` | Очистка истории |
| `/cancel` | Отмена задачи |

---

##  Конфигурация

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота | Пусто |
| `ALLOWED_USERS` | Разрешённые ID | Все |

---

##  Пример

```
Пользователь: Привет!
OTAIB: Привет! Рад тебя видеть! Я OTAI. 😊

Пользователь: Кто ты?
OTAIB: Я OTAI — более улучшенная версия!

Пользователь: Расскажи что-нибудь
OTAIB: Сегодня машина работает. (из словаря и шаблонов)
```

---

##  Лицензия

MIT License

---
