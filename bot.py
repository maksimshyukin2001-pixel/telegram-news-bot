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
import news_tags

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

    def check_banned_organizations(self, title, text):
        """Улучшенная проверка новости на упоминание запрещенных организаций"""
        content = f"{title} {text}".lower()
        
        found_organizations = []
        
        # Проверяем полные названия организаций (только целые слова)
        for org in banned_organizations.BANNED_ORGANIZATIONS:
            # Используем границы слов для точного совпадения
            pattern = r'\b' + re.escape(org.lower()) + r'\b'
            if re.search(pattern, content):
                found_organizations.append(org)
        
        # Улучшенная проверка по ключевым словам
        for keyword in banned_organizations.BANNED_KEYWORDS:
            # Ищем только целые слова
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, content):
                # Получаем более точный контекст
                matches = re.finditer(pattern, content)
                for match in matches:
                    start = max(0, match.start() - 30)
                    end = min(len(content), match.end() + 30)
                    context = content[start:end]
                    
                    # Фильтруем ложные срабатывания
                    if len(keyword) > 2:  # Игнорируем слишком короткие слова
                        # Проверяем, что это не часть другого слова
                        words_in_context = re.findall(r'\b\w+\b', context)
                        if any(keyword == word.lower() for word in words_in_context):
                            found_organizations.append(f"ключевое слово: '{keyword}' в контексте: ...{context}...")
        
        # Дополнительная проверка: игнорируем слишком короткие слова (менее 3 символов)
        # если они не являются частью запрещенных организаций
        filtered_organizations = []
        for org in found_organizations:
            if "ключевое слово:" in org:
                # Извлекаем ключевое слово из строки
                match = re.search(r"ключевое слово: '([^']*)'", org)
                if match and len(match.group(1)) < 3:
                    logger.info(f"🔍 Игнорируем короткое ключевое слово: '{match.group(1)}'")
                    continue
            filtered_organizations.append(org)
        
        return filtered_organizations

    def format_news_message(self, news_item):
        """Форматирование сообщения для публикации БЕЗ источника и хештегов"""
        title = news_item['title']
        text = news_item['full_text']
        
        # Проверяем на запрещенные организации
        banned_orgs = self.check_banned_organizations(title, text)
        if banned_orgs:
            logger.warning(f"🚫 Новость заблокирована из-за упоминания запрещенных организаций: {banned_orgs}")
            return None
        
        # Обрезаем текст до 800 символов
        if len(text) > 800:
            text = text[:797] + "..."
        
        # Форматируем сообщение БЕЗ ссылки на источник и хештегов
        message = f"📰 {title}\n\n"
        message += f"{text}"
        
        return message

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
            logger.error(f"❌ Ошибка получения статьи: {e}")
            return "", ""

    async def method_smart_request(self, url):
        """Умный запрос с обработкой JavaScript и динамического контента"""
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
            
            response = self.session.get(url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Удаляем ненужные элементы
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'aside']):
                element.decompose()
            
            # Ищем основной контент
            content_selectors = [
                'article',
                '.article-content',
                '.post-content',
                '.entry-content',
                '.content',
                '.news-text',
                '[class*="content"]',
                '[class*="article"]',
                '[class*="post"]',
                '[class*="entry"]',
                'main'
            ]
            
            content = None
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break
            
            if not content:
                # Если не нашли контейнер, используем body
                content = soup.find('body')
            
            # Извлекаем текст
            text = content.get_text(separator='\n', strip=True) if content else ""
            
            # Очищаем текст
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            # Ищем изображение
            image_url = ""
            image_selectors = [
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                'img[class*="article"]',
                'img[class*="news"]',
                'img[class*="post"]',
                'img[class*="entry"]',
                '.article-image img',
                '.post-image img',
                '.news-image img',
                '.entry-image img',
                'figure img'
            ]
            
            for selector in image_selectors:
                img_tag = soup.select_one(selector)
                if img_tag:
                    if img_tag.get('src'):
                        image_url = img_tag['src']
                        break
                    elif img_tag.get('content'):
                        image_url = img_tag['content']
                        break
            
            # Делаем URL абсолютным если нужно
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url and image_url.startswith('/'):
                from urllib.parse import urljoin
                image_url = urljoin(url, image_url)
            
            return cleaned_text, image_url
            
        except Exception as e:
            logger.error(f"Error in smart request: {e}")
            return "", ""

    async def method_simple_request(self, url):
        """Простой запрос для быстрого получения контента"""
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Удаляем ненужные элементы
            for element in soup.find_all(['script', 'style']):
                element.decompose()
            
            # Ищем контент
            content_areas = soup.find_all(['article', 'div', 'section'], 
                                        class_=lambda x: x and any(word in x for word in 
                                                                  ['content', 'article', 'post', 'entry', 'news']))
            
            if not content_areas:
                content_areas = [soup.find('body')]
            
            text_parts = []
            for content in content_areas:
                if content:
                    text = content.get_text(separator='\n', strip=True)
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    text_parts.extend(lines)
            
            # Объединяем и очищаем текст
            cleaned_text = '\n'.join(text_parts)
            
            # Ищем изображение
            image_url = ""
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src:
                    # Проверяем размеры изображения если есть
                    width = img.get('width')
                    height = img.get('height')
                    
                    # Предпочитаем большие изображения
                    if width and height:
                        try:
                            if int(width) >= 300 and int(height) >= 200:
                                image_url = src
                                break
                        except:
                            continue
                    else:
                        # Если нет размеров, берем первое подходящее
                        if not image_url and ('article' in str(img.parent) or 'news' in str(img.parent)):
                            image_url = src
            
            # Делаем URL абсолютным
            if image_url and image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url and image_url.startswith('/'):
                from urllib.parse import urljoin
                image_url = urljoin(url, image_url)
            
            return cleaned_text, image_url
            
        except Exception as e:
            logger.error(f"Error in simple request: {e}")
            return "", ""

    async def extract_image_only(self, url):
        """Извлечение только изображения когда текст не найден"""
        try:
            headers = {'User-Agent': self.ua.random}
            response = self.session.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем Open Graph изображение
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    from urllib.parse import urljoin
                    image_url = urljoin(url, image_url)
                return image_url
            
            # Ищем Twitter изображение
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    from urllib.parse import urljoin
                    image_url = urljoin(url, image_url)
                return image_url
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting image only: {e}")
            return ""

    async def alternative_content_fetch(self, url):
        """Альтернативный метод получения контента через RSS описание"""
        try:
            headers = {'User-Agent': self.ua.random}
            response = self.session.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Пробуем получить описание из meta
            description = soup.find('meta', attrs={'name': 'description'})
            if description and description.get('content'):
                text = description['content']
                
                # Ищем изображение
                image_url = ""
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    image_url = og_image['content']
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        from urllib.parse import urljoin
                        image_url = urljoin(url, image_url)
                
                return text, image_url
            
            return "", ""
            
        except Exception as e:
            logger.error(f"Error in alternative content fetch: {e}")
            return "", ""

    def select_best_image(self, image_urls):
        """Выбор лучшего изображения из списка"""
        if not image_urls:
            return ""
        
        # Предпочитаем изображения с определенными ключевыми словами в URL
        preferred_keywords = ['og:', 'twitter:', 'cover', 'featured', 'main', 'article', 'news']
        
        for url in image_urls:
            if any(keyword in url.lower() for keyword in preferred_keywords):
                return url
        
        # Иначе возвращаем первое изображение
        return image_urls[0]

    async def download_image(self, image_url):
        """Скачивание и сохранение изображения"""
        try:
            if not image_url:
                return None
                
            # Генерируем имя файла на основе URL
            filename = hashlib.md5(image_url.encode()).hexdigest() + '.jpg'
            filepath = os.path.join('downloaded_images', filename)
            
            # Проверяем, не скачано ли уже изображение
            if os.path.exists(filepath):
                logger.info(f"🖼️ Используем существующее изображение: {filename}")
                return filepath
            
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.ixbt.com/'
            }
            
            response = self.session.get(image_url, headers=headers, timeout=15, stream=True, verify=False)
            response.raise_for_status()
            
            # Сохраняем изображение
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ Изображение скачано: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания изображения {image_url}: {e}")
            return None

    async def create_news_image(self, title, image_path=None):
        """Создание изображения для новости с заголовком"""
        try:
            # Размеры изображения для Telegram
            width, height = 1200, 630
            
            # Создаем базовое изображение
            if image_path and os.path.exists(image_path):
                # Используем скачанное изображение как фон
                try:
                    background = Image.open(image_path)
                    background = background.resize((width, height), Image.Resampling.LANCZOS)
                except Exception as e:
                    logger.error(f"❌ Ошибка открытия фонового изображения: {e}")
                    background = Image.new('RGB', (width, height), color=(25, 25, 35))
            else:
                # Создаем градиентный фон
                background = Image.new('RGB', (width, height), color=(25, 25, 35))
            
            # Создаем полупрозрачный overlay для лучшей читаемости текста
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 180))
            background = background.convert('RGBA')
            background = Image.alpha_composite(background, overlay)
            
            draw = ImageDraw.Draw(background)
            
            # Загружаем шрифты
            try:
                title_font = ImageFont.truetype("arialbd.ttf", 48)
            except:
                try:
                    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                except:
                    title_font = ImageFont.load_default()
            
            # Разбиваем заголовок на строки
            words = title.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=title_font)
                text_width = bbox[2] - bbox[0]
                
                if text_width < width - 100:  # 100px padding
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Ограничиваем количество строк
            if len(lines) > 3:
                lines = lines[:3]
                lines[-1] = lines[-1][:97] + '...'
            
            # Рисуем заголовок
            total_text_height = len(lines) * 60
            y_position = (height - total_text_height) // 2
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                x_position = (width - text_width) // 2
                
                # Тень текста
                draw.text((x_position+2, y_position+2), line, font=title_font, fill=(0, 0, 0, 160))
                # Основной текст
                draw.text((x_position, y_position), line, font=title_font, fill=(255, 255, 255))
                
                y_position += 60
            
            # Сохраняем изображение
            output_path = os.path.join('images', f"news_{int(time.time())}.jpg")
            background.convert('RGB').save(output_path, 'JPEG', quality=85)
            
            logger.info(f"✅ Создано изображение новости: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания изображения новости: {e}")
            return None

    async def send_telegram_message(self, message, image_path=None):
        """Отправка сообщения в Telegram канал"""
        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo,
                        caption=message,
                        parse_mode='HTML'
                    )
                logger.info("✅ Новость отправлена с изображением")
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                logger.info("✅ Новость отправлена без изображения")
            return True
        except TelegramError as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            return False

    async def process_and_send_news(self):
        """Основной метод обработки и отправки новостей"""
        try:
            logger.info("🔄 Начинаем проверку новостей...")
            
            # Получаем новости
            news_list = await self.fetch_news()
            
            if not news_list:
                logger.info("📭 Новых новостей не найдено")
                return
            
            logger.info(f"📨 Найдено {len(news_list)} новых новостей")
            
            # Обрабатываем каждую новость
            for news_item in news_list:
                try:
                    # Форматируем сообщение
                    message = self.format_news_message(news_item)
                    
                    if not message:
                        logger.warning("❌ Сообщение не сформировано (возможно, заблокировано)")
                        continue
                    
                    # Скачиваем изображение
                    image_path = None
                    if news_item['image_url']:
                        image_path = await self.download_image(news_item['image_url'])
                    
                    # Если нет изображения из статьи, создаем свое
                    if not image_path:
                        logger.info("🎨 Создаем изображение с заголовком")
                        image_path = await self.create_news_image(news_item['title'])
                    
                    # Отправляем сообщение
                    success = await self.send_telegram_message(message, image_path)
                    
                    if success:
                        # Добавляем в обработанные
                        self.processed_news.add(news_item['hash'])
                        self.save_processed_news()
                        
                        logger.info(f"✅ Успешно отправлено: {news_item['title']}")
                        
                        # Задержка между отправками
                        await asyncio.sleep(10)
                    else:
                        logger.error(f"❌ Ошибка отправки новости: {news_item['title']}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки новости: {e}")
                    continue
            
            logger.info("✅ Проверка новостей завершена")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в process_and_send_news: {e}")

    async def run(self):
        """Основной цикл бота"""
        logger.info("🚀 Бот запущен!")
        
        while True:
            try:
                await self.process_and_send_news()
                logger.info(f"💤 Ожидание {CHECK_INTERVAL} секунд...")
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

async def main():
    """Основная функция"""
    bot = SmartNewsBot()
    await bot.run()

if __name__ == "__main__":
    # Проверяем наличие необходимых файлов
    required_files = ['banned_organizations.py', 'news_tags.py']
    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"❌ Отсутствует необходимый файл: {file}")
            sys.exit(1)
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
