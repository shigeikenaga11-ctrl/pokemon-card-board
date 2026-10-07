from pathlib import Path
import re

src = Path("/mnt/data/貼り付けたテキスト（1）(6).txt")
text = src.read_text(encoding="utf-8")

# 1) imports / settings
text = text.replace(
    "import time\n\nfrom datetime import datetime",
    "import time\nfrom pathlib import Path\n\nfrom datetime import datetime"
)

text = text.replace(
    'DATA_FILE = "cards.json"',
    'DATA_FILE = "cards.json"\nIMAGE_DIR = Path("images")'
)

# 2) Add binary download + image helpers before extract_prices
marker = "\ndef extract_prices(text):"
helpers = r'''
def download_bytes(url, referer=None):

    headers = dict(HEADERS)

    if referer:
        headers["Referer"] = referer

    request = urllib.request.Request(
        url,
        headers=headers
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return (
            response.read(),
            response.headers.get(
                "Content-Type",
                ""
            )
        )


def absolute_url(url, base_url=BASE_URL):

    return urllib.parse.urljoin(
        base_url,
        url
    )


def safe_filename(text):

    text = normalize(text)

    text = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        text
    )

    text = re.sub(
        r"\s+",
        "_",
        text
    )

    return text.strip("._")


def image_basename(card):

    number = normalize(
        card.get(
            "number",
            ""
        )
    )

    name = normalize(
        card.get(
            "name",
            ""
        )
    )

    number_part = safe_filename(
        number.replace(
            "/",
            "-"
        )
    )

    name_part = safe_filename(
        name
    )

    if number_part and name_part:
        return f"{number_part}_{name_part}"

    return (
        number_part
        or name_part
        or "card"
    )


def existing_image_path(card):

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    base = image_basename(
        card
    )

    for extension in (
        ".webp",
        ".jpg",
        ".jpeg",
        ".png"
    ):

        path = (
            IMAGE_DIR
            / f"{base}{extension}"
        )

        if path.exists():
            return path

    return None


def find_product_image_url(product):

    product_url = absolute_url(
        product.get(
            "href",
            ""
        )
    )

    if not product_url:
        return None

    try:

        html = download(
            product_url
        )

    except Exception as error:

        print(
            "    IMAGE PAGE ERROR:",
            repr(error)
        )

        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    candidates = []

    # 商品ページでよく使われるメイン画像候補を優先
    selectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        "img"
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            url = (
                element.get("content")
                or element.get("data-src")
                or element.get("data-original")
                or element.get("src")
                or ""
            )

            url = normalize(
                url
            )

            if not url:
                continue

            full_url = absolute_url(
                url,
                product_url
            )

            lowered = (
                full_url.lower()
            )

            if not any(
                extension in lowered
                for extension in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                )
            ):
                continue

            candidates.append(
                full_url
            )

    if not candidates:
        return None

    # og:image / twitter:image が先に入るので原則先頭を採用
    return candidates[0]


def extension_from_content_type(
    content_type,
    image_url
):

    content_type = (
        content_type
        .split(";")[0]
        .strip()
        .lower()
    )

    mapping = {
        "image/webp": ".webp",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png"
    }

    if content_type in mapping:
        return mapping[
            content_type
        ]

    path = urllib.parse.urlparse(
        image_url
    ).path.lower()

    for extension in (
        ".webp",
        ".jpg",
        ".jpeg",
        ".png"
    ):

        if path.endswith(
            extension
        ):

            if extension == ".jpeg":
                return ".jpg"

            return extension

    return ".jpg"


def save_card_image(
    card,
    product
):

    current = existing_image_path(
        card
    )

    if current is not None:

        card["image"] = (
            current
            .as_posix()
        )

        print(
            f"    IMAGE EXISTS: "
            f"{current}"
        )

        return True

    image_url = find_product_image_url(
        product
    )

    if not image_url:

        print(
            "    IMAGE NOT FOUND"
        )

        return False

    product_url = absolute_url(
        product.get(
            "href",
            ""
        )
    )

    try:

        image_bytes, content_type = (
            download_bytes(
                image_url,
                referer=product_url
            )
        )

    except Exception as error:

        print(
            "    IMAGE DOWNLOAD ERROR:",
            repr(error)
        )

        return False

    if not image_bytes:

        print(
            "    IMAGE EMPTY"
        )

        return False

    extension = (
        extension_from_content_type(
            content_type,
            image_url
        )
    )

    path = (
        IMAGE_DIR
        / (
            image_basename(
                card
            )
            + extension
        )
    )

    path.write_bytes(
        image_bytes
    )

    card["image"] = (
        path.as_posix()
    )

    print(
        f"    IMAGE SAVED: "
        f"{path}"
    )

    return True

'''
text = text.replace(marker, "\n" + helpers + marker, 1)

# 3) find_card_price returns best product instead of just price
text = text.replace(
    '    return best["price"]\n\n\n# =========================================================\n# 履歴処理',
    '    return best\n\n\n# =========================================================\n# 履歴処理'
)

# 4) update_card: receive product, derive price, save image
old = '''    price = find_card_price(
        card,
        products
    )


    if price is None:

        print(
            "    NOT FOUND"
        )

        return "fail"
'''
new = '''    product = find_card_price(
        card,
        products
    )


    if product is None:

        print(
            "    NOT FOUND"
        )

        return "fail"


    price = product["price"]


    # =====================================================
    # カード画像
    # =====================================================

    try:

        save_card_image(
            card,
            product
        )

    except Exception as error:

        # 画像取得失敗で価格更新まで止めない
        print(
            "    IMAGE ERROR:",
            repr(error)
        )
'''
if old not in text:
    raise RuntimeError("update_card target block not found")
text = text.replace(old, new, 1)

# 5) Ensure image directory exists in main
needle = '''    print(
        "================================"
    )


    # =====================================================
    # JSONロード
'''
replacement = '''    print(
        "================================"
    )


    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # =====================================================
    # JSONロード
'''
if needle not in text:
    raise RuntimeError("main insertion target not found")
text = text.replace(needle, replacement, 1)

out = Path("/mnt/data/update_data.py")
out.write_text(text, encoding="utf-8")

# Basic syntax check
compile(text, str(out), "exec")

print(f"作成完了: {out}")
print(f"行数: {len(text.splitlines())}")
