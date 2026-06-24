# -*- coding: utf-8 -*-
"""
Извлечение фото товара по ссылке Dewu (得物) / dw4.co.
Возвращаем несколько ракурсов товара, отбрасывая служебные иконки.
"""
import re
import logging
import aiohttp

logger = logging.getLogger(__name__)

# Реалистичные заголовки, имитируем мобильный браузер / WeChat-превью,
# т.к. именно для превью Dewu обычно отдаёт og:image в HTML.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1 "
        "MicroMessenger/8.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Находим ссылку Dewu/dw4 внутри произвольного текста сообщения.
DEWU_URL_RE = re.compile(r"https?://[^\s]*(?:dw4\.co|dewu\.com|poizon)[^\s]*", re.IGNORECASE)

# Прямые ссылки на CDN-картинки Dewu/Poizon (jpg/png/webp).
CDN_IMG_RE = re.compile(
    r'(https?:\\?/\\?/[^"\'\\\s]*(?:poizon|dewu|alicdn|deepoon)[^"\'\\\s]*\.(?:jpg|jpeg|png|webp)[^"\'\\\s]*)',
    re.IGNORECASE,
)

# Признаки служебных иконок интерфейса, а НЕ фото товара — такие отбрасываем.
JUNK_MARKERS = ("node-common", "/icon", "logo", "avatar", "placeholder", "default")
# Мелкие размеры в имени файла вида -66-66, -48-48 и т.п. (иконки).
SMALL_SIZE_RE = re.compile(r"-(\d{1,3})-(\d{1,3})\.(?:png|jpg|jpeg|webp)", re.IGNORECASE)


def _is_product_image(url: str) -> bool:
    """Отсеять служебные иконки; оставить только похожее на фото товара."""
    low = url.lower()
    if any(mark in low for mark in JUNK_MARKERS):
        return False
    m = SMALL_SIZE_RE.search(low)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w < 200 or h < 200:  # маленькая иконка
            return False
    return True


def find_dewu_url(text: str) -> str | None:
    """Вернуть первую ссылку Dewu из текста сообщения, либо None."""
    if not text:
        return None
    m = DEWU_URL_RE.search(text)
    return m.group(0) if m else None


def _clean_url(url: str) -> str:
    # В JSON слэши часто экранированы как \/ — чистим.
    return url.replace("\\/", "/").replace("\\u002F", "/").strip()


def _base_key(url: str) -> str:
    """Ключ для дедупликации: путь до '?' (одно фото в разных размерах = один товар)."""
    return url.split("?", 1)[0]


async def get_dewu_images(url: str, limit: int = 6) -> list[str]:
    """
    По ссылке Dewu вернуть список URL фото товара (разные ракурсы), до limit штук.
    Пустой список — если ничего не нашли.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            async with session.get(url, allow_redirects=True) as resp:
                final_url = str(resp.url)
                logger.info(f"Dewu: запрос {url} -> {final_url} [{resp.status}]")
                if resp.status != 200:
                    return []
                html = await resp.text(errors="ignore")
    except Exception as e:
        logger.error(f"Dewu: ошибка загрузки страницы: {e}")
        return []

    # Собираем все CDN-картинки в порядке появления.
    all_imgs = [_clean_url(u) for u in CDN_IMG_RE.findall(html)]

    # Оставляем только фото товара, убираем дубли по базовому пути.
    result = []
    seen_keys = set()
    for u in all_imgs:
        if not _is_product_image(u):
            continue
        key = _base_key(u)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        result.append(u)
        if len(result) >= limit:
            break

    logger.info(f"Dewu: фото товара отобрано: {len(result)} (из {len(all_imgs)} всего)")
    return result


async def get_dewu_image(url: str) -> str | None:
    """Совместимость: вернуть одно (первое) фото товара, либо None."""
    imgs = await get_dewu_images(url, limit=1)
    return imgs[0] if imgs else None
