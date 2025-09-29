# Категории и хештеги для новостей
CATEGORIES = {
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
        'exclude': ['игра', 'игровой', 'gaming'],
        'hashtags': ['ИИ', 'ИскусственныйИнтеллект', 'Нейросети', 'AI', 'МашинноеОбучение']
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
        'hashtags': ['Космос', 'SpaceX', 'NASA', 'Астрономия', 'Космонавтика']
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
        'hashtags': ['Гаджеты', 'Техника', 'Электроника', 'Устройства', 'Смартфоны']
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
        'hashtags': ['Телевизоры', 'ТВ', 'Дисплеи', '4K', 'OLED']
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
        'hashtags': ['Авто', 'Автомобили', 'Транспорт', 'Электромобили', 'Tesla']
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
        'hashtags': ['Игры', 'Гейминг', 'ИгровыеНовости', 'Киберспорт', 'PlayStation']
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
        'hashtags': ['Наука', 'Исследования', 'Открытия', 'Технологии', 'Инновации']
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
        'hashtags': ['Интернет', 'Онлайн', 'Соцсети', 'Цифровизация', 'Технологии']
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
        'hashtags': ['Софт', 'Программы', 'Приложения', 'Разработка', 'IT']
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
        'hashtags': ['Железо', 'Компьютеры', 'Комплектующие', 'Апгрейд', 'Техника']
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
        'hashtags': ['Безопасность', 'Кибербезопасность', 'ЗащитаДанных', 'Антивирус', 'Privacy']
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
        'hashtags': ['Бизнес', 'Стартапы', 'Инновации', 'Технобизнес', 'Инвестиции']
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
        'hashtags': ['Криптовалюта', 'Блокчейн', 'NFT', 'Биткоин', 'Web3']
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
        'hashtags': ['Здоровье', 'Медицина', 'Биотехнологии', 'ЗОЖ', 'Фитнес']
    }
}

# Общие теги для всех новостей
GENERAL_HASHTAGS = ['Технологии', 'IT', 'Инновации', 'ТехноНовости', 'Новости']

def get_category_hashtags(category_name):
    """Получить хештеги для конкретной категории"""
    if category_name in CATEGORIES:
        return CATEGORIES[category_name]['hashtags']
    return []

def get_all_hashtags(categories):
    """Получить все хештеги для списка категорий"""
    hashtags = []
    used_hashtags = set()
    
    for category in categories:
        if category in CATEGORIES:
            for hashtag in CATEGORIES[category]['hashtags']:
                hashtag_with_hash = f"#{hashtag}"
                if hashtag_with_hash not in used_hashtags:
                    hashtags.append(hashtag_with_hash)
                    used_hashtags.add(hashtag_with_hash)
    
    # Добавляем общие теги
    for hashtag in GENERAL_HASHTAGS:
        hashtag_with_hash = f"#{hashtag}"
        if hashtag_with_hash not in used_hashtags:
            hashtags.append(hashtag_with_hash)
            used_hashtags.add(hashtag_with_hash)
    
    # Ограничиваем количество хештегов
    return hashtags[:8]