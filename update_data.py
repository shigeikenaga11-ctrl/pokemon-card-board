import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

DATA_FILE = "cards.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/154 Safari/537.36"
    )
}

# まずは価格取得を試すカード
TRACK = {
    "137/103",  # リザードン
    "138/103",  # カスミ
    "135/103",  # ミュウex
    "163/103",  # ミュウVMAX
    "133/103",  # ボーマンダex
    "142/103",  # WANT ルギア
    "165/103",  # WANT コイキング
    "127/103",  # WANT ピカチュウex
}


def download(url):
    req = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def search_price(number):
    """
    カードラッシュでカード番号を検索。
    状態表記なしの商品を優先して価格を取得する。
    """

    keyword = urllib.parse.quote(number)

    url = (
        "https://www.cardrush-pokemon.jp/"
        "product-list/0/0/normal"
        f"?keyword={keyword}&num=100"
    )

    html = download(url)

    # HTMLを検索しやすくする
    text = re.sub(r"\s+", " ", html)

    # {137/103} のようなカード番号を含む商品付近を抽出
    escaped = re.escape(number)

    blocks = re.findall(
        rf".{{0,500}}\{{{escaped}\}}.{{0,700}}",
        text,
        flags=re.I
    )

    candidates = []

    for block in blocks:

        # 状態A-/B/C等は除外
        if re.search(r"状態\s*[A-ZＡ-Ｚ]", block):
            continue

        prices = re.findall(
            r"([0-9]{1,3}(?:,[0-9]{3})*)円",
            block
        )

        if not prices:
            continue

        price = int(prices[0].replace(",", ""))

        candidates.append(price)

    if not candidates:
        return None

    # 同一番号で複数候補がある場合は
    # 最初の通常商品価格を採用
    return candidates[0]


def update_card(card):

    number = card.get("number")

    if number not in TRACK:
        return

    print(
        f"Checking {card.get('name')} {number}..."
    )

    try:
        new_price = search_price(number)

    except Exception as e:
        print("ERROR:", e)
        return

    if new_price is None:
        print("  price not found")
        return

    old_price = card.get("currentPrice")

    # 昨日の値として直前価格を保存
    if old_price is not None:
        card["yesterdayPrice"] = old_price

    card["currentPrice"] = new_price

    # WANTカード
    # 初回だけ基準価格と狙い価格を固定
    if "referencePrice" in card:

        if card.get("referencePrice") is None:

            card["referencePrice"] = new_price

            card["targetPrice"] = round(
                new_price * 0.5
            )

    # 履歴
    if "history" not in card:
        card["history"] = []

    today = datetime.now().strftime("%Y-%m-%d")

    # 同じ日の重複を避ける
    card["history"] = [
        x for x in card["history"]
        if x.get("date") != today
    ]

    card["history"].append({
        "date": today,
        "price": new_price
    })

    # 365日だけ保持
    card["history"] = card["history"][-365:]

    print("  price =", new_price)


def main():

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    for card in data.get("owned", []):
        update_card(card)

    for card in data.get("wanted", []):
        update_card(card)

    data["lastUpdated"] = (
        datetime.now()
        .strftime("%Y-%m-%d %H:%M")
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

    print("DONE")


if __name__ == "__main__":
    main()
