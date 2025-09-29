import asyncio
import logging
import hashlib
import json
import os
import sys
import re
import random
import requests
import time
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import feedparser
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot
from telegram.error import TelegramError
from fake_useragent import UserAgent
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import io
import banned_organizations

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Конфигурация - теперь только один блок
if 'RAILWAY_ENVIRONMENT' in os.environ or 'RAILWAY_STATIC_URL' in os.environ:
    # Используем переменные окружения Railway
    TOKEN = os.environ.get('TELEGRAM_TOKEN', "7445394461:AAGHiGYBiCwEg-tbchU9lOJmywv4CjcKuls")
    CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL', "@techno_met")
else:
    # Локальные настройки
    TOKEN = "7445394461:AAGHiGYBiCwEg-tbchU9lOJmywv4CjcKuls"
    CHANNEL_ID = "@techno_met"

IXBT_RSS_URL = "https://www.ixbt.com/export/news.rss"
CHECK_INTERVAL = 1800  # 30 минут

# Убедитесь что пути к файлам работают в облаке
def ensure_directories():
    """Создание необходимых директорий"""
    directories = ['images', 'downloaded_images']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Вызов в начале
ensure_directories()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключаем логирование httpx
logging.getLogger('httpx').setLevel(logging.WARNING)

class SmartNewsBot:
    def __init__(self):
        self.processed_news = set()
        self.load_processed_news()
        self.bot = Bot(token=TOKEN)
        self.ua = UserAgent()
        self.session = self.create_advanced_session()
        
    def create_advanced_session(self):
        """Создание продвинутой сессии с обходом защиты"""
        session = requests.Session()
        
        # Настраиваем retry стратегию
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def check_banned_organizations(self, title, text):
        """Проверка новости на упоминание запрещенных организаций"""
        content = f"{title} {text}".lower()
        
        found_organizations = []
        
        # Проверяем полные названия организаций
        for org in banned_organizations.BANNED_ORGANIZATIONS:
            if org.lower() in content:
                found_organizations.append(org)
        
        # Проверяем по ключевым словам
        for keyword in banned_organizations.BANNED_KEYWORDS:
            if keyword in content:
                # Ищем контекст ключевого слова
                start = max(0, content.find(keyword) - 50)
                end = min(len(content), content.find(keyword) + len(keyword) + 50)
                context = content[start:end]
                
                # Извлекаем возможное название организации из контекста
                words = context.split()
                if len(words) > 2:
                    potential_org = ' '.join(words[:min(5, len(words))])
                    found_organizations.append(f"контекст: {potential_org}...")
        
        return found_organizations


    def load_processed_news(self):
        """Загрузка обработанных новостей из файла"""
        try:
            if os.path.exists('processed_news.json'):
                with open('processed_news.json', 'r') as f:
                    data = json.load(f)
                    self.processed_news = set(data)
        except Exception as e:
            logger.error(f"Error loading processed news: {e}")
            self.processed_news = set()

    def save_processed_news(self):
        """Сохранение обработанных новостей в файл"""
        try:
            with open('processed_news.json', 'w') as f:
                json.dump(list(self.processed_news), f)
        except Exception as e:
            logger.error(f"Error saving processed news: {e}")

    def get_news_hash(self, title, link):
        """Создание хэша для идентификации новости"""
        return hashlib.md5(f"{title}{link}".encode()).hexdigest()

    def detect_news_category(self, title, text):
        """Улучшенное определение категории новости для подбора хештегов"""
        title_lower = title.lower()
        text_lower = text.lower()
        
        # Объединяем текст для анализа
        full_text = f"{title_lower} {text_lower}"
        
        # Уточненные ключевые слова для категорий с весами и приоритетами
        categories = {
            'ai': {
                'keywords': [
                    'искусственный интеллект', 'нейросеть', 'нейросети', 'машинное обучение', 
                    'ai', 'chatgpt', 'gpt', 'openai', 'deepmind', 'ml ', ' dl ', 'computer vision',
                    'обработка естественного языка', 'генеративный ai', 'stable diffusion', 
                    'midjourney', 'llm', 'large language model', 'трансформер', 'transformer',
                    'ai agent', 'deep learning', 'обучение с подкреплением', 'training', 'inference',
                    'ai ethics', 'этика ии', 'сингулярность', 'superintelligence', 'ai safety',
                    'data science', 'data mining', 'big data', 'компьютерное зрение',
                    'распознавание образов', 'ai chip', 'tensorflow', 'pytorch', 'hugging face',
                    'chatbot', 'ai assistant', 'голосовой помощник', 'recommendation system',
                    'autonomous', 'ai generated', 'synthetic data', 'synthetic media', 'deepfake'
                ],
                'exclude': ['игра', 'игровой', 'gaming'],  # Исключения чтобы не путать с играми
                'weight': 0,
                'priority': 1
            },
            'space': {
                'keywords': [
                    'космос', 'spacex', 'nasa', 'марс', 'луна', 'спутник', 'орбита', 'ракета',
                    'starlink', 'roscosmos', 'esa', 'космонавт', 'астронавт', 'телескоп',
                    'james webb', 'hubble', 'международная космическая станция', 'мкс', 'iss',
                    'запуск', 'старт', 'посадка', 'starship', 'falcon', 'dragon', 'союз',
                    'внеземная жизнь', 'инопланетяне', 'alien', 'экзопланета', 'exoplanet',
                    'черная дыра', 'black hole', 'neutron star', 'нейтронная звезда',
                    'галактика', 'galaxy', 'млечный путь', 'solar system', 'солнечная система',
                    'астероид', 'комета', 'космический мусор', 'space debris', 'orbital',
                    'космодром', 'baikonur', 'artemis', 'apollo', 'космический туризм'
                ],
                'weight': 0,
                'priority': 1
            },
            'gadgets': {
                'keywords': [
                    'смартфон', 'телефон', 'iphone', 'android', 'планшет', 'ноутбук', 'гаджет',
                    'устройство', 'apple', 'samsung', 'xiaomi', 'huawei', 'google pixel',
                    'oneplus', 'oppo', 'vivo', 'realme', 'умные часы', 'smartwatch', 
                    'apple watch', 'samsung galaxy watch', 'фитнес-браслет', 'fitness tracker',
                    'xiaomi mi band', 'наушники', 'airpods', 'galaxy buds', 'wireless earbuds',
                    'bluetooth наушники', 'колонка', 'smart speaker', 'amazon echo', 
                    'google home', 'apple homepod', 'умный дом', 'smart home', 'iot',
                    'электронная книга', 'e-book', 'kindle', 'pocketbook', 'onyx boox',
                    'ipad', 'surface', 'macbook', 'dell', 'lenovo', 'hp', 'asus',
                    'трансформер', '2-в-1', 'гибрид', 'foldable', 'складывающийся'
                ],
                'weight': 0,
                'priority': 2
            },
            'tv': {
                'keywords': [
                    'телевизор', 'тв', 'oled', 'qled', '4k', '8k', 'экран', 'дисплей',
                    'ultra hd', 'full hd', 'hd', 'разрешение', 'hdr', 'dolby vision',
                    'hdr10', 'hdr10+', 'hlg', 'smart tv', 'android tv', 'webos', 'tizen',
                    'roku tv', 'частота обновления', 'refresh rate', '60hz', '120hz',
                    '240hz', 'подсветка', 'local dimming', 'изогнутый экран', 'curved',
                    'толщина', 'thin', 'безрамочный', 'bezelless', 'цветопередача',
                    'color gamut', 'dci-p3', 'rec.2020', 'яркость', 'nit', 'контрастность',
                    'панель', 'va', 'ips', 'quantum dot', 'квантовые точки', 'laser tv',
                    'проектор', 'home theater', 'домашний кинотеатр', 'звук', 'audio',
                    'dolby atmos', 'dts', 'soundbar', 'саундбар', 'lg', 'samsung', 'sony'
                ],
                'weight': 0,
                'priority': 2
            },
            'auto': {
                'keywords': [
                    'авто', 'машина', 'автомобиль', 'tesla', 'электромобиль', 'toyota',
                    'hyundai', 'марка', 'модель', 'bmw', 'mercedes', 'audi', 'volkswagen',
                    'ford', 'chevrolet', 'nissan', 'honda', 'kia', 'volvo', 'renault',
                    'peugeot', 'двигатель', 'engine', 'бензиновый', 'дизельный', 'гибрид',
                    'hybrid', 'plug-in hybrid', 'phev', 'трансмиссия', 'коробка передач',
                    'автоматическая', 'механическая', 'робот', 'вариатор', 'dsg', 'привод',
                    'передний', 'задний', 'полный', 'awd', '4wd', 'интерьер', 'салон',
                    'мультимедия', 'infotainment', 'apple carplay', 'android auto',
                    'круиз-контроль', 'адаптивный круиз-контроль', 'автопилот', 'autopilot',
                    'водительские ассистенты', 'lane keeping', 'автономное вождение',
                    'self-driving', 'беспилотник', 'безопасность', 'ncap', 'подушка безопасности',
                    'abs', 'esp', 'парковка', 'камера заднего вида', 'датчики парковки'
                ],
                'weight': 0,
                'priority': 2
            },
            'games': {
                'keywords': [
                    'игра', 'игровой', 'gaming', 'playstation', 'xbox', 'nintendo', 'steam',
                    'консоль', 'pc', 'пк', 'видеоигра', 'ps5', 'ps4', 'xbox series x',
                    'xbox series s', 'nintendo switch', 'playstation plus', 'xbox game pass',
                    'game pass ultimate', 'ea play', 'ubisoft connect', 'epic games store',
                    'gog', 'release', 'релиз', 'анонс', 'трейлер', 'gameplay', 'геймплей',
                    'сюжет', 'story', 'графика', 'graphics', 'fps', 'rpg', 'mmo', 'mmorpg',
                    'шутер', 'стратегия', 'экшен', 'приключение', 'инди', 'киберспорт',
                    'esports', 'twitch', 'youtube gaming', 'стрим', 'stream', 'dlc',
                    'дополнение', 'addon', 'expansion', 'патч', 'update', 'обновление',
                    'pre-order', 'предзаказ', 'рейтинг', 'metacritic', 'openworld',
                    'открытый мир', 'multiplayer', 'мультиплеер', 'co-op', 'кооператив',
                    'pvp', 'pve', 'vr игры', 'ar игры', 'mobile game', 'мобильная игра',
                    'gacha', 'roblox', 'minecraft', 'fortnite', 'call of duty', 'warzone'
                ],
                'weight': 0,
                'priority': 2
            },
            'science': {
                'keywords': [
                    'наука', 'исследование', 'ученые', 'открытие', 'эксперимент', 'лаборатория',
                    'scientific', 'discovery', 'study', 'research', 'физика', 'physics',
                    'квантовая физика', 'quantum', 'теория относительности', 'astrophysics',
                    'астрофизика', 'космология', 'химия', 'chemistry', 'биология', 'biology',
                    'генетика', 'genetics', 'dna', 'рнк', 'rna', 'геном', 'genome', 'crispr',
                    'медицина', 'medicine', 'вирус', 'vaccine', 'вакцина', 'иммунитет',
                    'immunity', 'антитело', 'antibody', 'клиническое испытание', 'археология',
                    'archaeology', 'антропология', 'anthropology', 'психология', 'psychology',
                    'нейробиология', 'neuroscience', 'мозг', 'математика', 'mathematics',
                    'теорема', 'гипотеза', 'алгоритм', 'материаловедение', 'nanotechnology',
                    'нанотехнологии', 'робототехника', 'robotics', 'бионика', 'биоинженерия',
                    'экология', 'ecology', 'climate change', 'изменение климата'
                ],
                'weight': 0,
                'priority': 1
            },
            'internet': {
                'keywords': [
                    'интернет', 'браузер', 'соцсеть', 'социальная сеть', 'facebook', 'instagram',
                    'tiktok', 'twitter', 'x ', 'youtube', 'linkedin', 'vk', 'telegram',
                    'whatsapp', 'wechat', 'signal', 'discord', 'reddit', 'pinterest', 'snapchat',
                    'провайдер', 'isp', 'скорость интернета', 'broadband', 'оптоволокно',
                    'fiber', '5g', 'wi-fi', 'wi-fi 6', 'wi-fi 7', 'роутер', 'маршрутизатор',
                    'mesh-система', 'трафик', 'data', 'vpn', 'proxy', 'tor', 'анонимность',
                    'privacy', 'конфиденциальность', 'cookies', 'tracking', 'блокировка сайтов',
                    'net neutrality', 'интернет вещей', 'iot', 'умный дом', 'смарт-город',
                    'web 3.0', 'метавселенная', 'metaverse', 'seo', 'sem', 'контекстная реклама',
                    'сайт', 'веб-разработка', 'хостинг', 'домен'
                ],
                'weight': 0,
                'priority': 2
            },
            'software': {
                'keywords': [
                    'программа', 'софт', 'приложение', 'обновление', 'windows', 'linux', 'macos',
                    'ios', 'android', 'api', 'интерфейс', 'ui', 'ux', 'разработка', 'development',
                    'программирование', 'coding', 'agile', 'scrum', 'devops', 'github', 'gitlab',
                    'bitbucket', 'ide', 'visual studio', 'vs code', 'jetbrains', 'intellij',
                    'pycharm', 'компилятор', 'интерпретатор', 'скрипт', 'script', 'open source',
                    'исходный код', 'source code', 'лицензия', 'license', 'gpl', 'mit', 'freeware',
                    'shareware', 'proprietary', 'баг', 'ошибка', 'debugging', 'отладка',
                    'тестирование', 'qa', 'quality assurance', 'unit test', 'патч', 'hotfix',
                    'релиз', 'версия', 'version', 'changelog', 'документация', 'readme'
                ],
                'weight': 0,
                'priority': 2
            },
            'hardware': {
                'keywords': [
                    'процессор', 'видеокарта', 'оперативная память', 'ssd', 'жесткий диск',
                    'материнская плата', 'cpu', 'gpu', 'ram', 'hdd', 'intel', 'amd', 'nvidia',
                    'qualcomm', 'apple silicon', 'm1', 'm2', 'ryzen', 'core i3', 'core i5',
                    'core i7', 'core i9', 'radeon', 'geforce', 'rtx', 'gtx', 'dlss', 'ray tracing',
                    'трассировка лучей', 'тактовя частота', 'clock speed', 'разгон', 'overclocking',
                    'охлаждение', 'cooling', 'кулер', 'радиатор', 'термопаста', 'водяное охлаждение',
                    'aio', 'liquid cooling', 'thermal throttling', 'блок питания', 'psu', 'мощность',
                    'efficiency', '80 plus', 'bronze', 'gold', 'platinum', 'корпус', 'case',
                    'atx', 'mini-itx', 'micro-atx', 'форм-фактор', 'сборка пк', 'pc build',
                    'конфигуратор', 'upgrade', 'апгрейд', 'периферия', 'клавиатура', 'мышь',
                    'монитор', 'принтер', 'сканер', 'веб-камера', 'микрофон'
                ],
                'weight': 0,
                'priority': 2
            },
            'security': {
                'keywords': [
                    'безопасность', 'вирус', 'хакер', 'кибербезопасность', 'шифрование', 'пароль',
                    'защита', 'malware', 'ransomware', 'trojan', 'spyware', 'антивирус', 'antivirus',
                    'kaspersky', 'eset', 'norton', 'mcafee', 'bitdefender', 'avast', 'брандмауэр',
                    'firewall', 'сетевой экран', 'ids', 'ips', 'обнаружение вторжений', 'prevention',
                    'атака', 'attack', 'ddos', 'фишинг', 'phishing', 'спам', 'social engineering',
                    'социальная инженерия', 'уязвимость нулевого дня', 'zero-day', 'exploit',
                    'патч', 'update', 'обновление безопасности', 'криптография', 'cryptography',
                    'aes', 'rsa', 'ssl', 'tls', 'https', 'сертификат', 'certificate', 'pki',
                    'data breach', 'утечка данных', 'leak', 'information security', 'биометрия',
                    'biometrics', 'отпечаток', 'face id', 'распознавание лица', 'двухфакторная аутентификация',
                    '2fa', 'mfa', 'многофакторная аутентификация', 'ключ доступа', 'access key'
                ],
                'weight': 0,
                'priority': 2
            },
            'business': {
                'keywords': [
                    'компания', 'корпорация', 'стартап', 'инвестиции', 'рынок', 'бизнес',
                    'прибыль', 'руководитель', 'управление', 'ceo', 'cfo', 'cto', 'акции',
                    'stock', 'фондовый рынок', 'stock market', 'nasdaq', 'nyse', 'moex',
                    'дивиденды', 'капитализация', 'market cap', 'венчурный капитал', 'venture capital',
                    'vc', 'angel investor', 'бизнес-ангел', 'посевные инвестиции', 'seed funding',
                    'series a', 'series b', 'ipo', 'spac', 'exit', 'merger', 'acquisition',
                    'слияния и поглощения', 'm&a', 'due diligence', 'юридическая проверка',
                    'бизнес-план', 'pitch', 'питч-презентация', 'коворкинг', 'incubator', 'инкубатор',
                    'акселератор', 'accelerator', 'y combinator', 'менеджмент', 'management',
                    'hr', 'human resources', 'рекрутинг', 'onboarding', 'корпоративная культура',
                    'remote work', 'удаленная работа', 'продукт', 'product', 'product manager',
                    'pm', 'project manager', 'проект', 'agile', 'scrum', 'kanban', 'kpi', 'метрики'
                ],
                'weight': 0,
                'priority': 2
            },
            'crypto': {
                'keywords': [
                    'криптовалюта', 'биткоин', 'bitcoin', 'btc', 'эфириум', 'ethereum', 'eth',
                    'блокчейн', 'blockchain', 'альткоин', 'altcoin', 'майнинг', 'mining',
                    'стейкинг', 'staking', 'defi', 'decentralized finance', 'nft', 'non-fungible token',
                    'токен', 'token', 'coinbase', 'binance', 'bybit', 'kucoin', 'кошелек', 'wallet',
                    'hardware wallet', 'ledger', 'trezor', 'метаморск', 'metamask', 'смарт-контракт',
                    'smart contract', 'solidity', 'rust', 'web3', 'дао', 'dao', 'decentralized autonomous organization',
                    'ico', 'ieo', 'ido', 'initial coin offering', 'airdrop', 'аирдроп', 'газ', 'gas fee',
                    'комиссия сети', 'транзакция', 'халвинг', 'halving', 'быки', 'медведи',
                    'bull market', 'bear market', 'волатильность', 'volatility', 'stablecoin',
                    'стейблкоин', 'usdt', 'usdc', 'dai', 'tether', 'централизованная биржа', 'dex',
                    'decentralized exchange', 'uniswap', 'pancakeswap', 'регулирование', 'regulation'
                ],
                'weight': 0,
                'priority': 2
            },
            'health': {
                'keywords': [
                    'здоровье', 'медицина', 'врач', 'больница', 'диагностика', 'лечение',
                    'здоровый образ жизни', 'зож', 'здоровое питание', 'диета', 'фитнес',
                    'тренировка', 'спорт', 'бег', 'йога', 'плавание', 'кардио', 'силовая тренировка',
                    'реабилитация', 'recovery', 'витамины', 'биодобавки', 'supplements', 'иммунитет',
                    'сон', 'sleep', 'психическое здоровье', 'mental health', 'стресс', 'тревожность',
                    'depression', 'депрессия', 'therapy', 'терапия', 'covid-19', 'коронавирус',
                    'пандемия', 'вакцина', 'вакцинация', 'booster', 'тест', 'pcr', 'антиген',
                    'антитело', 'гены', 'генетический тест', 'dna test', 'долголетие', 'longevity',
                    'anti-age', 'anti-aging', 'биохакер', 'biohacking', 'гмо', 'gmo', 'органик',
                    'organic', 'superfood', 'суперфуд', 'детокс', 'веган', 'вегетарианец', 'хирургия',
                    'surgery', 'микрохирургия', 'робот-хирург', 'da vinci', 'телемедицина', 'telehealth'
                ],
                'weight': 0,
                'priority': 2
            }
        }
        
        # Считаем вес для каждой категории с улучшенной логикой
        for category, data in categories.items():
            weight = 0
            
            for keyword in data['keywords']:
                # Проверяем вхождения с учетом границ слов
                pattern = r'\b' + re.escape(keyword) + r'\b'
                
                # Заголовок имеет больший вес (5 баллов)
                if re.search(pattern, title_lower):
                    weight += 5
                # Полный текст имеет меньший вес (2 балла)
                elif re.search(pattern, full_text):
                    weight += 2
            
            # Проверяем исключения (снижаем вес если есть исключающие слова)
            if 'exclude' in data:
                for exclude_word in data['exclude']:
                    if exclude_word in full_text:
                        weight = max(0, weight - 3)  # Существенно снижаем вес
            
            data['weight'] = weight
        
        # Сортируем категории по весу и приоритету
        def category_sort_key(item):
            category, data = item
            return (data['weight'], data.get('priority', 0))
        
        sorted_categories = sorted(categories.items(), key=category_sort_key, reverse=True)
        
        # Выбираем только категории с весом > 3 и максимум 3 самые релевантные
        found_categories = [cat for cat, data in sorted_categories if data['weight'] > 3][:3]
        
        # Если категорий не найдено, пробуем снизить порог
        if not found_categories:
            found_categories = [cat for cat, data in sorted_categories if data['weight'] > 1][:2]
        
        # Если все еще не найдено, используем общие теги
        if not found_categories:
            logger.info("ℹ️ Категории не определены, используются общие теги")
            return ['technology', 'news']
        
        # Добавляем общие теги
        result_categories = found_categories + ['technology', 'news']
        
        # Логируем результат
        logger.info(f"🏷️ Определены категории: {result_categories}")
        for cat in found_categories:
            logger.info(f"   - {cat}: вес {categories[cat]['weight']}")
        
        return result_categories

    def get_hashtags_for_category(self, categories):
        """Улучшенное получение хештегов для категорий"""
        category_hashtags = {
            'ai': ['ИИ', 'ИскусственныйИнтеллект', 'Нейросети', 'AI'],
            'space': ['Космос', 'SpaceX', 'NASA', 'Астрономия'],
            'gadgets': ['Гаджеты', 'Техника', 'Электроника', 'Устройства'],
            'tv': ['Телевизоры', 'ТВ', 'Дисплеи', '4K'],
            'auto': ['Авто', 'Автомобили', 'Транспорт', 'Электромобили'],
            'games': ['Игры', 'Гейминг', 'ИгровыеНовости', 'Киберспорт'],
            'science': ['Наука', 'Исследования', 'Открытия', 'Технологии'],
            'internet': ['Интернет', 'Онлайн', 'Соцсети', 'Цифровизация'],
            'software': ['Софт', 'Программы', 'Приложения', 'Разработка'],
            'hardware': ['Железо', 'Компьютеры', 'Комплектующие', 'Апгрейд'],
            'security': ['Безопасность', 'Кибербезопасность', 'ЗащитаДанных', 'Антивирус'],
            'business': ['Бизнес', 'Стартапы', 'Инновации', 'Технобизнес'],
            'crypto': ['Криптовалюта', 'Блокчейн', 'NFT', 'Биткоин'],
            'health': ['Здоровье', 'Медицина', 'Биотехнологии', 'ЗОЖ'],
            'technology': ['Технологии', 'IT', 'Инновации', 'ТехноНовости'],
            'news': ['Новости', 'СвежиеНовости', 'Обзор']
        }
        
        hashtags = []
        used_hashtags = set()
        
        # Собираем хештеги для каждой категории (уже с #)
        for category in categories:
            if category in category_hashtags:
                for hashtag in category_hashtags[category]:
                    hashtag_with_hash = f"#{hashtag}"
                    if hashtag_with_hash not in used_hashtags:
                        hashtags.append(hashtag_with_hash)
                        used_hashtags.add(hashtag_with_hash)
        
        # Убираем дубликаты и возвращаем максимум 5 хештегов
        unique_hashtags = list(set(hashtags))[:5]
        
        # Сортируем для консистентности
        unique_hashtags.sort()
        
        logger.info(f"🏷️ Сгенерированы хештеги: {unique_hashtags}")
        return unique_hashtags

    async def fetch_news(self):
        """Получение новостей с IXBT"""
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            }
            
            response = self.session.get(IXBT_RSS_URL, headers=headers, timeout=20)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            news_list = []
            
            for entry in feed.entries[:5]:
                news_hash = self.get_news_hash(entry.title, entry.link)
                
                if news_hash not in self.processed_news:
                    # Добавляем случайную задержку между запросами
                    await asyncio.sleep(random.uniform(2, 5))
                    
                    full_text, image_url = await self.get_full_article_text_and_image(entry.link)
                    
                    if len(full_text) > 150:
                        news_item = {
                            'title': entry.title,
                            'link': entry.link,
                            'summary': entry.summary,
                            'full_text': full_text,
                            'image_url': image_url,
                            'hash': news_hash,
                            'published': entry.published
                        }
                        news_list.append(news_item)
                        logger.info(f"📄 Загружена новость: {entry.title}")
                        if image_url:
                            logger.info(f"🖼️ Найдено изображение для новости: {image_url}")
                        else:
                            logger.warning("❌ Изображение не найдено для новости")
                    else:
                        logger.warning(f"❌ Слишком короткий текст: {len(full_text)} символов")
            
            return news_list
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []

    async def get_full_article_text_and_image(self, url):
        """Получение текста и изображения из статьи"""
        try:
            # Сначала пробуем получить и текст и изображение через основные методы
            methods = [
                self.method_smart_request,
                self.method_simple_request,
            ]
            
            best_result = None
            all_found_images = []  # Сохраняем ВСЕ найденные изображения
            
            for method in methods:
                try:
                    full_text, image_url = await method(url)
                    logger.info(f"🔄 Метод {method.__name__}: текст={len(full_text) if full_text else 0}, изображение={image_url}")
                    
                    # Сохраняем все найденные изображения
                    if image_url and image_url not in all_found_images:
                        all_found_images.append(image_url)
                        logger.info(f"💾 Сохранено изображение из метода {method.__name__}: {image_url}")
                    
                    if full_text and len(full_text) > 150:
                        logger.info(f"✅ Успешный метод: {method.__name__}")
                        if not best_result or len(full_text) > len(best_result):
                            best_result = full_text
                except Exception as e:
                    logger.warning(f"⚠️ Метод {method.__name__} не сработал: {e}")
                    continue
            
            # Если нашли контент, возвращаем его с лучшим изображением
            if best_result:
                best_image = self.select_best_image(all_found_images) if all_found_images else ""
                logger.info(f"✅ Возвращаем контент с изображением: {best_image}")
                return best_result, best_image
            
            # Если не нашли контент, но нашли изображения - пробуем получить только изображение
            if not best_result and all_found_images:
                logger.info("🖼️ Найдены изображения, но не найден контент. Пробуем получить только изображение...")
                image_only = await self.extract_image_only(url)
                if image_only and image_only not in all_found_images:
                    all_found_images.append(image_only)
            
            # Выбираем лучшее изображение из всех найденных
            best_image = self.select_best_image(all_found_images) if all_found_images else ""
            
            # Fallback - используем RSS описание
            rss_text, rss_image = await self.alternative_content_fetch(url)
            if rss_text and len(rss_text) > 100:
                logger.info("✅ Использовано RSS описание")
                # Добавляем изображение из RSS если есть
                if rss_image and rss_image not in all_found_images:
                    all_found_images.append(rss_image)
                
                # Обновляем лучшее изображение
                best_image = self.select_best_image(all_found_images) if all_found_images else ""
                logger.info(f"🖼️ Финальное изображение: {best_image}")
                return rss_text, best_image
            
            logger.info(f"🖼️ Финальное изображение: {best_image}")
            return "", best_image
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контента: {e}")
            # При ошибке пробуем получить хотя бы изображение
            image_url = await self.extract_image_only(url)
            rss_text, rss_image = await self.alternative_content_fetch(url)
            
            # Собираем все возможные изображения
            all_images = []
            if image_url:
                all_images.append(image_url)
            if rss_image:
                all_images.append(rss_image)
            
            best_image = self.select_best_image(all_images) if all_images else ""
            return rss_text, best_image

    async def extract_image_only(self, url):
        """Отдельный метод для извлечения только изображения"""
        try:
            logger.info(f"🔍 Отдельный поиск изображения для: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем изображение ВСЕМИ способами
            image_url = self.extract_all_possible_images(soup, url)
            
            logger.info(f"🖼️ Результат отдельного поиска: {image_url}")
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка отдельного поиска изображения: {e}")
            return ""

    async def method_smart_request(self, url):
        """Умный запрос с обходом защиты"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        await asyncio.sleep(random.uniform(2, 4))
        
        try:
            response = self.session.get(url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            
            # Проверяем на блокировку
            if any(word in response.text.lower() for word in ['captcha', 'cloudflare', 'access denied', 'bot']):
                raise Exception("Обнаружена защита")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем изображение ВСЕМИ способами
            image_url = self.extract_all_possible_images(soup, url)
            
            # Извлекаем текст
            content = self.extract_content(soup)
            
            return content, image_url
            
        except Exception as e:
            raise Exception(f"Smart request failed: {e}")

    async def method_simple_request(self, url):
        """Простой запрос"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        await asyncio.sleep(random.uniform(1, 2))
        
        try:
            response = self.session.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем изображение ВСЕМИ способами
            image_url = self.extract_all_possible_images(soup, url)
            
            # Извлекаем текст
            content = self.extract_content(soup)
            
            return content, image_url
            
        except Exception as e:
            raise Exception(f"Simple request failed: {e}")

    def extract_all_possible_images(self, soup, base_url):
        """Извлечение изображений ВСЕМИ возможными способами"""
        logger.info("🔍 Начинаю ПОЛНЫЙ поиск изображений на странице...")
        
        found_images = []
        
        # 1. Мета-теги (самый надежный)
        meta_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'meta[itemprop="image"]',
            'meta[name="og:image:url"]',
            'meta[property="twitter:image:src"]',
            'link[rel="image_src"]',
            'link[rel="apple-touch-icon"]',
            'link[rel="apple-touch-startup-image"]',
        ]
        
        for selector in meta_selectors:
            elements = soup.select(selector)
            for element in elements:
                image_url = element.get('content') or element.get('href') or element.get('src')
                if image_url:
                    normalized_url = self.normalize_image_url(image_url, base_url)
                    if normalized_url and normalized_url not in found_images:
                        found_images.append(normalized_url)
                        logger.info(f"✅ Мета-тег {selector}: {normalized_url}")
        
        # 2. Структура статьи iXBT
        article_selectors = [
            'div.b-article img',
            'article img',
            '.b-article__text img',
            '.article-content img',
            '.post-content img',
            '.entry-content img',
            '.article-body img',
            'figure img',
            '.b-article__image img',
            '.article-image',
            '.wp-block-image img',
            '.content img',
            'main img',
            '.news-img',
            '.post-thumbnail img',
            '.entry-thumbnail img',
        ]
        
        for selector in article_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Пробуем все возможные атрибуты
                for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-srcset', 'srcset']:
                    image_url = element.get(attr)
                    if image_url:
                        # Обрабатываем srcset
                        if attr == 'srcset' and ',' in image_url:
                            image_url = image_url.split(',')[0].split(' ')[0]
                        
                        normalized_url = self.normalize_image_url(image_url, base_url)
                        if normalized_url and normalized_url not in found_images:
                            found_images.append(normalized_url)
                            logger.info(f"✅ Статья {selector} [{attr}]: {normalized_url}")
        
        # 3. Все изображения на странице с фильтрацией
        all_images = soup.find_all('img')
        for img in all_images:
            # Пропускаем иконки, логотипы и маленькие изображения
            src = img.get('src', '')
            if any(ignore in src.lower() for ignore in ['logo', 'icon', 'avatar', 'spacer', 'pixel', 'emoji', 'favicon']):
                continue
            
            # Пропускаем слишком маленькие изображения
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    if int(width) < 100 or int(height) < 100:
                        continue
                except:
                    pass
            
            # Пробуем все атрибуты
            for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                image_url = img.get(attr)
                if image_url:
                    normalized_url = self.normalize_image_url(image_url, base_url)
                    if normalized_url and normalized_url not in found_images and self.is_valid_image_url(normalized_url):
                        found_images.append(normalized_url)
                        logger.info(f"✅ Общий поиск [{attr}]: {normalized_url}")
        
        # 4. Ищем в стилях (background-image)
        styles = soup.find_all(style=re.compile(r'background-image'))
        for style in styles:
            style_content = style.get('style', '')
            urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style_content)
            for image_url in urls:
                normalized_url = self.normalize_image_url(image_url, base_url)
                if normalized_url and normalized_url not in found_images:
                    found_images.append(normalized_url)
                    logger.info(f"✅ CSS background: {normalized_url}")
        
        # 5. Ищем в JSON-LD структурированных данных
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                data = json.loads(script.string)
                images = self.extract_images_from_jsonld(data)
                for image_url in images:
                    normalized_url = self.normalize_image_url(image_url, base_url)
                    if normalized_url and normalized_url not in found_images:
                        found_images.append(normalized_url)
                        logger.info(f"✅ JSON-LD: {normalized_url}")
            except:
                pass
        
        logger.info(f"🎯 Всего найдено изображений: {len(found_images)}")
        
        # Выбираем лучшее изображение (приоритет по размеру и качеству)
        if found_images:
            best_image = self.select_best_image(found_images)
            logger.info(f"🏆 Выбрано лучшее изображение: {best_image}")
            return best_image
        
        logger.warning("❌ Изображения не найдены на странице")
        return ""

    def extract_images_from_jsonld(self, data):
        """Извлечение изображений из JSON-LD данных"""
        images = []
        
        if isinstance(data, dict):
            # Проверяем основные поля с изображениями
            for key in ['image', 'thumbnail', 'photo', 'logo']:
                if key in data:
                    image_data = data[key]
                    if isinstance(image_data, str):
                        images.append(image_data)
                    elif isinstance(image_data, dict) and 'url' in image_data:
                        images.append(image_data['url'])
                    elif isinstance(image_data, list):
                        for item in image_data:
                            if isinstance(item, str):
                                images.append(item)
                            elif isinstance(item, dict) and 'url' in item:
                                images.append(item['url'])
            
            # Рекурсивно проверяем вложенные структуры
            for value in data.values():
                if isinstance(value, (dict, list)):
                    images.extend(self.extract_images_from_jsonld(value))
        
        elif isinstance(data, list):
            for item in data:
                images.extend(self.extract_images_from_jsonld(item))
        
        return images

    def select_best_image(self, image_urls):
        """Выбор лучшего изображения из найденных"""
        if not image_urls:
            return ""
        
        # Приоритет по расширениям
        extension_priority = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        
        for ext in extension_priority:
            for url in image_urls:
                if url.lower().endswith(ext):
                    return url
        
        # Приоритет по ключевым словам в URL
        priority_keywords = ['large', 'big', 'main', 'featured', 'cover', 'hero']
        for keyword in priority_keywords:
            for url in image_urls:
                if keyword in url.lower():
                    return url
        
        # Возвращаем первое изображение
        return image_urls[0]

    def extract_content(self, soup):
        """Извлечение контента из страницы"""
        # Удаляем ненужные элементы
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            element.decompose()
        
        # Метод 1: Поиск по специфичным селекторам iXBT
        selectors = [
            'div.b-article__text',
            'article.b-article',
            'div.b-article-body',
            'div.article-content',
            'div.post-content',
            'div.entry-content',
            'div.content',
            'article',
            'div.article__text',
            'div.article-body',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = self.clean_and_extract_text(element)
                if len(text) > 200:
                    logger.info(f"✅ Найден контент по селектору: {selector}")
                    return text
        
        # Метод 2: Поиск по семантическим тегам
        semantic_tags = ['main', 'article', 'div[role="main"]']
        for tag in semantic_tags:
            if tag.startswith('div'):
                element = soup.find('div', role='main')
            else:
                element = soup.find(tag)
                
            if element:
                text = self.clean_and_extract_text(element)
                if len(text) > 200:
                    logger.info(f"✅ Найден контент по семантике: {tag}")
                    return text
        
        return ""

    def clean_and_extract_text(self, element):
        """Очистка и извлечение текста из элемента"""
        # Клонируем элемент
        element = BeautifulSoup(str(element), 'html.parser')
        
        # Удаляем мусорные элементы
        garbage_selectors = [
            'div.ad', 'div.adv', 'div.advertisement', 'div.banner',
            'div.comments', 'div.social', 'div.share', 'div.related',
            'div.recommended', 'div.teaser', 'div.meta', 'div.tags',
            'ins', 'iframe', 'a[href*="ad"]', 'div[class*="ad"]',
            'div[class*="banner"]', 'div.widget', 'div.subscribe',
            'div.navigation', 'div.pagination', 'div.author',
        ]
        
        for selector in garbage_selectors:
            for elem in element.select(selector):
                elem.decompose()
        
        # Извлекаем только параграфы
        paragraphs = element.find_all('p')
        text_parts = []
        
        for p in paragraphs:
            text = p.get_text(strip=True)
            if self.is_meaningful_text(text):
                text_parts.append(text)
        
        text = '\n'.join(text_parts)
        return self.post_process_text(text)

    def is_meaningful_text(self, text):
        """Проверка, является ли текст осмысленным"""
        if len(text) < 40:
            return False
            
        garbage_indicators = [
            'реклама', 'подписывайтесь', 'источник:', 'читать также',
            'комментар', 'фото:', 'видео:', 'читать далее', 'share',
            'теги:', 'оцените статью', 'поделиться', 'редакция рекомендует',
        ]
        
        if any(indicator in text.lower() for indicator in garbage_indicators):
            return False
            
        return len(text.split()) >= 5

    def post_process_text(self, text):
        """Постобработка текста"""
        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем URL
        text = re.sub(r'https?://\S+', '', text)
        
        # Удаляем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()

    def is_valid_image_url(self, url):
        """Проверка, что URL похож на изображение"""
        if not url or url.strip() == '':
            return False
        
        url_lower = url.lower()
        
        # Проверяем расширения файлов
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.svg']
        if any(url_lower.endswith(ext) for ext in valid_extensions):
            return True
        
        # Проверяем паттерны в URL
        image_patterns = [
            '/images/', '/img/', '/uploads/', '/media/',
            'image', 'photo', 'picture', 'img', 'upload'
        ]
        if any(pattern in url_lower for pattern in image_patterns):
            return True
        
        # Проверяем наличие параметров с изображениями
        if any(param in url_lower for param in ['/wp-content/', '/content/images/']):
            return True
        
        return False

    def normalize_image_url(self, image_url, base_url):
        """Нормализация URL изображения"""
        if not image_url:
            return ""
        
        # Очищаем URL от пробелов и кодируем специальные символы
        image_url = image_url.strip()
        image_url = image_url.replace(' ', '%20')  # Кодируем пробелы
        
        # Удаляем параметры запроса и якоря
        image_url = image_url.split('?')[0].split('#')[0]
        
        # Преобразуем относительные URL
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = 'https://www.ixbt.com' + image_url
        elif not image_url.startswith(('http://', 'https://')):
            # Если URL относительный без слеша
            if image_url.startswith('./'):
                image_url = image_url[2:]
            base_domain = 'https://www.ixbt.com'
            image_url = base_domain + '/' + image_url.lstrip('/')
        
        return image_url

    async def alternative_content_fetch(self, url):
        """Альтернативный метод через RSS"""
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(IXBT_RSS_URL, headers=headers, timeout=20)
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries:
                if entry.link == url and hasattr(entry, 'summary'):
                    soup = BeautifulSoup(entry.summary, 'html.parser')
                    text = soup.get_text(strip=True)
                    
                    # Ищем изображение в RSS описании
                    image_url = ""
                    img_tag = soup.find('img')
                    if img_tag and img_tag.get('src'):
                        image_url = self.normalize_image_url(img_tag.get('src'), url)
                    
                    if len(text) > 100:
                        logger.info("✅ Использовано RSS описание")
                        return text, image_url
            
            return "", ""
        except Exception as e:
            logger.error(f"❌ Ошибка альтернативного получения: {e}")
            return "", ""

    async def download_image(self, image_url, filename):
        """Скачивание изображения с улучшенной обработкой ошибок"""
        try:
            if not image_url:
                logger.warning("❌ URL изображения пустой")
                return False
                
            logger.info(f"🖼️ Скачиваю изображение: {image_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Referer': 'https://www.ixbt.com/',
            }
            
            # Добавляем таймауты и stream для больших файлов
            response = self.session.get(
                image_url, 
                headers=headers, 
                timeout=30, 
                verify=False,
                stream=True
            )
            response.raise_for_status()
            
            # Проверяем content-type
            content_type = response.headers.get('content-type', '').lower()
            logger.info(f"📋 Content-Type: {content_type}")
            
            if 'image' not in content_type:
                logger.warning(f"⚠️ Неизвестный content-type: {content_type}")
            
            # Сохраняем изображение
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Проверяем размер файла
            file_size = os.path.getsize(filename)
            logger.info(f"📦 Размер файла: {file_size} байт")
            
            if file_size < 1024:  # Минимум 1KB
                logger.warning(f"⚠️ Файл слишком маленький: {file_size} байт")
                os.remove(filename)
                return False
            
            # Пробуем открыть изображение для проверки валидности
            try:
                with Image.open(filename) as img:
                    img.verify()  # Проверяем целостность файла
                logger.info(f"✅ Изображение скачано и проверено: {filename}")
                return True
            except Exception as img_error:
                logger.error(f"❌ Невалидное изображение: {img_error}")
                os.remove(filename)
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ Таймаут при скачивании изображения")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ Ошибка соединения при скачивании изображения")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка {e.response.status_code}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка скачивания: {e}")
            return False

    def create_news_image(self, title, filename):
        """Создание новостного изображения (только как fallback)"""
        try:
            width, height = 1200, 630
            
            # Создаем базовое изображение
            image = Image.new('RGB', (width, height), color=(30, 30, 46))
            draw = ImageDraw.Draw(image)
            
            # Добавляем градиент
            for y in range(height):
                r = int(30 + (50 * y / height))
                g = int(30 + (40 * y / height))
                b = int(46 + (50 * y / height))
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # Добавляем заголовок (упрощенная версия)
            try:
                # Пробуем использовать системный шрифт
                font = ImageFont.load_default()
                title_lines = self.wrap_text(title, font, width - 100)
                
                # Рисуем заголовок
                y_position = height // 3
                for line in title_lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    x_position = (width - text_width) // 2
                    draw.text((x_position, y_position), line, fill=(255, 255, 255), font=font)
                    y_position += bbox[3] - bbox[1] + 10
            except:
                pass
            
            image.save(filename, 'JPEG', quality=90)
            logger.info(f"🖼️ Создано новостное изображение (fallback): {filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания изображения: {e}")
            # Создаем простейшее изображение
            try:
                Image.new('RGB', (800, 400), color=(90, 100, 110)).save(filename)
                return True
            except:
                return False

    def wrap_text(self, text, font, max_width):
        """Перенос текста"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines[:3]  # Максимум 3 строки

    def rephrase_text(self, text, title):
        """Перефразирование текста"""
        try:
            # Разбиваем на предложения
            sentences = re.split(r'[.!?]+', text)
            meaningful_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 30:
                    continue
                    
                # Пропускаем мусор
                if any(word in sentence.lower() for word in [
                    'реклама', 'подписывайтесь', 'источник:', 'комментар'
                ]):
                    continue
                    
                meaningful_sentences.append(sentence)
            
            if not meaningful_sentences:
                return ""
            
            # Берем 3 самых информативных предложения
            selected_sentences = meaningful_sentences[:3]
            
            # Перефразируем
            rephrased_sentences = []
            for sentence in selected_sentences:
                rephrased = self.rephrase_sentence(sentence)
                if rephrased:
                    rephrased_sentences.append(rephrased)
            
            if not rephrased_sentences:
                return ""
            
            # Форматируем
            summary = self.format_sentences_properly(rephrased_sentences)
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Ошибка перефразирования: {e}")
            return text[:400] + '...'

    def rephrase_sentence(self, sentence):
        """Перефразирование предложения"""
        try:
            # Убираем указания на источник
            sentence = re.sub(r'\([^)]*источник[^)]*\)', '', sentence, flags=re.IGNORECASE)
            sentence = re.sub(r'по данным[^,.]+', '', sentence, flags=re.IGNORECASE)
            sentence = re.sub(r'сообщает[^,.]+', '', sentence, flags=re.IGNORECASE)
            
            # Заменяем синонимы
            synonyms = {
                'сообщается': 'по информации',
                'заявил': 'отметил',
                'объявил': 'сообщил',
                'разработал': 'создал',
                'представил': 'показал',
                'анонсировал': 'объявил о',
                'компания': 'организация',
                'корпорация': 'компания',
                'стартап': 'новая компания',
            }
            
            words = sentence.split()
            rephrased_words = []
            
            for word in words:
                lower_word = word.lower()
                if lower_word in synonyms:
                    rephrased_words.append(synonyms[lower_word])
                else:
                    rephrased_words.append(word)
            
            rephrased = ' '.join(rephrased_words)
            
            return rephrased.strip()
            
        except Exception as e:
            return sentence

    def format_sentences_properly(self, sentences):
        """Форматирование предложений"""
        if not sentences:
            return ""
        
        formatted_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if not sentence.endswith(('.', '!', '?')):
                sentence += '.'
            
            if sentence and len(sentence) > 1:
                sentence = sentence[0].upper() + sentence[1:]
            
            formatted_sentences.append(sentence)
        
        result = ' '.join(formatted_sentences)
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip()

    def create_news_post(self, news_item):
        """Создание поста для Telegram с проверкой на запрещенные организации"""
        title = news_item['title']
        original_text = news_item['full_text']
        
        logger.info(f"🎯 Обрабатываю новость: {title}")
        
        # Проверяем на запрещенные организации
        banned_orgs = self.check_banned_organizations(title, original_text)
        
        warning_text = ""
        if banned_orgs:
            warning_text = "\n\n⚠️ *ВНИМАНИЕ:* В новости упоминаются организации, "
            warning_text += "запрещенные на территории РФ"
            
            # Добавляем список найденных организаций (первые 3)
            orgs_list = banned_orgs[:3]
            warning_text += f"\nОбнаружены упоминания: {', '.join(orgs_list)}"
            
            if len(banned_orgs) > 3:
                warning_text += f" и ещё {len(banned_orgs) - 3}"
            
            logger.warning(f"🚫 Обнаружены запрещенные организации: {banned_orgs}")
        
        # Перефразируем текст
        rephrased_text = self.rephrase_text(original_text, title)
        
        if not rephrased_text or len(rephrased_text.strip()) < 80:
            logger.error("❌ Не удалось перефразировать текст")
            return None
        
        # Определяем категорию и хештеги
        categories = self.detect_news_category(title, rephrased_text)
        hashtags = self.get_hashtags_for_category(categories)
        
        # Создаем пост с предупреждением (если есть)
        post_text = self.format_post(title, rephrased_text, hashtags, warning_text)
        
        return post_text

   def format_post(self, title, text, hashtags, warning_text=""):
        """Форматирование поста с возможным предупреждением"""
        clean_title = re.sub(r'<[^>]+>', '', title.strip())
        clean_text = re.sub(r'<[^>]+>', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text.strip())
        
        # Хештеги уже содержат #, просто объединяем
        hashtags_str = ' '.join(hashtags)
        
        # Жирный заголовок с помощью Markdown
        post = f"*{clean_title}*\n\n{clean_text}"
        
        # Добавляем предупреждение если есть
        if warning_text:
            post += warning_text
        
        post += f"\n\n{hashtags_str}"
        
        return post

    def escape_markdown_v2(self, text):
        """Экранирование для MarkdownV2"""
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        
        def escape_text(text_to_escape):
            return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text_to_escape)
        
        lines = text.split('\n')
        escaped_lines = []
        
        for line in lines:
            escaped_lines.append(escape_text(line))
        
        return '\n'.join(escaped_lines)

   def format_telegram_post(self, post_text):
        """Форматирование для Telegram с учетом предупреждений"""
        try:
            # Разделяем на части
            parts = post_text.split('\n\n')
            
            if len(parts) >= 3:
                # Заголовок (первая часть) - оставляем жирный
                title_line = parts[0]
                
                # Основной текст (вторая часть) - экранируем
                text_content = parts[1]
                escaped_text = self.escape_markdown_v2(text_content)
                
                # Предупреждение (может быть в третьей части)
                warning_content = ""
                hashtags = parts[-1]  # Хештеги всегда последние
                
                # Если есть предупреждение, оно будет перед хештегами
                if len(parts) >= 4 and "ВНИМАНИЕ" in parts[2]:
                    warning_content = parts[2]
                    # Экранируем предупреждение, но оставляем хештеги как есть
                    escaped_warning = self.escape_markdown_v2(warning_content)
                    formatted = f"{title_line}\n\n{escaped_text}\n\n{escaped_warning}\n\n{hashtags}"
                else:
                    formatted = f"{title_line}\n\n{escaped_text}\n\n{hashtags}"
            else:
                # Если структура нестандартная, экранируем только текст
                lines = post_text.split('\n')
                if len(lines) >= 3:
                    title_line = lines[0]
                    text_content = '\n'.join(lines[1:-1])
                    hashtags = lines[-1]
                    escaped_text = self.escape_markdown_v2(text_content)
                    formatted = f"{title_line}\n\n{escaped_text}\n\n{hashtags}"
                else:
                    # Просто экранируем весь текст кроме хештегов
                    formatted = self.escape_markdown_v2(post_text)
            
            if len(formatted) > 1024:
                # Упрощаем текст если слишком длинный
                lines = formatted.split('\n')
                if len(lines) > 2:
                    short_text = lines[2][:300] + '...'
                    simplified = f"{lines[0]}\n\n{short_text}"
                    
                    # Сохраняем предупреждение и хештеги если есть
                    if len(lines) > 4 and "ВНИМАНИЕ" in lines[4]:
                        simplified += f"\n\n{lines[4]}\n\n{lines[-1]}"
                    elif len(lines) > 3:
                        simplified += f"\n\n{lines[-1]}"
                    
                    return simplified
            
            return formatted
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования: {e}")
            # Простой fallback без Markdown
            simple_text = re.sub(r'[*_`\[\]()~>#+\-=|{}.!]', '', post_text)
            return simple_text[:900] + "\n\n#Технологии #Новости"

    async def publish_to_telegram(self, post_text, image_path, news_hash):
        """Публикация в Telegram"""
        for attempt in range(3):
            try:
                formatted_text = self.format_telegram_post(post_text)
                
                logger.info(f"📤 Публикация (попытка {attempt + 1})")
                
                with open(image_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo,
                        caption=formatted_text,
                        parse_mode='MarkdownV2'
                    )
                
                logger.info("✅ Пост опубликован")
                
                # Удаляем изображение после успешной публикации
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logger.info(f"🗑️ Изображение удалено: {image_path}")
                except Exception as e:
                    logger.error(f"❌ Ошибка удаления изображения: {e}")
                
                return True
                
            except TelegramError as e:
                logger.error(f"❌ Ошибка Telegram: {e}")
                
                if attempt == 2:
                    try:
                        plain_text = re.sub(r'[*_`\[\]()~>#+\-=|{}.!]', '', post_text)
                        plain_text = plain_text[:800] + "\n\n#Технологии #Новости"
                        
                        with open(image_path, 'rb') as photo:
                            await self.bot.send_photo(
                                chat_id=CHANNEL_ID,
                                photo=photo,
                                caption=plain_text
                            )
                        logger.info("✅ Пост опубликован как простой текст")
                        
                        # Удаляем изображение после успешной публикации
                        try:
                            if os.path.exists(image_path):
                                os.remove(image_path)
                                logger.info(f"🗑️ Изображение удалено: {image_path}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка удаления изображения: {e}")
                        
                        return True
                    except Exception as e2:
                        logger.error(f"❌ Финальная ошибка: {e2}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Ошибка публикации: {e}")
                await asyncio.sleep(2)
        
        return False

    async def process_news_cycle(self):
        """Цикл обработки новостей"""
        try:
            logger.info("🔄 Поиск новых новостей...")
            
            news_list = await self.fetch_news()
            
            if not news_list:
                logger.info("ℹ️ Новых новостей нет")
                return
                
            for news_item in news_list:
                logger.info(f"📝 Обработка: {news_item['title']}")
                logger.info(f"🔗 Ссылка: {news_item['link']}")
                logger.info(f"🖼️ URL изображения: {news_item['image_url']}")
                
                post_text = self.create_news_post(news_item)
                
                if not post_text:
                    continue
                
                # Создаем папки
                Path("images").mkdir(exist_ok=True)
                Path("downloaded_images").mkdir(exist_ok=True)
                
                image_filename = f"downloaded_images/news_{news_item['hash']}.jpg"
                fallback_image_filename = f"images/news_{news_item['hash']}.jpg"
                
                # Пробуем скачать изображение с сайта
                image_downloaded = False
                if news_item['image_url']:
                    logger.info(f"🖼️ Пытаюсь скачать изображение: {news_item['image_url']}")
                    image_downloaded = await self.download_image(news_item['image_url'], image_filename)
                else:
                    logger.warning("❌ URL изображения не найден в новости")
                
                # Используем скачанное изображение или создаем fallback
                if image_downloaded:
                    logger.info("✅ Использовано изображение из новости")
                    final_image_path = image_filename
                else:
                    logger.warning("⚠️ Не удалось скачать изображение, создаю fallback")
                    if self.create_news_image(news_item['title'], fallback_image_filename):
                        final_image_path = fallback_image_filename
                    else:
                        logger.error("❌ Не удалось создать изображение, пропускаем новость")
                        continue
                
                # Публикуем
                success = await self.publish_to_telegram(
                    post_text, final_image_path, news_item['hash']
                )
                
                if success:
                    self.processed_news.add(news_item['hash'])
                    self.save_processed_news()
                    logger.info(f"✅ Новость обработана: {news_item['hash']}")
                    await asyncio.sleep(10)
                else:
                    logger.error("❌ Ошибка публикации")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка цикла обработки: {e}")

async def main():
    """Основная функция для облачного хостинга"""
    bot = SmartNewsBot()
    
    logger.info("🚂 Бот запущен на Railway!")
    logger.info(f"📊 Обработанных новостей: {len(bot.processed_news)}")
    logger.info(f"🔧 Токен: {'установлен' if TOKEN else 'не установлен'}")
    logger.info(f"📢 Канал: {CHANNEL_ID}")
    
    # Бесконечный цикл для облачного хостинга
    while True:
        try:
            await bot.process_news_cycle()
            logger.info(f"💤 Ожидание {CHECK_INTERVAL} сек...")
            await asyncio.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен пользователем")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в основном цикле: {e}")
            import traceback
            logger.error(f"🔍 Детали ошибки: {traceback.format_exc()}")
            logger.info("🔄 Перезапуск через 60 секунд...")
            await asyncio.sleep(60)

if __name__ == '__main__':
    # Информация о среде выполнения
    print(f"🐍 Python version: {sys.version}")
    print(f"🚂 Railway environment: {'RAILWAY_ENVIRONMENT' in os.environ}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Фатальная ошибка: {e}")
        sys.exit(1)