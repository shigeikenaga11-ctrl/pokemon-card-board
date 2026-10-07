import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


DATA_FILE = "cards.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}


TRACK = {
    "137/103",
    "138/103",
    "135/103",
    "163/103",
    "133/103",
    "142/103",
    "165/103",
    "127/103",
}


def download(url):

    req = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        req,
        timeout=30
    ) as r:

        return r.read().decode(
            "utf-8",
            errors="ignore"
        )


def normalize(text):

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def extract_price(text):

    # 「19,800円」等
    matches = re.findall(
        r"([0-9]{1,3}(?:,[0-9]{3})*)\s*円",
        text
    )

    if not matches:
        return None

    prices = []

    for p in matches:

        try:
            value = int(
                p.replace(",", "")
            )

            # 明らかに価格ではない数字を除外
            if 10 <= value <= 10000000:
                prices.append(value)

        except:
            pass

    if not prices:
        return None

    return prices[0]


def search_price(number):

    keyword = urllib.parse.quote("M6a")

    url = (
        "https://www.cardrush-pokemon.jp/"
        "product-list/0/0/normal"
        f"?keyword={keyword}"
        "&num=100"
        "&order=desc"
    )

    html = download(url)

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    candidates = []


    # -------------------------
    # 商品リンクを探す
    # -------------------------

    for link in soup.find_all(
        "a",
        href=True
    ):

        text = normalize(
            link.get_text(
                " ",
                strip=True
            )
        )

        if number not in text:
            continue


        # M6a以外は除外
        if "M6a" not in text:
            continue


        print(
            "  PRODUCT:",
            text[:150]
        )


        # 状態品除外
        if re.search(
            r"状態\s*[A-CＡ-Ｃ]",
            text
        ):
            print(
                "    -> condition item skip"
            )
            continue


        # -------------------------
        # link自身から価格
        # -------------------------

        price = extract_price(
            text
        )


        # -------------------------
        # 親要素から価格
        # -------------------------

        if price is None:

            parent = link.parent

            depth = 0

            while (
                parent is not None
                and depth < 6
            ):

                parent_text = normalize(
                    parent.get_text(
                        " ",
                        strip=True
                    )
                )

                price = extract_price(
                    parent_text
                )

                if price is not None:

                    print(
                        "    parent price:",
                        price
                    )

                    break

                parent = parent.parent

                depth += 1


        if price is not None:

            candidates.append(
                price
            )

            print(
                f"    CANDIDATE: "
                f"{price:,} yen"
            )


    # -------------------------
    # fallback
    # -------------------------

    if not candidates:

        print(
            "  product-link method failed"
        )

        # 番号を含む文字列ノードを直接探す

        strings = soup.find_all(
            string=re.compile(
                re.escape(number)
            )
        )

        print(
            "  text matches:",
            len(strings)
        )

        for node in strings:

            parent = node.parent

            for depth in range(8):

                if parent is None:
                    break

                block = normalize(
                    parent.get_text(
                        " ",
                        strip=True
                    )
                )

                # 番号確認
                if number not in block:
                    parent = parent.parent
                    continue

                # M6a確認
                if "M6a" not in block:
                    parent = parent.parent
                    continue

                # 状態品除外
                if re.search(
                    r"状態\s*[A-CＡ-Ｃ]",
                    block
                ):
                    parent = parent.parent
                    continue

                price = extract_price(
                    block
                )

                if price is not None:

                    print(
                        "  FALLBACK:",
                        block[:160]
                    )

                    print(
                        f"  FALLBACK PRICE: "
                        f"{price:,} yen"
                    )

                    candidates.append(
                        price
                    )

                    break

                parent = parent.parent


    if not candidates:
        return None


    # 重複削除
    candidates = list(
        dict.fromkeys(
            candidates
        )
    )


    print(
        "  candidates:",
        candidates
    )


    # 通常品候補の先頭
    return candidates[0]


def update_card(card):

    number = card.get(
        "number"
    )

    if number not in TRACK:
        return


    print(
        f"\nChecking "
        f"{card.get('name')} "
        f"{number}..."
    )


    try:

        new_price = search_price(
            number
        )

    except Exception as e:

        print(
            "  ERROR:",
            repr(e)
        )

        return


    if new_price is None:

        print(
            "  PRICE NOT FOUND"
        )

        return


    print(
        f"  FOUND: "
        f"{new_price:,} yen"
    )


    old_price = card.get(
        "currentPrice"
    )


    # 前回取得価格
    if old_price is not None:

        card[
            "yesterdayPrice"
        ] = old_price


    card[
        "currentPrice"
    ] = new_price


    # -------------------------
    # WANT
    # -------------------------

    if "referencePrice" in card:

        # 初回取得時のみ固定
        if card.get(
            "referencePrice"
        ) is None:

            card[
                "referencePrice"
            ] = new_price

            card[
                "targetPrice"
            ] = round(
                new_price * 0.5
            )


    # -------------------------
    # HISTORY
    # -------------------------

    if "history" not in card:

        card[
            "history"
        ] = []


    now = datetime.now(
        ZoneInfo(
            "Asia/Tokyo"
        )
    )

    today = now.strftime(
        "%Y-%m-%d"
    )


    # 同日は最新価格へ更新
    card["history"] = [

        item

        for item
        in card["history"]

        if item.get(
            "date"
        ) != today
    ]


    card["history"].append({

        "date":
            today,

        "price":
            new_price
    })


    # 1年間保持
    card["history"] = (
        card["history"][-365:]
    )


def main():

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)


    print(
        "=== Pokemon Card "
        "Price Update ==="
    )


    for card in data.get(
        "owned",
        []
    ):

        update_card(
            card
        )


    for card in data.get(
        "wanted",
        []
    ):

        update_card(
            card
        )


    now = datetime.now(
        ZoneInfo(
            "Asia/Tokyo"
        )
    )


    data[
        "lastUpdated"
    ] = now.strftime(
        "%Y-%m-%d %H:%M"
    )


    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


    print(
        "\n=== DONE ==="
    )


if __name__ == "__main__":
    main()
