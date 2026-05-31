import feedparser
import anthropic
import requests
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")

RSS_FEEDS = [
    "https://popkiller.pl/rss.xml",
    "https://newonce.net/feed",
    "https://www.cgm.pl/feed/",
    "https://hiphopdx.com/rss",
    "https://allhiphop.com/feed",
    "https://xxlmag.com/feed/"
]

POSTED_FILE = "posted.json"


# =========================
# STORAGE
# =========================

def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []


def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# VIRAL INTELLIGENCE
# =========================

PL_ARTISTS = [
    "mata", "bedoes", "kizo", "oki", "malik", "gibbs",
    "taco", "que", "quebonafide", "szpaku", "guzior",
    "white 2115", "2115", "kabe", "paluch", "pezet"
]

VIRAL_WORDS = [
    "beef", "diss", "konflikt", "skandal", "drama",
    "album", "singiel", "drop", "premiera", "wywiad"
]

BAD_TOPICS = [
    "football", "nba", "crypto", "stock", "weather", "politics"
]


def score_article(title):
    t = title.lower()
    score = 0

    # 🔥 PL rap boost
    for a in PL_ARTISTS:
        if a in t:
            score += 6

    # 🔥 viral words
    for w in VIRAL_WORDS:
        if w in t:
            score += 3

    # 🔥 big names extra boost
    if any(x in t for x in ["mata", "bedoes", "kizo", "oki", "malik"]):
        score += 8

    # ❌ unwanted topics
    for b in BAD_TOPICS:
        if b in t:
            score -= 20

    # 💬 engagement boost
    if any(x in t for x in ["ujawnia", "odpowiada", "atak", "skandal", "beef"]):
        score += 4

    return score


def engagement_score(title):
    t = title.lower()
    score = 0

    triggers = [
        "beef", "diss", "konflikt", "skandal", "drama",
        "ujawnia", "odpowiada", "atak", "rozpad", "powrót"
    ]

    stars = ["mata", "bedoes", "kizo", "oki", "malik", "taco"]

    for x in triggers:
        if x in t:
            score += 3

    for s in stars:
        if s in t:
            score += 5

    return score


def extract_key(title):
    return title.lower()


# =========================
# RSS + TREND DETECTOR
# =========================

def get_new_articles():
    posted = load_posted()
    articles = []
    trend_counter = {}

    raw = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:10]:
                if e.link in posted:
                    continue

                key = extract_key(e.title)

                trend_counter[key] = trend_counter.get(key, 0) + 1

                raw.append({
                    "title": e.title,
                    "link": e.link,
                    "key": key
                })

        except Exception as e:
            print("RSS error:", e)

    final = []

    for a in raw:
        score = score_article(a["title"])

        score += engagement_score(a["title"])

        # 🔥 TREND BOOST
        if trend_counter[a["key"]] >= 2:
            score += 8

        if score >= 7:
            a["score"] = score
            final.append(a)

    final.sort(key=lambda x: x["score"], reverse=True)

    return final


# =========================
# AI (SZOP WYJAŚNIA)
# =========================

def generate_post(title):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    t = title.lower()

    is_drama = any(x in t for x in ["beef", "diss", "konflikt", "skandal", "drama"])

    if is_drama:
        style = """
Jesteś „Szop Wyjaśnia” w trybie DRAMA.
Analizujesz konflikty sceny rapowej.
Jesteś pewny siebie, lekko ironiczny, bardziej ostry.
"""
    else:
        style = """
Jesteś „Szop Wyjaśnia”.
Komentujesz polską scenę rapową spokojnie, naturalnie, jak człowiek.
"""

    prompt = (
        style +
        "\nZasady:\n"
        "- max 3 zdania\n"
        "- naturalny język (jak człowiek)\n"
        "- 2–3 emoji (🦝 💸 👑 🎧 🔥 😳)\n"
        "- ZERO linków\n"
        "- ZERO hashtagów\n"
        "- nie wymyślaj faktów\n\n"
        f"News: {title}"
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    text = response.content[0].text

    # 🔥 safety net (blokada linków)
    text = text.replace("http://", "").replace("https://", "")

    return text


# =========================
# FACEBOOK POST
# =========================

def post_fb(message):
    try:
        r = requests.post(
            f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/feed",
            data={
                "message": message,
                "access_token": FB_PAGE_TOKEN
            }
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# =========================
# MAIN
# =========================

def main():
    print("Start Szop Bot")

    articles = get_new_articles()
    posted = load_posted()

    if not articles:
        print("Brak viral newsów")
        return

    for a in articles[:3]:
        print("Processing:", a["title"], "score:", a.get("score", 0))

        try:
            post = generate_post(a["title"])
            print("POST:", post)

            res = post_fb(post)
            print("FB:", res)

            posted.append(a["link"])
            save_posted(posted)

            time.sleep(5)

        except Exception as e:
            print("Error:", e)

    print("Done")


if __name__ == "__main__":
    main()