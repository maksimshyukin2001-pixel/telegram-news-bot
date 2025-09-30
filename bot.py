import asyncio
import logging
import hashlib
import json
import os
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

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Конфигурация
TOKEN = "7445394461:AAGHiGYBiCwEg-tbchU9lOJmywv4CjcKuls"
CHANNEL_ID = "@techno_met"
IXBT_RSS_URL = "https://www.ixbt.com/export/news.rss"
CHECK_INTERVAL = 1800  # 30 минут

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
            
            # Создаем базое изображение
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
                if len(meaningful_sentences) >= 3:
                    break
            
            if not meaningful_sentences:
                return text[:400] + "..." if len(text) > 400 else text
            
            # Берем первые 2-3 предложения
            result = ' '.join(meaningful_sentences[:3])
            
            # Ограничиваем длину
            if len(result) > 500:
                result = result[:497] + "..."
            
            return result
            
        except Exception as e:
            logger.error(f"Error rephrasing text: {e}")
            return text[:400] + "..." if len(text) > 400 else text

    def format_news_message(self, news_item):
        """Форматирование сообщения для отправки"""
        try:
            # Перефразируем текст
            rephrased_text = self.rephrase_text(news_item['full_text'], news_item['title'])
            
            # Форматируем сообщение (просто заголовок и текст)
            message = f"{news_item['title']}\n\n{rephrased_text}"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            # Fallback сообщение
            return f"{news_item['title']}\n\n{news_item['summary']}"

    async def send_news_to_channel(self, news_item):
        """Отправка новости в канал"""
        try:
            message_text = self.format_news_message(news_item)
            image_path = None
            
            # Скачиваем изображение если есть
            if news_item['image_url']:
                image_filename = f"temp_image_{int(time.time())}.jpg"
                if await self.download_image(news_item['image_url'], image_filename):
                    image_path = image_filename
                    logger.info(f"✅ Изображение готово к отправке: {image_path}")
                else:
                    logger.warning("❌ Не удалось скачать изображение, создаем fallback")
                    # Создаем fallback изображение
                    fallback_image = f"fallback_{int(time.time())}.jpg"
                    if self.create_news_image(news_item['title'], fallback_image):
                        image_path = fallback_image
            
            # Отправляем сообщение
            if image_path and os.path.exists(image_path):
                try:
                    with open(image_path, 'rb') as photo:
                        await self.bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=photo,
                            caption=message_text
                        )
                    logger.info("✅ Новость отправлена с изображением")
                except TelegramError as e:
                    logger.error(f"❌ Ошибка отправки с фото: {e}")
                    # Пробуем отправить без фото
                    await self.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message_text
                    )
                    logger.info("✅ Новость отправлена без изображения")
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message_text
                )
                logger.info("✅ Новость отправлена без изображения")
            
            # Очистка временных файлов
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except:
                    pass
            
            # Помечаем новость как обработанную
            self.processed_news.add(news_item['hash'])
            self.save_processed_news()
            
            logger.info(f"✅ Новость отправлена: {news_item['title']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки новости: {e}")
            return False

    async def run(self):
        """Основной цикл бота"""
        logger.info("🤖 Бот запущен!")
        
        while True:
            try:
                logger.info("🔄 Проверка новых новостей...")
                news_list = await self.fetch_news()
                
                if news_list:
                    logger.info(f"📥 Найдено {len(news_list)} новых новостей")
                    
                    for news_item in news_list:
                        await self.send_news_to_channel(news_item)
                        await asyncio.sleep(10)  # Задержка между отправками
                else:
                    logger.info("📭 Новых новостей нет")
                
                logger.info(f"⏳ Ожидание {CHECK_INTERVAL} секунд...")
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                await asyncio.sleep(60)

async def main():
    bot = SmartNewsBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
