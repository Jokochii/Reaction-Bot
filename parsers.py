import re
import aiohttp
from datetime import datetime


async def fetch_store_metadata(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=5) as response:
                if response.status != 200: return None, None
                html = await response.text(errors='ignore')

                title_m = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html,
                                    re.I)
                img_m = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)

                title = title_m.group(1).split('–')[0].strip() if title_m else None
                image = img_m.group(1).strip() if img_m else None
                if image and image.startswith("//"): image = "https:" + image
                return title, image
    except Exception:
        return None, None


async def extract_readybot_data(message):
    embed_title, product_url, image_list = None, None, []
    raw_content = message.content or ""

    if message.embeds:
        for emb in message.embeds:
            if emb.url and "hopespace.moe" in emb.url:
                product_url = emb.url
                break
            raw_content += f"\n{emb.title or ''}\n{emb.description or ''}"

    snapshot = getattr(message, 'forward_snapshot', None) or getattr(message, 'snapshot', None)
    if snapshot and not product_url:
        raw_content += f"\n{getattr(snapshot, 'content', '') or ''}"
        snap_embeds = getattr(snapshot, 'embeds', None)
        if snap_embeds:
            for emb in snap_embeds:
                if emb.url and "hopespace.moe" in emb.url:
                    product_url = emb.url
                    break

    if not product_url:
        url_match = re.search(r'(https://hopespace\.moe/products/[^]\s?\n)]+)', raw_content)
        if url_match: product_url = url_match.group(1)

    item_title = "Unknown Item"
    if product_url:
        web_title, web_image = await fetch_store_metadata(product_url)
        if web_title: item_title = web_title
        if web_image:
            image_list.append(web_image)
            return item_title, product_url, None, image_list

    if message.attachments:
        for a in message.attachments:
            if a.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                if a.url not in image_list: image_list.append(a.url)

    if message.embeds:
        for emb in message.embeds:
            embed_title = emb.title or embed_title
            if emb.image and emb.image.url and emb.image.url not in image_list:
                image_list.append(emb.image.url)

    if item_title == "Unknown Item" and raw_content:
        brackets = re.findall(r'\[([^]\n]+)]', raw_content)
        for content in brackets:
            clean_content = content.strip()
            if clean_content.lower() in ['po', 'go', 'open', 'closed'] or re.search(
                    r'ends|closing|deadline|\d{1,2}[/-]\d{1,2}', clean_content, flags=re.IGNORECASE):
                continue
            extracted = re.sub(r'^(title|item|go):\s*', '', clean_content, flags=re.IGNORECASE).strip()
            item_title = f"{extracted} GO" if not extracted.lower().endswith("go") else extracted
            break

    if item_title == "Unknown Item" and raw_content:
        lines = [l.strip() for l in raw_content.split('\n') if l.strip()]
        if lines:
            first_line = lines[0]
            first_line = re.sub(r'\[(?:po|go|open|closed)]', '', first_line, flags=re.IGNORECASE)
            first_line = re.sub(r'\[(?:ends|closing|deadline)[^]]*]', '', first_line, flags=re.IGNORECASE)
            first_line = re.sub(r'<@&?\d+>|@\w+|https?://\S+', '', first_line).strip()

            if re.search(r'\bgo\b', first_line, flags=re.IGNORECASE):
                first_line = re.split(r'\bgo\b', first_line, maxsplit=1, flags=re.IGNORECASE)[0].strip()

            first_line = first_line.strip('[]- ,.').strip()
            if first_line:
                item_title = f"{first_line} GO" if not first_line.lower().endswith("go") else first_line

    if item_title == "Unknown Item" and embed_title: item_title = embed_title
    return item_title, product_url, None, image_list[:4]


def parse_date_from_text(text):
    if not text: return None
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11,
        'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6, 'july': 7, 'august': 8, 'september': 9,
        'october': 10, 'november': 11, 'december': 12
    }

    text_clean = text.lower().replace('[', ' ').replace(']', ' ')

    numeric_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})\b', text_clean)
    if numeric_match:
        val1, val2 = int(numeric_match.group(1)), int(numeric_match.group(2))
        day, month = (val2, val1) if val2 > 12 else (val1, val2)
        return format_to_valid_date(day, month)

    words = re.findall(r'\b\w+\b', text_clean)
    for idx, word in enumerate(words):
        if word in months_map:
            found_month, found_day = months_map[word], None

            if idx + 1 < len(words):
                m_next = re.match(r'^(\d{1,2})(?:st|nd|rd|th)?$', words[idx + 1])
                if m_next:
                    found_day = int(m_next.group(1))

            if idx - 1 >= 0 and not found_day:
                m_prev = re.match(r'^(\d{1,2})(?:st|nd|rd|th)?$', words[idx - 1])
                if m_prev:
                    found_day = int(m_prev.group(1))

            if found_day: return format_to_valid_date(found_day, found_month)
    return None


def format_to_valid_date(day, month):
    if month < 1 or month > 12 or day < 1 or day > 31: return None
    now = datetime.now()
    year = now.year
    try:
        target = datetime(year=year, month=month, day=day)
        if target < now: target = target.replace(year=year + 1)
        return target.strftime('%Y-%m-%d')
    except ValueError:
        return None
