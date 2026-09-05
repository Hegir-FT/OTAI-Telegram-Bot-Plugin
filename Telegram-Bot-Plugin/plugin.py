
import os
import sys
import asyncio
import threading
import logging
from datetime import datetime, timedelta
import sqlite3
from collections import defaultdict
import json
import random
from pathlib import Path
import importlib.util
from typing import Dict, List, Optional


try:
    from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  Библиотека python-telegram-bot не установлена.")
    print("Установите её командой: pip install python-telegram-bot")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

ALLOWED_USERS = []  
MAX_MESSAGE_LENGTH = 4000  


telegram_bot_instance = None
bot_thread = None
user_sessions = {}  
training_queue = asyncio.Queue()  
stats_cache = {}  
stats_cache_time = None



def load_dictionary():
    """Загружает словарь из dictionary.json"""
    
  
    dict_path = Path(__file__).parent / "dictionary.json"
    if dict_path.exists():
        try:
            with open(dict_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка чтения dictionary.json: {e}")
    
    
    templates_dir = Path(__file__).parent.parent / "dictionary_and_templates"
    if templates_dir.exists():
        dict_path = templates_dir / "dictionary.json"
        if dict_path.exists():
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка чтения dictionary.json: {e}")
    
    logger.warning("Словарь не найден, будут использоваться базовые шаблоны")
    return None



def validate_dictionary(dictionary: Optional[Dict]) -> bool:
    """Проверяет, что словарь содержит все необходимые ключи"""
    if not dictionary:
        return False
    
    required_keys = ["nouns", "verbs", "adjectives"]
    for key in required_keys:
        if key not in dictionary:
            logger.warning(f"Отсутствует ключ '{key}' в словаре")
            return False
    
    if not dictionary.get("nouns") or not dictionary.get("verbs"):
        logger.warning("Словарь пуст или неполный")
        return False
    
    return True




def load_templates(filter_group: Optional[str] = None, filter_level: Optional[str] = None) -> List[Dict]:
    """Загружает шаблоны из templates.json"""
    
    
    templates_path = Path(__file__).parent / "templates.json"
    
    
    if not templates_path.exists():
        templates_dir = Path(__file__).parent.parent / "dictionary_and_templates"
        if templates_dir.exists():
            templates_path = templates_dir / "templates.json"
    
    if not templates_path.exists():
        logger.warning("Шаблоны не найдены, используются базовые")
        return [
            {"id": 1, "group": "base", "level": "A1", "template": "Я {verb} {noun}."},
            {"id": 2, "group": "base", "level": "A1", "template": "Мне нравится {adj} {noun}."},
            {"id": 3, "group": "base", "level": "A1", "template": "Сегодня {noun} {verb}."},
            {"id": 4, "group": "base", "level": "A1", "template": "Это очень {adj} {noun}."},
        ]
    
    try:
        with open(templates_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            templates = data.get("templates", [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Ошибка чтения templates.json: {e}")
        return []
    
    if filter_group:
        templates = [t for t in templates if t.get("group") == filter_group]
    if filter_level:
        templates = [t for t in templates if t.get("level") == filter_level]
    
    return templates




def load_response_bank():
    """Загружает response_bank"""
    
    
    local_bank = Path(__file__).parent / "response_bank.py"
    if local_bank.exists():
        try:
            spec = importlib.util.spec_from_file_location("response_bank_local", local_bank)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.ResponseBank()
        except Exception as e:
            logger.error(f"Ошибка загрузки локального response_bank: {e}")
    
    
    templates_dir = Path(__file__).parent.parent / "dictionary_and_templates"
    if templates_dir.exists():
        bank_in_templates = templates_dir / "response_bank.py"
        if bank_in_templates.exists():
            try:
                spec = importlib.util.spec_from_file_location("response_bank_templates", bank_in_templates)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.ResponseBank()
            except Exception as e:
                logger.error(f"Ошибка загрузки response_bank из templates: {e}")
    
  
    root_bank = Path(__file__).parent.parent.parent / "response_bank_korotki.py"
    if root_bank.exists():
        try:
            spec = importlib.util.spec_from_file_location("response_bank_root", root_bank)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.ResponseBank()
        except Exception as e:
            logger.error(f"Ошибка загрузки root response_bank: {e}")
    
    logger.warning("ResponseBank не найден")
    return None




_dictionary = None
_templates = None
_response_bank = None

def _init_data():
    """Инициализирует словарь, шаблоны и response_bank"""
    global _dictionary, _templates, _response_bank
    if _dictionary is None:
        _dictionary = load_dictionary()
    if _templates is None:
        _templates = load_templates()
    if _response_bank is None:
        _response_bank = load_response_bank()


def reload_data():
    """Принудительно перезагружает все данные"""
    global _dictionary, _templates, _response_bank
    _dictionary = load_dictionary()
    _templates = load_templates()
    _response_bank = load_response_bank()
    logger.info("Данные успешно перезагружены")
    return True




def handle_special_questions(user_message: str) -> Optional[str]:
    """Обрабатывает конкретные вопросы пользователя"""
    user_lower = user_message.lower().strip()
    
  
    who_patterns = [
        "кто ты", "ты кто", "кто такой", "расскажи о себе", 
        "представься", "что ты за бот", "твоё имя", "как тебя зовут",
        "кто вы", "вы кто", "что ты такое", "ты человек", "ты бот",
        "ты робот", "ии", "искусственный интеллект", "кто ты такой"
    ]
    if any(pattern in user_lower for pattern in who_patterns):
        responses = [
            "Я OTAI — более улучшенная версия старого ИИ-бота TAIB! 😊",
            "Привет! Я OTAI, улучшенная версия TAIB. Рад познакомиться!",
            "OTAI — это я! Эволюционировавший TAIB с новыми возможностями.",
            "Я OTAI, преемник TAIB. Теперь я умнее и быстрее!",
            "Меня зовут OTAI. Я — новая версия бота TAIB, но с расширенным функционалом."
        ]
        return random.choice(responses)
  
    
    hello_patterns = ["привет", "здравствуй", "здравствуйте", "салют", "хай", "hi", "hello", "ку", "прив"]
    if any(pattern in user_lower for pattern in hello_patterns):
        responses = [
            "Привет! Рад тебя видеть! Я OTAI.",
            "Здравствуй! Как у тебя дела?",
            "Привет-привет! Я OTAI, чем могу помочь?",
            "Салют! Давно не виделись!",
            "Здравствуйте! Рад познакомиться!"
        ]
        return random.choice(responses)
    
  
    how_patterns = ["как дела", "как ты", "как жизнь", "как настроение", "как у тебя"]
    if any(pattern in user_lower for pattern in how_patterns):
        responses = [
            "У меня всё отлично! А у тебя?",
            "Прекрасно! Спасибо, что спросили!",
            "Всё супер! Я полон энергии!",
            "Отлично! А как твои дела?",
            "Замечательно! Чем могу быть полезен?"
        ]
        return random.choice(responses)
    
    
    ability_patterns = ["что умеешь", "что ты можешь", "твои возможности", "что ты делаешь"]
    if any(pattern in user_lower for pattern in ability_patterns):
        responses = [
            "Я умею отвечать на вопросы, вести диалог и генерировать случайные фразы!",
            "Я могу общаться, отвечать на твои вопросы и даже шутить!",
            "Мои возможности: диалог, генерация ответов, обработка запросов.",
            "Я умею поддерживать беседу и помогать с разными вопросами."
        ]
        return random.choice(responses)
    
  
    goodbye_patterns = ["пока", "до свидания", "увидимся", "прощай", "bye", "goodbye", "до встречи"]
    if any(pattern in user_lower for pattern in goodbye_patterns):
        responses = [
            "Пока! Рад был пообщаться!",
            "До свидания! Возвращайся ещё!",
            "Увидимся! Буду ждать тебя снова!",
            "Пока-пока! Не пропадай!"
        ]
        return random.choice(responses)
    
    
    thanks_patterns = ["спасибо", "благодарю", "спс", "спасиб", "thanks"]
    if any(pattern in user_lower for pattern in thanks_patterns):
        responses = [
            "Пожалуйста! Рад был помочь!",
            "Всегда пожалуйста! 😊",
            "Не за что! Обращайся!",
            "Рад помочь!"
        ]
        return random.choice(responses)
    
    
    sorry_patterns = ["извини", "прости", "прошу прощения", "извините"]
    if any(pattern in user_lower for pattern in sorry_patterns):
        responses = [
            "Ничего страшного!",
            "Всё в порядке!",
            "Не переживай!",
            "Без проблем!"
        ]
        return random.choice(responses)
    
    return None


def detect_group(user_message: str) -> str:
    """Определяет группу шаблонов по ключевым словам"""
    user_lower = user_message.lower()
    
    if any(word in user_lower for word in ["почему", "как", "что", "зачем", "неужели", "чей", "чьё"]):
        return "question"
    elif any(word in user_lower for word in ["вчера", "завтра", "скоро", "уже", "только что", "недавно", "позже"]):
        return "time"
    elif any(word in user_lower for word in ["не", "никогда", "без", "невозможно", "нельзя"]):
        return "negative"
    elif any(word in user_lower for word in ["если", "чтобы", "из-за", "несмотря", "когда"]):
        return "conditional"
    elif any(word in user_lower for word in ["лучше", "чем", "предпочитаю", "самое", "самый"]):
        return "comparison"
    elif any(word in user_lower for word in ["попробуй", "рекомендую", "стоит", "не забудь", "давай"]):
        return "imperative"
    elif any(word in user_lower for word in ["говорят", "часто", "многие", "каждый", "иногда", "обычно"]):
        return "abstract"
    elif any(word in user_lower for word in ["нравится", "люблю", "обожаю", "предпочитаю"]):
        return "preference"
    elif any(word in user_lower for word in ["помоги", "срочно", "проблема", "нужна помощь"]):
        return "help"
    else:
        return "base"




def generate_response(user_message: str, db_manager=None) -> str:
    """Основная функция генерации ответа"""
    _init_data()
    
    
    special_response = handle_special_questions(user_message)
    if special_response:
        return special_response
    
    
    if _response_bank:
        resp = _response_bank.get_response(user_message)
        if resp:
            return resp
    
    
    group = detect_group(user_message)
    templates = load_templates(filter_group=group)
    
    
    if not templates:
        templates = load_templates()
    
    
    if _dictionary and templates and validate_dictionary(_dictionary):
        nouns = _dictionary.get("nouns", [])
        verbs = _dictionary.get("verbs", [])
        adjectives = _dictionary.get("adjectives", [])
        adverbs = _dictionary.get("adverbs", [])
        
        if nouns and verbs and adjectives:
            template_obj = random.choice(templates)
            template = template_obj["template"]
            
            result = template
            if "{noun}" in result and nouns:
                result = result.replace("{noun}", random.choice(nouns))
            if "{verb}" in result and verbs:
                result = result.replace("{verb}", random.choice(verbs))
            if "{adj}" in result and adjectives:
                result = result.replace("{adj}", random.choice(adjectives))
            if "{adv}" in result and adverbs:
                result = result.replace("{adv}", random.choice(adverbs))
            
            return result
    
    
    return "Извините, я не понял, но вот вам случайный ответ."

class TrainingTask:
    """Класс для представления задачи обучения"""
    def __init__(self, user_id, user_name):
        self.user_id = user_id
        self.user_name = user_name
        self.start_time = datetime.now()
        self.status = "queued" 
        self.progress = 0
        self.message = None
        self.error = None

class TelegramBotManager:
    """Менеджер для управления Telegram ботом в отдельном потоке"""
    
    def __init__(self, core_bot):
        self.core_bot = core_bot
        self.application = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.training_tasks: Dict[int, TrainingTask] = {}
        self.task_counter = 0
        self.stats_lock = threading.Lock()
        
      
        self.processing_queue = asyncio.Queue()
        self.worker_task = None
        
    def start(self):
        """Запускает Telegram бота в отдельном потоке"""
        if not TELEGRAM_AVAILABLE:
            print("❌ Невозможно запустить Telegram бот: библиотека не установлена")
            return False
            
        if not TOKEN:
            print("❌ Токен Telegram бота не указан")
            return False
            
        if self.is_running:
            print("ℹ️ Telegram бот уже запущен")
            return True
            
        try:
        
            builder = Application.builder()
            builder.token(TOKEN)
            builder.connect_timeout(30.0)
            builder.read_timeout(30.0)
            builder.write_timeout(30.0)
            builder.pool_timeout(30.0)
            self.application = builder.build()
            
            
            self._register_handlers()
            
        
            self.stop_event.clear()
            bot_thread = threading.Thread(
                target=self._run_bot,
                daemon=True,
                name="TelegramBotThread"
            )
            bot_thread.start()
            
            
            import time
            time.sleep(2)
            
            
            self._start_workers()
            
            self.is_running = True
            
            
            try:
                bot_info = self.application.bot.get_me()
                print(f"✅ Telegram бот запущен! @{bot_info.username}")
                print(f"📊 Бот готов к работе с генерацией ответов через plugin.py")
            except:
                print("✅ Telegram бот запущен!")
                
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска Telegram бота: {e}")
            return False
    
    def _start_workers(self):
        """Запускает фоновые воркеры для асинхронной обработки"""
        def run_workers():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._worker_loop())
        
        worker_thread = threading.Thread(target=run_workers, daemon=True)
        worker_thread.start()
    
    async def _worker_loop(self):
        """Основной цикл воркера для обработки задач"""
        while not self.stop_event.is_set():
            try:
                # Обрабатываем задачи обучения
                if not training_queue.empty():
                    await self._process_training_queue()
                
                # Обновляем кэш статистики
                if self._should_update_stats_cache():
                    await self._update_stats_cache()
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Ошибка в воркере: {e}")
                await asyncio.sleep(5)
    
    def _should_update_stats_cache(self):
        """Проверяет, нужно ли обновить кэш статистики"""
        global stats_cache_time
        if stats_cache_time is None:
            return True
        return (datetime.now() - stats_cache_time) > timedelta(minutes=5)
    
    async def _update_stats_cache(self):
        """Обновляет кэш статистики"""
        global stats_cache, stats_cache_time
        try:
            with self.stats_lock:
                stats_cache = self._get_detailed_stats()
                stats_cache_time = datetime.now()
        except Exception as e:
            logger.error(f"Ошибка обновления кэша статистики: {e}")
    
    def _run_bot(self):
        """Запускает основной цикл бота (выполняется в отдельном потоке)"""
        try:
            self.application.run_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
                stop_signals=None,
                timeout=60
            )
        except Exception as e:
            logger.error(f"Ошибка в цикле бота: {e}")
    
    def _register_handlers(self):
        """Регистрирует все обработчики команд и сообщений"""
        app = self.application
        
        
        app.add_handler(CommandHandler("start", self._start_command))
        app.add_handler(CommandHandler("help", self._help_command))
        app.add_handler(CommandHandler("train", self._train_command))
        app.add_handler(CommandHandler("stats", self._stats_command))
        app.add_handler(CommandHandler("clear", self._clear_command))
        app.add_handler(CommandHandler("status", self._status_command))
        app.add_handler(CommandHandler("export", self._export_command))
        app.add_handler(CommandHandler("cancel", self._cancel_command))
        
  
        app.add_handler(CallbackQueryHandler(self._callback_handler)
