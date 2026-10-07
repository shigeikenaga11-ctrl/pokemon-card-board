import json
import re
import urllib.parse
import urllib.request
import time

from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


# =========================================================
# 設定
# =========================================================

DATA_FILE = "cards.json"

SOURCE_NAME = "カードラッシュ"

BASE_URL = (
    "https://www.cardrush-pokemon.jp/"
    "product-list/0/0/normal"
)

SEARCH_KEYWORD = "M6a"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

JST = ZoneInfo("Asia/Tokyo")

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

# 暴走防止
MAX_PAGES = 20

# サイトへの連続アクセスを避ける
PAGE_WAIT = 1.0


# =========================================================
# 共通
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


def normalize_name(name):

    name = normalize(name)

    name = (
        name
        .replace(" ", "")
        .replace("　", "")
    )

    return name.lower()


def download(url):

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )


def extract_prices(text):

    text = normalize(text)

    matches = re.findall(
        r"([0-9]{1,3}(?:,[0-9]{3})*)\s*円",
        text
    )

    prices = []

    for value in matches:

        try:

            price = int(
                value.replace(
                    ",",
                    ""
                )
            )

            if (
                10
                <= price
                <= 10_000_000
            ):

                prices.append(
                    price
                )

        except ValueError:
            pass

    return prices


def is_condition_item(text):

    text = normalize(text)

    patterns = [
        r"状態\s*A",
        r"状態\s*Ａ",
        r"状態\s*B",
        r"状態\s*Ｂ",
        r"状態\s*C",
        r"状態\s*Ｃ"
    ]

    return any(
        re.search(
            pattern,
            text
        )
        for pattern
        in patterns
    )


# =========================================================
# 1ページの商品解析
# =========================================================

def parse_products(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    products = []

    seen = set()


    for link in soup.find_all(
        "a",
        href=True
    ):

        link_text = normalize(
            link.get_text(
                " ",
                strip=True
            )
        )


        # M6a商品のみ
        if (
            SEARCH_KEYWORD.lower()
            not in
            link_text.lower()
        ):
            continue


        # 000/000
        number_match = re.search(
            r"(\d{3}/\d{3})",
            link_text
        )

        if not number_match:
            continue


        number = (
            number_match.group(1)
        )


        # ---------------------------------------------
        # 商品を囲む親要素から価格取得
        # ---------------------------------------------

        parent = link

        product_text = None

        prices = []


        for _ in range(7):

            if parent is None:
                break


            text = normalize(
                parent.get_text(
                    " ",
                    strip=True
                )
            )


            found_prices = (
                extract_prices(
                    text
                )
            )


            if found_prices:

                product_text = text

                prices = (
                    found_prices
                )

                break


            parent = parent.parent


        if not product_text:
            continue


        # 状態品は除外
        if is_condition_item(
            product_text
        ):
            continue


        # ---------------------------------------------
        # 商品名
        # ---------------------------------------------

        name_part = link_text


        # [M6a] 等削除
        name_part = re.sub(
            r"\[?M6a\]?",
            "",
            name_part,
            flags=re.I
        )


        # {137/103} 等削除
        name_part = re.sub(
            r"[\{\[\(]?"
            + re.escape(number)
            + r"[\}\]\)]?",
            "",
            name_part
        )


        name_part = normalize(
            name_part
        )


        # 最初の価格
        price = prices[0]


        href = link.get(
            "href",
            ""
        )


        # 商品URLが同じなら重複
        key = (
            href,
            number,
            price
        )


        if key in seen:
            continue


        seen.add(
            key
        )


        products.append({

            "name":
                name_part,

            "number":
                number,

            "price":
                price,

            "text":
                product_text,

            "href":
                href
        })


    return products


# =========================================================
# 全ページ取得
# =========================================================

def build_product_list():

    print()
    print(
        "Downloading Cardrush "
        "all pages..."
    )


    all_products = []

    seen_products = set()

    previous_page_signature = None


    for page in range(
        1,
        MAX_PAGES + 1
    ):

        query = urllib.parse.urlencode({

            "keyword":
                SEARCH_KEYWORD,

            "num":
                100,

            "order":
                "desc",

            "page":
                page
        })


        url = (
            BASE_URL
            + "?"
            + query
        )


        print()
        print(
            f"PAGE {page}"
        )


        try:

            html = download(
                url
            )

        except Exception as error:

            print(
                "  DOWNLOAD ERROR:",
                repr(error)
            )

            break


        print(
            f"  downloaded: "
            f"{len(html):,} bytes"
        )


        page_products = (
            parse_products(
                html
            )
        )


        print(
            f"  parsed: "
            f"{len(page_products)}"
        )


        # ---------------------------------------------
        # 商品ゼロなら終了
        # ---------------------------------------------

        if not page_products:

            print(
                "  no products -> stop"
            )

            break


        # ---------------------------------------------
        # 同じページを返され続けた場合の対策
        # ---------------------------------------------

        signature = tuple(
            sorted(
                (
                    p["href"],
                    p["number"],
                    p["price"]
                )
                for p
                in page_products
            )
        )


        if (
            previous_page_signature
            is not None
            and
            signature
            == previous_page_signature
        ):

            print(
                "  same page repeated "
                "-> stop"
            )

            break


        previous_page_signature = (
            signature
        )


        # ---------------------------------------------
        # 全商品へ追加
        # ---------------------------------------------

        new_count = 0


        for product in page_products:

            key = (
                product["href"],
                product["number"],
                product["price"]
            )


            if key in seen_products:
                continue


            seen_products.add(
                key
            )


            all_products.append(
                product
            )


            new_count += 1


        print(
            f"  new products: "
            f"{new_count}"
        )


        print(
            f"  total: "
            f"{len(all_products)}"
        )


        # 新商品がゼロなら終了
        if new_count == 0:

            print(
                "  no new products "
                "-> stop"
            )

            break


        time.sleep(
            PAGE_WAIT
        )


    print()
    print(
        "================================"
    )

    print(
        f"TOTAL NORMAL PRODUCTS: "
        f"{len(all_products)}"
    )

    print(
        "================================"
    )


    return all_products


# =========================================================
# カード照合
# =========================================================

def find_card_price(
    card,
    products
):

    name = normalize_name(
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


    candidates = []


    for product in products:

        # カード番号完全一致
        if (
            product["number"]
            != number
        ):
            continue


        product_name = (
            normalize_name(
                product["name"]
            )
        )


        product_text = (
            normalize_name(
                product["text"]
            )
        )


        # 名前一致
        if (
            name not in product_name
            and
            name not in product_text
        ):
            continue


        candidates.append(
            product
        )


    if not candidates:

        return None


    # =====================================================
    # 一致度スコア
    # =====================================================

    def score(product):

        product_name = (
            normalize_name(
                product["name"]
            )
        )

        product_text = (
            normalize_name(
                product["text"]
            )
        )

        value = 0


        # 名前完全一致
        if product_name == name:

            value += 200


        # 名前から始まる
        if product_name.startswith(
            name
        ):

            value += 100


        # 名前を含む
        if name in product_name:

            value += 50


        # 本文に名前
        if name in product_text:

            value += 10


        # 状態品なら除外相当
        if is_condition_item(
            product["text"]
        ):

            value -= 10000


        return value


    candidates.sort(
        key=score,
        reverse=True
    )


    best = candidates[0]


    print(
        f"    match: "
        f"{best['name']} "
        f"{best['number']} "
        f"¥{best['price']:,}"
    )


    # 候補が複数ならログだけ表示
    if len(candidates) > 1:

        print(
            f"    candidates: "
            f"{len(candidates)}"
        )


    return best["price"]


# =========================================================
# 履歴処理
# =========================================================

def get_previous_price(
    history,
    today
):

    if not isinstance(
        history,
        list
    ):

        return None


    previous = []


    for item in history:

        date = item.get(
            "date"
        )

        price = item.get(
            "price"
        )


        if not date:
            continue


        if price is None:
            continue


        # 今日より前だけ
        if date < today:

            previous.append(
                item
            )


    if not previous:

        return None


    previous.sort(
        key=lambda item:
        item.get(
            "date",
            ""
        )
    )


    return previous[-1].get(
        "price"
    )


def update_history(
    card,
    price,
    today
):

    history = card.get(
        "history"
    )


    if not isinstance(
        history,
        list
    ):

        history = []


    # 今日の記録だけ削除
    history = [

        item

        for item
        in history

        if item.get(
            "date"
        ) != today
    ]


    # 今日の価格を追加
    history.append({

        "date":
            today,

        "price":
            price
    })


    # 日付順
    history.sort(
        key=lambda item:
        item.get(
            "date",
            ""
        )
    )


    # 最大365日
    card["history"] = (
        history[-365:]
    )


# =========================================================
# カード更新
# =========================================================

def update_card(
    card,
    products,
    today,
    is_wanted=False
):

    name = card.get(
        "name",
        ""
    )

    number = card.get(
        "number",
        ""
    )


    print()
    print(
        f"Checking "
        f"{name} "
        f"{number}"
    )


    # エネルギーはスキップ
    if number in ENERGY_NUMBERS:

        print(
            "    SKIP: energy"
        )

        return "skip"


    price = find_card_price(
        card,
        products
    )


    if price is None:

        print(
            "    NOT FOUND"
        )

        return "fail"


    # =====================================================
    # 本当の前日以前の最新価格
    # =====================================================

    history = card.get(
        "history",
        []
    )


    previous_price = (
        get_previous_price(
            history,
            today
        )
    )


    card[
        "yesterdayPrice"
    ] = previous_price


    # =====================================================
    # 現在価格
    # =====================================================

    card[
        "currentPrice"
    ] = price


    card[
        "priceSource"
    ] = SOURCE_NAME


    # =====================================================
    # WANT
    # =====================================================

    if is_wanted:

        # 初回だけ固定
        if card.get(
            "referencePrice"
        ) is None:

            card[
                "referencePrice"
            ] = price


        # 目標価格も初回だけ固定
        if card.get(
            "targetPrice"
        ) is None:

            reference = (
                card.get(
                    "referencePrice"
                )
            )


            if reference is not None:

                card[
                    "targetPrice"
                ] = round(
                    reference * 0.5
                )


    # =====================================================
    # 履歴更新
    # =====================================================

    update_history(
        card,
        price,
        today
    )


    # =====================================================
    # ログ
    # =====================================================

    print(
        f"    CURRENT: "
        f"¥{price:,}"
    )


    if previous_price is None:

        print(
            "    PREVIOUS: —"
        )

    else:

        difference = (
            price
            - previous_price
        )


        percentage = (

            (
                price
                / previous_price
                - 1
            )
            * 100

            if previous_price
            else 0
        )


        print(
            f"    PREVIOUS: "
            f"¥{previous_price:,}"
        )


        print(
            f"    CHANGE: "
            f"{difference:+,} "
            f"({percentage:+.1f}%)"
        )


    if is_wanted:

        print(
            f"    REFERENCE: "
            f"{card.get('referencePrice')}"
        )

        print(
            f"    TARGET: "
            f"{card.get('targetPrice')}"
        )


    return "success"


# =========================================================
# MAIN
# =========================================================

def main():

    now = datetime.now(
        JST
    )


    today = now.strftime(
        "%Y-%m-%d"
    )


    print(
        "================================"
    )

    print(
        "Pokemon Card Price Updater"
    )

    print(
        now.strftime(
            "%Y-%m-%d %H:%M JST"
        )
    )

    print(
        "================================"
    )


    # =====================================================
    # JSONロード
    # =====================================================

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )


    # =====================================================
    # カードラッシュ全ページ
    # =====================================================

    products = (
        build_product_list()
    )


    if not products:

        raise RuntimeError(
            "No Cardrush products parsed."
        )


    # =====================================================
    # 更新
    # =====================================================

    success = 0

    failed = 0

    skipped = 0


    # -----------------------------------------------------
    # 保有カード
    # -----------------------------------------------------

    for card in data.get(
        "owned",
        []
    ):

        result = update_card(

            card,

            products,

            today,

            is_wanted=False
        )


        if result == "success":

            success += 1

        elif result == "fail":

            failed += 1

        else:

            skipped += 1


    # -----------------------------------------------------
    # WANT
    # -----------------------------------------------------

    for card in data.get(
        "wanted",
        []
    ):

        result = update_card(

            card,

            products,

            today,

            is_wanted=True
        )


        if result == "success":

            success += 1

        elif result == "fail":

            failed += 1

        else:

            skipped += 1


    # =====================================================
    # メタ情報
    # =====================================================

    data[
        "lastUpdated"
    ] = now.strftime(
        "%Y-%m-%d %H:%M"
    )


    data[
        "priceSource"
    ] = SOURCE_NAME


    data[
        "updateStats"
    ] = {

        "success":
            success,

        "failed":
            failed,

        "skipped":
            skipped,

        "productsParsed":
            len(products)
    }


    # =====================================================
    # JSON保存
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


    # =====================================================
    # 最終結果
    # =====================================================

    print()
    print(
        "================================"
    )

    print(
        "UPDATE COMPLETE"
    )

    print(
        f"PRODUCTS: "
        f"{len(products)}"
    )

    print(
        f"SUCCESS : "
        f"{success}"
    )

    print(
        f"FAILED  : "
        f"{failed}"
    )

    print(
        f"SKIPPED : "
        f"{skipped}"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
