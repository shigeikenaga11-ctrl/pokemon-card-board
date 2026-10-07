import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


# =========================================================
# SETTINGS
# =========================================================

DATA_FILE = "cards.json"

IMAGE_DIR = Path("images")

SEARCH_URL = (
    "https://www.pokemon-card.com/card-search/index.php"
)

OFFICIAL_BASE = (
    "https://www.pokemon-card.com"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language":
        "ja,en-US;q=0.9,en;q=0.8"
}

ENERGY_NUMBERS = {
    "水",
    "炎",
    "草",
    "雷",
    "鋼",
    "超",
    "闘",
    "悪"
}

WAIT = 0.7


# =========================================================
# BASIC
# =========================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace(
        "\u3000",
        " "
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def normalize_name(text):

    return (
        normalize(text)
        .replace(" ", "")
        .replace("　", "")
        .lower()
    )


def request_bytes(url):

    req = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        req,
        timeout=30
    ) as response:

        return response.read()


def request_text(url):

    return request_bytes(
        url
    ).decode(
        "utf-8",
        errors="ignore"
    )


# =========================================================
# FILE NAME
# =========================================================

def image_filename(card):

    number = normalize(
        card.get(
            "number",
            ""
        )
    )

    number = (
        number
        .replace("/", "_")
        .replace("\\", "_")
    )

    return (
        f"M6a_{number}.jpg"
    )


# =========================================================
# SEARCH OFFICIAL SITE
# =========================================================

def search_card(card):

    name = normalize(
        card.get(
            "name",
            ""
        )
    )

    number = normalize(
        card.get(
            "number",
            ""
        )
    )


    if not name:
        return None


    if not number:
        return None


    if number in ENERGY_NUMBERS:
        return None


    print()
    print(
        f"SEARCH "
        f"{name} "
        f"{number}"
    )


    # =====================================================
    # 公式検索
    #
    # card-search は keyword にカード名を渡す
    # =====================================================

    query = urllib.parse.urlencode({
        "keyword": name,
        "regulation_sidebar_form":
            "all"
    })


    url = (
        SEARCH_URL
        + "?"
        + query
    )


    try:

        html = request_text(
            url
        )

    except Exception as error:

        print(
            "  SEARCH ERROR:",
            repr(error)
        )

        return None


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    candidates = []


    # =====================================================
    # details.php/card/xxxxx
    # を収集
    # =====================================================

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href",
            ""
        )


        if (
            "details.php/card/"
            not in href
        ):
            continue


        text = normalize(
            link.get_text(
                " ",
                strip=True
            )
        )


        if href.startswith(
            "http"
        ):

            detail_url = href

        else:

            detail_url = (
                urllib.parse.urljoin(
                    OFFICIAL_BASE,
                    href
                )
            )


        candidates.append({
            "url":
                detail_url,

            "text":
                text
        })


    # URL重複除去

    unique = []

    seen = set()


    for item in candidates:

        if item["url"] in seen:
            continue

        seen.add(
            item["url"]
        )

        unique.append(
            item
        )


    candidates = unique


    print(
        f"  candidates: "
        f"{len(candidates)}"
    )


    # =====================================================
    # 各候補ページを確認
    # =====================================================

    for candidate in candidates:

        try:

            detail_html = (
                request_text(
                    candidate["url"]
                )
            )

        except Exception:

            continue


        detail_soup = BeautifulSoup(
            detail_html,
            "html.parser"
        )


        page_text = normalize(
            detail_soup.get_text(
                " ",
                strip=True
            )
        )


        # ---------------------------------------------
        # M6a + カード番号の両方を要求
        # ---------------------------------------------

        set_match = re.search(
            r"\bM6a\b",
            page_text,
            re.I
        )


        number_pattern = (
            re.escape(
                number.split("/")[0]
            )
            +
            r"\s*/\s*"
            +
            re.escape(
                number.split("/")[1]
            )
        )


        number_match = re.search(
            number_pattern,
            page_text
        )


        if not set_match:
            continue


        if not number_match:
            continue


        # ---------------------------------------------
        # カード名も確認
        # ---------------------------------------------

        title = ""

        h1 = detail_soup.find(
            "h1"
        )


        if h1:

            title = normalize(
                h1.get_text(
                    " ",
                    strip=True
                )
            )


        if (
            normalize_name(name)
            not in
            normalize_name(
                title + " " + page_text[:500]
            )
        ):

            continue


        print(
            "  MATCH:",
            candidate["url"]
        )


        return {
            "url":
                candidate["url"],

            "html":
                detail_html,

            "soup":
                detail_soup
        }


    print(
        "  NOT FOUND"
    )

    return None


# =========================================================
# FIND IMAGE
# =========================================================

def find_card_image(
    soup,
    number
):

    candidates = []


    for img in soup.find_all(
        "img"
    ):

        src = (
            img.get("src")
            or
            img.get("data-src")
            or
            img.get("data-original")
            or
            ""
        )


        if not src:
            continue


        alt = normalize(
            img.get(
                "alt",
                ""
            )
        )


        width = normalize(
            img.get(
                "width",
                ""
            )
        )


        height = normalize(
            img.get(
                "height",
                ""
            )
        )


        src_lower = (
            src.lower()
        )


        score = 0


        # ポケカ公式カード画像でよく使われる語
        if "card" in src_lower:
            score += 20


        if "card_images" in src_lower:
            score += 100


        if "card-image" in src_lower:
            score += 100


        if "images/card" in src_lower:
            score += 50


        # ロゴ等を避ける
        bad_words = [
            "logo",
            "icon",
            "header",
            "footer",
            "banner",
            "btn",
            "button",
            "sns"
        ]


        if any(
            word in src_lower
            for word in bad_words
        ):

            score -= 100


        candidates.append({
            "src":
                src,

            "alt":
                alt,

            "width":
                width,

            "height":
                height,

            "score":
                score
        })


    if not candidates:

        return None


    candidates.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )


    # 上位候補をログ表示

    for item in candidates[:5]:

        print(
            "    IMG CANDIDATE",
            item["score"],
            item["src"][:120]
        )


    best = candidates[0]


    if best["score"] < 0:

        return None


    return urllib.parse.urljoin(
        OFFICIAL_BASE,
        best["src"]
    )


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def save_image(
    image_url,
    path
):

    try:

        raw = request_bytes(
            image_url
        )


        if len(raw) < 5000:

            print(
                "  IMAGE TOO SMALL:",
                len(raw)
            )

            return False


        # ---------------------------------------------
        # JPG/PNG/WebP判定
        # ---------------------------------------------

        extension = ".jpg"


        if raw.startswith(
            b"\x89PNG"
        ):

            extension = ".png"


        elif raw.startswith(
            b"RIFF"
        ) and b"WEBP" in raw[:20]:

            extension = ".webp"


        actual_path = (
            path.with_suffix(
                extension
            )
        )


        actual_path.write_bytes(
            raw
        )


        print(
            f"  SAVED: "
            f"{actual_path} "
            f"({len(raw):,} bytes)"
        )


        return actual_path


    except Exception as error:

        print(
            "  IMAGE ERROR:",
            repr(error)
        )

        return False


# =========================================================
# UPDATE ONE CARD
# =========================================================

def update_card_image(
    card
):

    number = normalize(
        card.get(
            "number",
            ""
        )
    )


    if number in ENERGY_NUMBERS:

        print()
        print(
            f"SKIP ENERGY "
            f"{card.get('name')} "
            f"{number}"
        )

        return "skip"


    # =====================================================
    # 既存ローカル画像があればそのまま
    # =====================================================

    current_image = normalize(
        card.get(
            "image",
            ""
        )
    )


    if current_image.startswith(
        "images/"
    ):

        existing = Path(
            current_image
        )


        if existing.exists():

            print()
            print(
                f"EXISTS "
                f"{card.get('name')} "
                f"{number}"
            )

            return "exists"


    # =====================================================
    # 公式カード検索
    # =====================================================

    result = search_card(
        card
    )


    if result is None:

        return "fail"


    # =====================================================
    # 画像URL取得
    # =====================================================

    image_url = find_card_image(
        result["soup"],
        number
    )


    if not image_url:

        print(
            "  IMAGE NOT FOUND"
        )

        return "fail"


    print(
        "  IMAGE:",
        image_url
    )


    # =====================================================
    # 保存
    # =====================================================

    filename = image_filename(
        card
    )


    path = (
        IMAGE_DIR
        /
        filename
    )


    actual_path = save_image(
        image_url,
        path
    )


    if not actual_path:

        return "fail"


    # =====================================================
    # cards.json に相対パス保存
    # =====================================================

    card["image"] = (
        actual_path
        .as_posix()
    )


    card[
        "imageSource"
    ] = (
        "ポケモンカードゲーム公式"
    )


    card[
        "officialCardUrl"
    ] = (
        result["url"]
    )


    return "success"


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "================================"
    )

    print(
        "Pokemon Card Image Updater"
    )

    print(
        "OFFICIAL POKEMON CARD SITE"
    )

    print(
        "================================"
    )


    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )


    success = 0

    failed = 0

    skipped = 0

    existing = 0


    # =====================================================
    # 同じカード番号の画像を再利用するためのキャッシュ
    # =====================================================

    processed = {}


    all_groups = [

        (
            "OWNED",
            data.get(
                "owned",
                []
            )
        ),

        (
            "WANTED",
            data.get(
                "wanted",
                []
            )
        )

    ]


    for group_name, cards in all_groups:

        print()
        print(
            "================================"
        )

        print(
            group_name
        )

        print(
            "================================"
        )


        for card in cards:

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


            cache_key = (
                normalize_name(name),
                number
            )


            # -----------------------------------------
            # 同じカードが既に処理済み
            # -----------------------------------------

            if cache_key in processed:

                cached = (
                    processed[
                        cache_key
                    ]
                )


                if cached:

                    card["image"] = (
                        cached.get(
                            "image",
                            ""
                        )
                    )

                    card[
                        "imageSource"
                    ] = (
                        cached.get(
                            "imageSource",
                            ""
                        )
                    )

                    card[
                        "officialCardUrl"
                    ] = (
                        cached.get(
                            "officialCardUrl",
                            ""
                        )
                    )


                continue


            result = (
                update_card_image(
                    card
                )
            )


            if result == "success":

                success += 1


            elif result == "exists":

                existing += 1


            elif result == "skip":

                skipped += 1


            else:

                failed += 1


            processed[
                cache_key
            ] = {

                "image":
                    card.get(
                        "image",
                        ""
                    ),

                "imageSource":
                    card.get(
                        "imageSource",
                        ""
                    ),

                "officialCardUrl":
                    card.get(
                        "officialCardUrl",
                        ""
                    )

            }


            # 公式サイトに負荷をかけない
            time.sleep(
                WAIT
            )


    # =====================================================
    # SAVE JSON
    # =====================================================

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


    print()
    print(
        "================================"
    )

    print(
        "IMAGE UPDATE COMPLETE"
    )

    print(
        f"SUCCESS  : {success}"
    )

    print(
        f"EXISTING : {existing}"
    )

    print(
        f"FAILED   : {failed}"
    )

    print(
        f"SKIPPED  : {skipped}"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
