import os
import json
import requests
import textwrap
import cloudinary
import cloudinary.uploader
import feedparser
import re
import random
import time
import traceback

from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from openai import OpenAI

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# =====================================================
# LOGGER
# =====================================================

def log(message):

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{current_time}] {message}")

# =====================================================
# OPENAI
# =====================================================

client = OpenAI(api_key=OPENAI_API_KEY)

# =====================================================
# CLOUDINARY
# =====================================================

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# =====================================================
# CLEAN TITLE
# =====================================================

def clean_title(title):

    title = title.lower()

    title = re.sub(r'[^a-zA-Z0-9 ]', '', title)

    title = re.sub(r'\s+', ' ', title)

    return title.strip()

# =====================================================
# FILTER BAD / OLD NEWS
# =====================================================

def is_valid_news(title):

    title_lower = title.lower()

    blocked_keywords = [

        "death",
        "dies",
        "dead",
        "killed",
        "murder",
        "suicide",
        "accident",
        "crash",
        "funeral",
        "obituary",
        "rape",
        "assault",
        "body found",
        "terror",
        "attack",
        "violence",
        "fire death",
        "shot dead",
        "hospital death",
        "custody death",
        "earthquake deaths",
        "flood deaths",
        "old",
        "archive",
        "throwback",
        "anniversary",
        "remembering",
        "historic"
    ]

    for keyword in blocked_keywords:

        if keyword in title_lower:

            log(f"🚫 Blocked News: {title}")

            return False

    old_years = [
        "2020",
        "2021",
        "2022",
        "2023",
        "2024"
    ]

    for year in old_years:

        if year in title_lower:

            log(f"🚫 Old News Skipped: {title}")

            return False

    return True

# =====================================================
# FETCH NEWS
# =====================================================

def fetch_news():

    log("🌍 Fetching Jaipur News")

    articles = []

    # =================================================
    # GNEWS
    # =================================================

    try:

        log("📰 Fetching GNews")

        gnews_url = (
            f"https://gnews.io/api/v4/search?"
            f'q=Jaipur'
            f"&lang=en"
            f"&max=25"
            f"&apikey={GNEWS_API_KEY}"
        )

        response = requests.get(
            gnews_url,
            timeout=30
        )

        data = response.json()

        for article in data.get("articles", []):

            articles.append({
                "title": article["title"],
                "description": article.get("description", "")
            })

        log(f"✅ GNews Articles: {len(data.get('articles', []))}")

    except Exception as e:

        log(f"❌ GNews Error: {e}")

    # =================================================
    # NEWS API
    # =================================================

    try:

        if NEWS_API_KEY:

            log("📰 Fetching NewsAPI")

            newsapi_url = (
                f"https://newsapi.org/v2/everything?"
                f'q=Jaipur'
                f"&language=en"
                f"&pageSize=25"
                f"&sortBy=publishedAt"
                f"&apiKey={NEWS_API_KEY}"
            )

            response = requests.get(
                newsapi_url,
                timeout=30
            )

            data = response.json()

            for article in data.get("articles", []):

                articles.append({
                    "title": article["title"],
                    "description": article.get("description", "")
                })

            log(f"✅ NewsAPI Articles: {len(data.get('articles', []))}")

    except Exception as e:

        log(f"❌ NewsAPI Error: {e}")

    # =================================================
    # GOOGLE RSS
    # =================================================

    try:

        log("📰 Fetching Google RSS")

        rss_url = (
            "https://news.google.com/rss/search?"
            "q=Jaipur+metro+traffic+business+events+tourism+government+startup+viral+weather+sports&hl=en-IN&gl=IN&ceid=IN:en"
        )

        feed = feedparser.parse(rss_url)

        for entry in feed.entries[:25]:

            articles.append({
                "title": entry.title,
                "description": getattr(entry, "summary", "")
            })

        log(f"✅ Google RSS Articles: {len(feed.entries[:25])}")

    except Exception as e:

        log(f"❌ Google RSS Error: {e}")

    # =================================================
    # DAINIK BHASKAR RSS
    # =================================================

    try:

        log("📰 Fetching Dainik Bhaskar RSS")

        bhaskar_rss = (
            "https://www.bhaskar.com/rss-v1--category-1998.xml"
        )

        feed = feedparser.parse(bhaskar_rss)

        for entry in feed.entries[:25]:

            articles.append({
                "title": entry.title,
                "description": getattr(entry, "summary", "")
            })

        log(f"✅ Bhaskar RSS Articles: {len(feed.entries[:25])}")

    except Exception as e:

        log(f"❌ Bhaskar RSS Error: {e}")

    # =================================================
    # REMOVE DUPLICATES
    # =================================================

    log("🧹 Removing Duplicate News")

    unique_articles = []

    seen_titles = set()

    for article in articles:

        cleaned = clean_title(article["title"])

        if len(cleaned) < 20:
            continue

        duplicate = False

        for seen in seen_titles:

            if cleaned[:55] == seen[:55]:

                duplicate = True
                break

        if not duplicate:

            seen_titles.add(cleaned)

            unique_articles.append(article)

    log(f"✅ Unique Articles: {len(unique_articles)}")

    random.shuffle(unique_articles)

    # =================================================
    # FIND VALID NEWS
    # =================================================

    for article in unique_articles:

        if (
            is_valid_news(article["title"])
            and not already_posted(article["title"])
        ):

            log(f"📰 Selected News: {article['title']}")

            return article

    log("⚠ No New Unique News Found")

    return None

# =====================================================
# AI CONTENT GENERATION
# =====================================================

def generate_content(news):

    try:

        log("🤖 Generating Professional Jaipur Content")

        prompt = f"""
News Title: {news['title']}

News Description: {news.get('description', '')}

Write the response in the same language as the news title.

Return ONLY valid JSON.

Rules:
- Write in ONLY ONE language
- Use either pure Hindi OR pure English
- Never mix Hindi and English in the same sentence
- Use proper grammar and spelling
- Language should feel professional and natural
- Jaipur focused
- Headline must feel BREAKING and attention-grabbing
- Headline should create curiosity
- Avoid clickbait or fake drama
- Keep headline under 8 words
- Headline should look like a professional Jaipur news page
- Detailed informative caption
- Explain what happened clearly
- Explain why Jaipur people should care
- Use clean readable sentences
- 70-120 word caption
- Caption WITHOUT hashtags
- 8 hashtags only
- Use real Instagram hashtags starting with #
- Space separated hashtags
- Comma separated keywords
- Write ONLY about current/latest news
- Never mention old years like 2024
- Never invent facts
- Never create fake information
- If information is limited, keep caption factual
- Use simple news-style language
- NO emojis inside caption
- NO Hinglish
- NO double quotes inside values
- NO line breaks inside JSON values

Format:
{{
    "headline": "",
    "caption": "",
    "hashtags": "",
    "keywords": ""
}}
"""

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional Jaipur news editor for Mast Jaipur. "
                        "Write clean, grammatically correct Instagram news content. "
                        "Use either proper Hindi or proper English only. "
                        "Never mix languages in the same sentence. "
                        "Headlines should feel modern, sharp, and professional. "
                        "Captions should explain the news clearly and factually. "
                        "Return ONLY valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=350,
            temperature=0.8
        )

        content = response.choices[0].message.content

        log("📦 AI Response Received")

        content = content.strip()

        content = content.replace("\n", " ")

        content = content.replace("\r", " ")

        content = re.sub(r'\s+', ' ', content)

        content = re.sub(r'[\x00-\x1F\x7F]', '', content)

        content = (
            content
            .replace('“', '"')
            .replace('”', '"')
            .replace("‘", "'")
            .replace("’", "'")
        )

        log("🧹 AI Response Cleaned")

        try:

            result = json.loads(content)

        except Exception:

            log("⚠ First JSON Parse Failed")

            fixed_content = (
                content
                .replace('\\"', '"')
                .replace("'", "")
            )

            result = json.loads(fixed_content)

        required_keys = [
            "headline",
            "caption",
            "hashtags",
            "keywords"
        ]

        for key in required_keys:

            if key not in result:

                log(f"❌ Missing Key: {key}")

                return None

        result["headline"] = str(
            result["headline"]
        ).strip()

        result["caption"] = str(
            result["caption"]
        ).strip()

        result["hashtags"] = str(
            result["hashtags"]
        ).strip()

        result["keywords"] = str(
            result["keywords"]
        ).strip()

        log("✅ AI Content Generated")

        return result

    except Exception as e:

        log(f"❌ AI Generation Error: {e}")

        traceback.print_exc()

        return None

# =====================================================
# CREATE IMAGE
# =====================================================

def create_image(headline):

    try:

        log("🎨 Creating Image")

        image = Image.open("background.jpg").convert("RGB")

        width, height = image.size

        draw = ImageDraw.Draw(image)

        font = ImageFont.truetype(
            "Poppins-Bold.ttf",
            450
        )

        wrapped = textwrap.fill(headline, width=16)

        bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=font
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) / 2
        y = (height - text_height) / 2

        draw.multiline_text(
            (x + 3, y + 3),
            wrapped,
            font=font,
            fill="black",
            align="center"
        )

        draw.multiline_text(
            (x, y),
            wrapped,
            font=font,
            fill="#9A166A",
            align="center"
        )

        output_path = "final_post.jpg"

        image.save(output_path)

        log("✅ Image Created")

        return output_path

    except Exception as e:

        log(f"❌ Image Creation Error: {e}")

        traceback.print_exc()

        return None

# =====================================================
# UPLOAD IMAGE
# =====================================================

def upload_image(path):

    try:

        log("☁ Uploading Image To Cloudinary")

        response = cloudinary.uploader.upload(
            path,
            timeout=60
        )

        image_url = response["secure_url"]

        log("✅ Cloudinary Upload Successful")

        return image_url

    except Exception as e:

        log(f"❌ Cloudinary Upload Error: {e}")

        traceback.print_exc()

        return None

# =====================================================
# INSTAGRAM POST
# =====================================================

def post_instagram(image_url, caption):

    try:

        log("📤 Creating Instagram Media Container")

        create_url = (
            f"https://graph.facebook.com/v22.0/"
            f"{INSTAGRAM_BUSINESS_ID}/media"
        )

        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        }

        response = requests.post(
            create_url,
            data=payload,
            timeout=60
        )

        result = response.json()

        log(f"📦 Container Response: {result}")

        if "id" not in result:

            log("❌ Failed To Create Media Container")

            return False

        creation_id = result["id"]

        log("⏳ Waiting For Instagram Processing")

        time.sleep(20)

        publish_url = (
            f"https://graph.facebook.com/v22.0/"
            f"{INSTAGRAM_BUSINESS_ID}/media_publish"
        )

        publish_payload = {
            "creation_id": creation_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN
        }

        publish_response = requests.post(
            publish_url,
            data=publish_payload,
            timeout=60
        )

        publish_result = publish_response.json()

        log(f"🚀 Publish Response: {publish_result}")

        if "id" in publish_result:

            log("✅ Instagram Post Published")

            return True

        if (
            "error" in publish_result
            and publish_result["error"].get("code") == 9007
        ):

            log("🔄 Media Not Ready. Retrying")

            time.sleep(15)

            retry_response = requests.post(
                publish_url,
                data=publish_payload,
                timeout=60
            )

            retry_result = retry_response.json()

            log(f"🔁 Retry Response: {retry_result}")

            if "id" in retry_result:

                log("✅ Instagram Published After Retry")

                return True

        log("❌ Instagram Publish Failed")

        return False

    except Exception as e:

        log(f"❌ Instagram Error: {e}")

        traceback.print_exc()

        return False

# =====================================================
# DUPLICATE CHECK
# =====================================================

def already_posted(title):

    try:

        if not os.path.exists("posted_news.txt"):
            return False

        with open("posted_news.txt", "r") as file:
            posted = file.read().splitlines()

        cleaned = clean_title(title)

        posted_cleaned = [
            clean_title(p)
            for p in posted
        ]

        return cleaned in posted_cleaned

    except Exception as e:

        log(f"❌ Duplicate Check Error: {e}")

        return False

# =====================================================
# SAVE POSTED NEWS
# =====================================================

def save_posted_news(title):

    try:

        with open("posted_news.txt", "a") as file:

            file.write(title + "\n")

        log("✅ News Saved To Cache")

    except Exception as e:

        log(f"❌ Save Cache Error: {e}")

# =====================================================
# MAIN AUTOMATION
# =====================================================

def run_automation():

    try:

        log("🚀 Starting Jaipur Automation")

        news = fetch_news()

        if not news:

            log("⚠ No News Available")

            return

        if already_posted(news["title"]):

            log("⚠ Duplicate News Skipped")

            return

        ai_content = generate_content(news)

        if not ai_content:

            log("❌ AI Content Failed")

            return

        headline = ai_content["headline"]

        hashtags = ai_content.get("hashtags", "")
        keywords = ai_content.get("keywords", "")

        if isinstance(hashtags, list):

            hashtags = " ".join(
                tag if tag.startswith("#")
                else f"#{tag}"
                for tag in hashtags
            )

        if isinstance(keywords, list):

            keywords = ", ".join(keywords)

        caption = (
            ai_content["caption"]
            + "\n\n"
            + hashtags
            + "\n\n["
            + keywords
            + "]"
        )

        log(f"🔥 Headline: {headline}")

        image_path = create_image(headline)

        if not image_path:
            return

        image_url = upload_image(image_path)

        if not image_url:
            return

        success = post_instagram(
            image_url,
            caption
        )

        if success:

            save_posted_news(news["title"])

        else:

            log("❌ Post Failed")

    except Exception as e:

        log(f"❌ Automation Crash: {e}")

        traceback.print_exc()

# =====================================================
# RUN
# =====================================================

run_automation()