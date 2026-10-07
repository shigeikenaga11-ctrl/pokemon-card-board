import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_FILE = "cards.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}

TRACK = {
    "137/103",  # リザードン
    "138/103",  # カスミ
    "135/103",  # ミュウex
    "163/103",  # ミュウVMAX
    "133/103",  # ボーマンダex
    "142/103",  # ルギア
    "165/103",  # コイキング
    "127/103",  # ピカチュウex
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


def search_price(number):

    # カード番号単独より
    # M6a全体ページの方が安定して取得できる
    keyword = urllib.parse.quote("M6a")

    url = (
        "https://www.cardrush-pokemon.jp/"
        "product-list/0/0/normal"
        f"?keyword={keyword}&num=100&order=desc"
    )

    html = download(url)

    # 改行などを整理
    text = re.sub(
        r"\s+",
        " ",
        html
    )

    # HTMLタグを簡易除去
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    # HTML entity
    text = (
        text
        .replace("&yen;", "円")
        .replace("&#165;", "円")
        .replace("&nbsp;", " ")
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    escaped = re.escape(number)

    # カード番号の位置を全部探す
    matches = list(
        re.finditer(
            escaped,
            text
        )
    )

    print(
        f"  number matches = {len(matches)}"
    )

    candidates = []

    for match in matches:

        start = max(
            0,
            match.start() - 250
        )

        end = min(
            len(text),
            match.end() + 350
        )

        block = text[start:end]

        # M6a以外を除外
        if "M6a" not in block:
            continue

        # カード番号より前の部分を確認
        before = text[
            max(0, match.start() - 180):
            match.start()
        ]

        # 状態品を除外
        if any(
            x in before
            for x in [
                "状態A",
                "状態Ｂ",
                "状態B",
                "状態Ｃ",
                "状態C"
            ]
        ):
            continue

        # カード番号より後ろから価格を探す
        after = text[
            match.end():
            min(
                len(text),
                match.end() + 300
            )
        ]

        price_match = re.search(
            r"([0-9]{1,3}(?:,[0-9]{3})*)\s*円",
            after
        )

        if not price_match:
            continue

        price = int(
            price_match
            .group(1)
            .replace(",", "")
        )

        candidates.append(price)

        print(
            f"  candidate = {price:,} yen"
        )

    if not candidates:
        return None

    # 最初の通常品を採用
    return candidates[0]


def update_card(card):

    number = card.get("number")

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
        f"  FOUND: {new_price:,} yen"
    )

    old_price = card.get(
        "currentPrice"
    )

    # 前回値を保存
    if old_price is not None:
        card[
            "yesterdayPrice"
        ] = old_price

    card[
        "currentPrice"
    ] = new_price

    # WANT
    if "referencePrice" in card:

        # 初回だけ固定
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

    # 履歴
    if "history" not in card:
        card["history"] = []

    now = datetime.now(
        ZoneInfo("Asia/Tokyo")
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    # 同日のデータは上書き
    card["history"] = [
        item
        for item in card["history"]
        if item.get("date") != today
    ]

    card["history"].append({
        "date": today,
        "price": new_price
    })

    # 365日保持
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
        update_card(card)

    for card in data.get(
        "wanted",
        []
    ):
        update_card(card)

    now = datetime.now(
        ZoneInfo("Asia/Tokyo")
    )

    data["lastUpdated"] = (
        now.strftime(
            "%Y-%m-%d %H:%M"
        )
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
