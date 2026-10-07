import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


# =========================================================
# 設定
# =========================================================

DATA_FILE = "cards.json"

SOURCE_NAME = "カードラッシュ"

SOURCE_URL = (
    "https://www.cardrush-pokemon.jp/"
    "product-list/0/0/normal"
    "?keyword=M6a"
    "&num=100"
    "&order=desc"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
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

JST = ZoneInfo("Asia/Tokyo")


# =========================================================
# 共通処理
# =========================================================

def normalize(text):
    """
    空白・改行を整理
    """

    if text is None:
        return ""

    text = str(text)

    text = text.replace("\u3000", " ")

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def normalize_name(name):
    """
    商品名比較用
    """

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
    """
    「19,800円」などを価格として抽出
    """

    text = normalize(text)

    matches = re.findall(
        r"([0-9]{1,3}(?:,[0-9]{3})*)\s*円",
        text
    )

    result = []

    for value in matches:

        try:

            price = int(
                value.replace(",", "")
            )

            if 10 <= price <= 10_000_000:

                result.append(
                    price
                )

        except ValueError:
            pass

    return result


def is_condition_item(text):
    """
    状態A- / 状態B / 状態C等を除外
    """

    text = normalize(text)

    patterns = [
        r"状態\s*A",
        r"状態\s*Ａ",
        r"状態\s*B",
        r"状態\s*Ｂ",
        r"状態\s*C",
        r"状態\s*Ｃ",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# =========================================================
# カードラッシュの商品一覧を取得
# =========================================================

def build_product_list():

    print()
    print(
        "Downloading Cardrush..."
    )

    html = download(
        SOURCE_URL
    )

    print(
        f"Downloaded: "
        f"{len(html):,} bytes"
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    products = []

    seen = set()


    # -----------------------------------------------------
    # 商品リンクを起点に取得
    # -----------------------------------------------------

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

        if "M6a" not in link_text:
            continue

        # 000/000形式を探す
        number_match = re.search(
            r"(\d{3}/\d{3})",
            link_text
        )

        if not number_match:
            continue

        number = number_match.group(1)


        # ---------------------------------------------
        # 親要素から商品全体を探す
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
                extract_prices(text)
            )

            if found_prices:

                product_text = text
                prices = found_prices

                break

            parent = parent.parent


        if not product_text:
            continue


        # 状態品除外
        if is_condition_item(
            product_text
        ):
            continue


        # ---------------------------------------------
        # 名前部分を取得
        # ---------------------------------------------

        name_part = link_text

        # [M6a]などを削除
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

        # レアリティ記号などは残しても
        # 後で部分一致するので問題なし

        name_part = normalize(
            name_part
        )


        price = prices[0]


        key = (
            name_part,
            number,
            price
        )

        if key in seen:
            continue

        seen.add(key)


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
                link.get("href", "")
        })


    print(
        f"Normal products parsed: "
        f"{len(products)}"
    )

    return products


# =========================================================
# カードを商品一覧から検索
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

        if (
            product["number"]
            != number
        ):
            continue


        product_name = normalize_name(
            product["name"]
        )

        product_text = normalize_name(
            product["text"]
        )


        # 名前一致
        #
        # 例：
        # ミュウex
        # ミュウex(SAR)
        #
        # のようなケースに対応

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


    # -----------------------------------------------------
    # より名前が近い商品を優先
    # -----------------------------------------------------

    def score(product):

        product_name = (
            normalize_name(
                product["name"]
            )
        )

        result = 0


        if product_name == name:

            result += 100


        if product_name.startswith(
            name
        ):

            result += 50


        if name in product_name:

            result += 20


        # 状態表記が万一残っていたら大幅減点

        if is_condition_item(
            product["text"]
        ):

            result -= 1000


        return result


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


    return best["price"]


# =========================================================
# 履歴更新
# =========================================================

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


    # 同じ日のデータを削除
    history = [

        item

        for item in history

        if item.get(
            "date"
        ) != today
    ]


    history.append({

        "date":
            today,

        "price":
            price
    })


    # 日付順
    history.sort(
        key=lambda x:
        x.get(
            "date",
            ""
        )
    )


    # 最大365日
    card["history"] = (
        history[-365:]
    )


# =========================================================
# 1カード更新
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


    # エネルギー
    if number in ENERGY_NUMBERS:

        print(
            "    SKIP: energy"
        )

        return False


    price = find_card_price(
        card,
        products
    )


    if price is None:

        print(
            "    NOT FOUND"
        )

        return False


    old_price = card.get(
        "currentPrice"
    )


    # -----------------------------------------------------
    # 前日価格
    # -----------------------------------------------------

    history = card.get(
        "history",
        []
    )


    yesterday_price = None


    # 今日以外の最新履歴を探す

    previous = [

        item

        for item in history

        if (
            item.get("date")
            and
            item.get("date") != today
        )
    ]


    if previous:

        previous.sort(
            key=lambda x:
            x.get(
                "date",
                ""
            )
        )

        yesterday_price = (
            previous[-1]
            .get(
                "price"
            )
        )


    # 過去履歴がない場合だけ
    # 既存currentPriceを使用

    elif old_price is not None:

        yesterday_price = (
            old_price
        )


    card[
        "yesterdayPrice"
    ] = yesterday_price


    card[
        "currentPrice"
    ] = price


    card[
        "priceSource"
    ] = SOURCE_NAME


    # -----------------------------------------------------
    # WANT
    # -----------------------------------------------------

    if is_wanted:

        # 初回のみ基準価格固定

        if card.get(
            "referencePrice"
        ) is None:

            card[
                "referencePrice"
            ] = price


        # targetPriceも初回だけ固定

        if card.get(
            "targetPrice"
        ) is None:

            reference = card.get(
                "referencePrice"
            )

            if reference is not None:

                card[
                    "targetPrice"
                ] = round(
                    reference * 0.5
                )


    # -----------------------------------------------------
    # 履歴
    # -----------------------------------------------------

    update_history(
        card,
        price,
        today
    )


    print(
        f"    CURRENT: "
        f"¥{price:,}"
    )


    if (
        yesterday_price
        is not None
    ):

        difference = (
            price
            - yesterday_price
        )

        print(
            f"    CHANGE: "
            f"{difference:+,}"
        )


    if is_wanted:

        print(
            f"    TARGET: "
            f"{card.get('targetPrice')}"
        )


    return True


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


    # -----------------------------------------------------
    # cards.json
    # -----------------------------------------------------

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )


    # -----------------------------------------------------
    # カードラッシュ
    # 一度だけ取得
    # -----------------------------------------------------

    try:

        products = (
            build_product_list()
        )

    except Exception as error:

        print()
        print(
            "DOWNLOAD ERROR:"
        )

        print(
            repr(error)
        )

        raise


    if not products:

        raise RuntimeError(
            "No products parsed. "
            "Cardrush HTML may have changed."
        )


    # -----------------------------------------------------
    # 更新
    # -----------------------------------------------------

    success = 0

    failed = 0

    skipped = 0


    # 保有
    for card in data.get(
        "owned",
        []
    ):

        if (
            card.get("number")
            in ENERGY_NUMBERS
        ):

            skipped += 1

            continue


        result = update_card(

            card,

            products,

            today,

            is_wanted=False
        )


        if result:

            success += 1

        else:

            failed += 1


    # WANT
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


        if result:

            success += 1

        else:

            failed += 1


    # -----------------------------------------------------
    # メタデータ
    # -----------------------------------------------------

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
            skipped
    }


    # -----------------------------------------------------
    # 保存
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # 結果
    # -----------------------------------------------------

    print()
    print(
        "================================"
    )

    print(
        "UPDATE COMPLETE"
    )

    print(
        f"SUCCESS : {success}"
    )

    print(
        f"FAILED  : {failed}"
    )

    print(
        f"SKIPPED : {skipped}"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
