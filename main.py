import os
import json
import requests
import textwrap
import cloudinary
import cloudinary.uploader

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from openai import OpenAI

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

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
# FETCH NEWS
# =====================================================

# =====================================================
# FETCH MULTIPLE NEWS SOURCES
# =====================================================

def fetch_news():

    articles = []

    # =================================================
    # GNEWS
    # =================================================

    try:

        GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

        gnews_url = (
            f"https://gnews.io/api/v4/search?"
            f'q=Jaipur OR Rajasthan'
            f"&lang=en"
            f"&max=10"
            f"&apikey={GNEWS_API_KEY}"
        )

        response = requests.get(gnews_url)

        data = response.json()

        for article in data.get("articles", []):

            articles.append({
                "title": article["title"],
                "description": article.get("description", "")
            })

    except Exception as e:
        print("GNews Error:", e)

    # =================================================
    # NEWS API
    # =================================================

    try:

        newsapi_key = os.getenv("NEWS_API_KEY")

        newsapi_url = (
            f"https://newsapi.org/v2/everything?"
            f'q=Jaipur OR Rajasthan'
            f"&language=en"
            f"&pageSize=10"
            f"&sortBy=publishedAt"
            f"&apiKey={newsapi_key}"
        )

        response = requests.get(newsapi_url)

        data = response.json()

        for article in data.get("articles", []):

            articles.append({
                "title": article["title"],
                "description": article.get("description", "")
            })

    except Exception as e:
        print("NewsAPI Error:", e)

    # =================================================
    # REMOVE DUPLICATES
    # =================================================

    unique_articles = []

    seen_titles = set()

    for article in articles:

        title = article["title"].strip().lower()

        if title not in seen_titles:

            seen_titles.add(title)

            unique_articles.append(article)

    # =================================================
    # FIND NON-POSTED ARTICLE
    # =================================================

    for article in unique_articles:

        if not already_posted(article["title"]):

            return article

    raise Exception("No New Unique News Found")

# =====================================================
# AI CONTENT GENERATION
# =====================================================

def generate_content(news):

    prompt = f"""
News: {news['title']}

Return JSON only.

Rules:
- Hinglish
- Viral Instagram style
- SEO optimized
- Jaipur audience
- Max 35 word caption
- Caption WITHOUT hashtags
- 8 hashtags only
- Use real Instagram hashtags starting with #
- Space separated hashtags
- Comma separated keywords
- Short attractive headline

Format:
{{
"headline":"",
"caption":"",
"hashtags":"#tag1 #tag2 #tag3",
"keywords":""
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Mast Jaipur social media writer. "
                    "Write short viral Jaipur news captions."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=220,
        temperature=0.8
    )

    content = response.choices[0].message.content

    try:
        result = json.loads(content)
    except:
        print("❌ JSON Error")
        print(content)
        return None

    return result

# =====================================================
# CREATE IMAGE
# =====================================================

def create_image(headline):

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

    # SHADOW
    draw.multiline_text(
        (x + 3, y + 3),
        wrapped,
        font=font,
        fill="black",
        align="center"
    )

    # MAIN TEXT
    draw.multiline_text(
        (x, y),
        wrapped,
        font=font,
        fill="#9A166A",
        align="center"
    )

    # BRANDING
    small_font = ImageFont.truetype(
        "Poppins-Bold.ttf",
        35
    )

    output_path = "final_post.jpg"

    image.save(output_path)

    print("✅ Image Created")

    return output_path

# =====================================================
# UPLOAD IMAGE
# =====================================================

def upload_image(path):

    response = cloudinary.uploader.upload(path)

    return response["secure_url"]

# =====================================================
# INSTAGRAM POST
# =====================================================

def post_instagram(image_url, caption):

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
        data=payload
    )

    result = response.json()

    print(result)

    creation_id = result["id"]

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
        data=publish_payload
    )

    print("✅ Posted Successfully")
    print(publish_response.json())

# =====================================================
# DUPLICATE CHECK
# =====================================================

def already_posted(title):

    if not os.path.exists("posted_news.txt"):
        return False

    with open("posted_news.txt", "r") as file:
        posted = file.read().splitlines()

    return title in posted

# =====================================================
# SAVE POSTED NEWS
# =====================================================

def save_posted_news(title):

    with open("posted_news.txt", "a") as file:
        file.write(title + "\n")

# =====================================================
# MAIN AUTOMATION
# =====================================================

def run_automation():

    print("🚀 Starting Automation")

    # FETCH NEWS
    news = fetch_news()

    print("✅ News Fetched")

    # CHECK DUPLICATE
    if already_posted(news["title"]):

        print("⚠ Already Posted")
        return

    # AI CONTENT
    ai_content = generate_content(news)

    if not ai_content:
        return

    headline = ai_content["headline"]

    hashtags = ai_content.get("hashtags", "")
    keywords = ai_content.get("keywords", "")

    # CONVERT LIST TO STRING
    if isinstance(hashtags, list):
        hashtags = " ".join(
            tag if tag.startswith("#") else f"#{tag}"
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

    print("✅ AI Content Generated")

    print("Headline:")
    print(headline)

    # CREATE IMAGE
    image_path = create_image(headline)

    # UPLOAD IMAGE
    image_url = upload_image(image_path)

    print("✅ Image Uploaded")

    # POST INSTAGRAM
    post_instagram(image_url, caption)

    # SAVE POSTED NEWS
    save_posted_news(news["title"])

    print("✅ News Saved")

# =====================================================
# RUN
# =====================================================

run_automation()