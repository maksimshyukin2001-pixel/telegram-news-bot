import asyncio
import logging
import hashlib
import json
import os
import re
import random
import requests
import time
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
import news_tags

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Конфигурация
if 'RAILWAY_ENVIRONMENT' in os.environ or 'RAILWAY_STATIC_URL' in os.environ:
    TOKEN = os.environ.get('TELEGRAM_TOKEN', "7445394461:AAGHiGYBiCwEg-tbchU9lOJmywv4CjcKuls")
    CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL', "@techno_met")
else:
    TOKEN = "7445394461:AAGHiGYBiCwEg-tbchU9lOJmywv4CjcKuls"
    CHANNEL_ID = "@techno_met"

IXBT_RSS_URL = "https://www.ixbt.com/export/news.rss"
CHECK_INTERVAL = 1800

# Создание директорий
Path("images").mkdir(exist_ok=True)
Path("downloaded_images").mkdir(exist_ok=True)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)

class SmartNewsBot:
    def __init__(self):
        self.processed_news = set()
        self.load_processed_news()
        self.bot = Bot(token=TOKEN)
        self.ua = UserAgent()
        self.session = self.create_advanced_session()
        
    def create_advanced_session(self):
        session = requests.Session()
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
        try:
            if os.path.exists('processed_news.json'):
                with open('processed_news.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_news = set(data)
        except Exception as e:
            logger.error(f"Error loading processed news: {e}")
            self.processed_news = set()

    def save_processed_news(self):
        try:
            with open('processed_news.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_news), f)
        except Exception as e:
            logger.error(f"Error saving processed news: {e}")

    def get_news_hash(self, title, link):
        return hashlib.md5(f"{title}{link}".encode()).hexdigest()

    def check_banned_organizations(self, title, text):
        try:
            import banned_organizations
            content = f"{title} {text}".lower()
            found_organizations = []
            
            for org in banned_organizations.BANNED_ORGANIZATIONS:
                if org.lower() in content:
                    found_organizations.append(org)
            
            for keyword in banned_organizations.BANNED_KEYWORDS:
                if keyword in content:
                    start = max(0, content.find(keyword) - 50)
                    end = min(len(content), content.find(keyword) + len(keyword) + 50)
                    context = content[start:end]
                    words = context.split()
                    if len(words) > 2:
                        potential_org = ' '.join(words[:min(5, len(words))])
                        found_organizations.append(f"контекст: {potential_org}...")
            
            return found_organizations
        except ImportError:
            logger.warning("Модуль banned_organizations не найден")
            return []
        except Exception as e:
            logger.error(f"Ошибка проверки организаций: {e}")
            return []

    def detect_news_category(self, title, text):
        title_lower = title.lower()
        text_lower = text.lower()
        full_text = f"{title_lower} {text_lower}"
        
        category_scores = {}
        
        for category_name, category_data in news_tags.CATEGORIES.items():
            score = 0
            keywords = category_data['keywords']
            
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, title_lower):
                    score += 5
                elif re.search(pattern, full_text):
                    score += 2
            
            if 'exclude' in category_data:
                for exclude_word in category_data['exclude']:
                    if exclude_word in full_text:
                        score = max(0, score - 3)
            
            category_scores[category_name] = score
        
        top_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        found_categories = [cat for cat, score in top_categories if score > 3][:3]
        
        if not found_categories:
            found_categories = [cat for cat, score in top_categories if score > 1][:2]
        
        if not found_categories:
            found_categories = ['technology', 'news']
        else:
            found_categories.extend(['technology', 'news'])
        
        logger.info(f"Определены категории: {found_categories}")
        return found_categories

    def get_hashtags_for_category(self, categories):
        return news_tags.get_all_hashtags(categories)

    async def fetch_news(self):
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
                        logger.info(f"Загружена новость: {entry.title}")
                    else:
                        logger.warning(f"Слишком короткий текст: {len(full_text)} символов")
            
            return news_list
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []

    async def get_full_article_text_and_image(self, url):
        try:
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for element in soup.find_all(['script', 'style']):
                element.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            images = []
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://www.ixbt.com' + src
                    
                    if src.startswith('http'):
                        images.append(src)
            
            best_image = self.select_best_image(images) if images else ""
            
            return cleaned_text, best_image
            
        except Exception as e:
            logger.error(f"Ошибка получения контента: {e}")
            return "", ""

    def select_best_image(self, images):
        if not images:
            return ""
        
        scored_images = []
        
        for img_url in images:
            score = 0
            
            if 'ixbt.com' in img_url:
                score += 10
            
            content_folders = ['content', 'article', 'post', 'news', 'images', 'img']
            for folder in content_folders:
                if f'/{folder}/' in img_url:
                    score += 5
            
            size_indicators = ['large', 'big', 'main', 'hero', 'cover', 'full']
            for indicator in size_indicators:
                if indicator in img_url.lower():
                    score += 3
            
            small_indicators = ['thumb', 'small', 'icon', 'mini']
            for indicator in small_indicators:
                if indicator in img_url.lower():
                    score -= 5
            
            logo_indicators = ['logo', 'icon', 'avatar']
            for indicator in logo_indicators:
                if indicator in img_url.lower():
                    score -= 10
            
            scored_images.append((img_url, score))
        
        scored_images.sort(key=lambda x: x[1], reverse=True)
        best_image = scored_images[0][0] if scored_images else ""
        
        return best_image

    async def download_image(self, image_url):
        try:
            if not image_url:
                return None
                
            headers = {
                'User-Agent': self.ua.random,
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.ixbt.com/'
            }
            
            response = self.session.get(image_url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return None
            
            image_data = response.content
            image_path = f"downloaded_images/{hashlib.md5(image_url.encode()).hexdigest()}.jpg"
            
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            return image_path
            
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения: {e}")
            return None

    def create_news_image(self, title):
        try:
            width, height = 1200, 630
            img = Image.new('RGB', (width, height), color=(25, 25, 35))
            draw = ImageDraw.Draw(img)
            
            try:
                title_font = ImageFont.truetype("arialbd.ttf", 48)
            except:
                title_font = ImageFont.load_default()
            
            words = title.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) < 60:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            lines = lines[:3]
            
            for i, line in enumerate(lines):
                text_width = draw.textlength(line, font=title_font)
                x = (width - text_width) // 2
                y = 200 + i * 70
                draw.text((x, y), line, font=title_font, fill=(255, 255, 255))
            
            output_path = f"images/news_{int(time.time())}.jpg"
            img.save(output_path, 'JPEG', quality=85)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка создания изображения: {e}")
            return None

    async def send_news_to_channel(self, news_item):
        try:
            banned_orgs = self.check_banned_organizations(news_item['title'], news_item['full_text'])
            if banned_orgs:
                logger.warning(f"Новость содержит запрещенные организации: {banned_orgs}")
                return False

            categories = self.detect_news_category(news_item['title'], news_item['full_text'])
            hashtags = self.get_hashtags_for_category(categories)
            
            article_image_path = None
            if news_item['image_url']:
                article_image_path = await self.download_image(news_item['image_url'])
            
            final_image_path = self.create_news_image(news_item['title'])
            
            message_text = f"📰 {news_item['title']}\n\n"
            
            sentences = re.split(r'[.!?]+', news_item['full_text'])
            meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
            
            if meaningful_sentences:
                preview_text = '. '.join(meaningful_sentences[:2]) + '.'
                if len(preview_text) > 400:
                    preview_text = preview_text[:397] + '...'
                message_text += f"{preview_text}\n\n"
            
            message_text += f"🔗 Читать подробнее: {news_item['link']}\n\n"
            message_text += ' '.join(hashtags)
            
            if final_image_path and os.path.exists(final_image_path):
                with open(final_image_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo,
                        caption=message_text,
                        parse_mode='HTML'
                    )
                logger.info(f"Новость отправлена: {news_item['title']}")
            else:
                await self.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message_text,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
                logger.info(f"Новость отправлена без изображения: {news_item['title']}")
            
            self.processed_news.add(news_item['hash'])
            self.save_processed_news()
            
            try:
                if article_image_path and os.path.exists(article_image_path):
                    os.remove(article_image_path)
                if final_image_path and os.path.exists(final_image_path):
                    os.remove(final_image_path)
            except Exception as e:
                logger.warning(f"Ошибка очистки файлов: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки новости: {e}")
            return False

    async def run(self):
        logger.info("Бот запущен и начал мониторинг новостей...")
        
        while True:
            try:
                logger.info("Проверяем новые новости...")
                news_list = await self.fetch_news()
                
                if news_list:
                    logger.info(f"Найдено {len(news_list)} новых новостей")
                    
                    for news_item in news_list:
                        success = await self.send_news_to_channel(news_item)
                        
                        if success:
                            delay = random.uniform(10, 30)
                            await asyncio.sleep(delay)
                else:
                    logger.info("Новых новостей не найдено")
                
                logger.info(f"Ожидание {CHECK_INTERVAL} секунд...")
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                await asyncio.sleep(60)

async def main():
    bot = SmartNewsBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
