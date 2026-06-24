# -*- coding: utf-8 -*-
"""
Извлечение фото товара по ссылке Dewu (得物) / dw4.co.
Пробуем несколько способов подряд, чтобы быть устойчивее к защите.
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

# Паттерны для поиска картинки в HTML/JSON ответа.
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)
# Прямые ссылки на CDN-картинки Dewu/Poizon (jpg/png/webp).
CDN_IMG_RE = re.compile(
    r'(https?:\\?/\\?/[^"\'\\\s]*(?:poizon|dewu|alicdn|deepoon)[^"\'\\\s]*\.(?:jpg|jpeg|png|webp)[^"\'\\\s]*)',
    re.IGNORECASE,
)


def find_dewu_url(text: str) -> str | None:
    """Вернуть первую ссылку Dewu из текста сообщения, либо None."""
    if not text:
        return None
    m = DEWU_URL_RE.search(text)
    return m.group(0) if m else None


def _clean_url(url: str) -> str:
    # В JSON слэши часто экранированы как \/ — чистим.
    return url.replace("\\/", "/").replace("\\u002F", "/").strip()


async def get_dewu_image(url: str) -> str | None:
    """
    По ссылке Dewu вернуть URL фото товара, либо None если не удалось.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            async with session.get(url, allow_redirects=True) as resp:
                final_url = str(resp.url)
                logger.info(f"Dewu: запрос {url} -> {final_url} [{resp.status}]")
                if resp.status != 200:
                    return None
                html = await resp.text(errors="ignore")
    except Exception as e:
        logger.error(f"Dewu: ошибка загрузки страницы: {e}")
        return None

    # 1) og:image — самый надёжный, если есть.
    for rx in (OG_IMAGE_RE, OG_IMAGE_RE2):
        m = rx.search(html)
        if m:
            img = _clean_url(m.group(1))
            logger.info(f"Dewu: нашёл og:image -> {img}")
            return img

    # 2) Любая CDN-картинка в теле страницы / встроенном JSON.
    m = CDN_IMG_RE.search(html)
    if m:
        img = _clean_url(m.group(1))
        logger.info(f"Dewu: нашёл CDN-картинку -> {img}")
        return img

    logger.warning("Dewu: картинка не найдена в ответе страницы")
    return None
