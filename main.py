from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)

# Normalize URL to ensure it has http(s) protocol
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

# Extract Meta Tags from HTML content
def extract_meta_tags(html: str, url: str):
    soup = BeautifulSoup(html, "html.parser")

    def get_meta_by_name(name):
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content", "").strip() if tag and tag.get("content") else ""

    def get_meta_by_property(prop):
        tag = soup.find("meta", attrs={"property": prop})
        if not tag:
            tag = soup.find("meta", attrs={"name": prop})
        return tag.get("content", "").strip() if tag and tag.get("content") else ""

    def get_link_rel(rel):
        tag = soup.find("link", rel=rel)
        return tag.get("href", "").strip() if tag and tag.get("href") else ""

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta = {
        "title": title,
        "description": get_meta_by_name("description"),
        "robots": get_meta_by_name("robots"),
        "canonical": get_link_rel("canonical"),
        # Open Graph
        "og:title": get_meta_by_property("og:title"),
        "og:description": get_meta_by_property("og:description"),
        "og:image": get_meta_by_property("og:image"),
        "og:url": get_meta_by_property("og:url"),
        "og:type": get_meta_by_property("og:type"),
        # Twitter
        "twitter:card": get_meta_by_property("twitter:card"),
        "twitter:title": get_meta_by_property("twitter:title"),
        "twitter:description": get_meta_by_property("twitter:description"),
        "twitter:image": get_meta_by_property("twitter:image"),
    }

    # fallback: if og:url missing, use the requested URL
    if not meta["og:url"]:
        meta["og:url"] = url

    return meta

# Generate SEO feedback for the user
def generate_feedback(meta):
    feedback = []

    def add(level, message):
        feedback.append({"level": level, "message": message})

    # Title checks
    title = meta.get("title", "")
    if not title:
        add("error", "Missing <title> tag. Every page should have a unique, descriptive title.")
    else:
        if len(title) < 30:
            add("warning", f"Title is quite short ({len(title)} chars). Aim for 30–60 characters.")
        elif len(title) > 65:
            add("warning", f"Title may be too long ({len(title)} chars). It might get truncated in search results.")
        else:
            add("ok", "Title length looks good.")

    # Description checks
    description = meta.get("description", "")
    if not description:
        add("error", "Missing meta description. Add a concise, compelling description (50–160 characters).")
    else:
        if len(description) < 50:
            add("warning", f"Description is short ({len(description)} chars). Aim for 50–160 characters.")
        elif len(description) > 170:
            add("warning", f"Description is long ({len(description)} chars). It might be truncated in search.")
        else:
            add("ok", "Meta description length looks good.")

    # Robots
    robots = meta.get("robots", "").lower()
    if robots:
        if "noindex" in robots:
            add("warning", "robots tag contains 'noindex'. This page will not appear in search results.")
        if "nofollow" in robots:
            add("warning", "robots tag contains 'nofollow'. Search engines won't follow links on this page.")
    else:
        add("ok", "No robots meta tag found. Default is index, follow (usually fine).")

    # Canonical
    if not meta.get("canonical"):
        add("warning", "Missing canonical link tag. Consider adding one to avoid duplicate content issues.")
    else:
        add("ok", "Canonical URL is set.")

    # Open Graph
    if not meta.get("og:title") or not meta.get("og:description"):
        add("warning", "Open Graph title/description missing or incomplete. Social shares may look generic.")
    else:
        add("ok", "Open Graph title and description are present.")

    if not meta.get("og:image"):
        add("warning", "Open Graph image missing. Social shares may not show a nice preview image.")
    else:
        add("ok", "Open Graph image is set.")

    # Twitter
    if not meta.get("twitter:card"):
        add("warning", "twitter:card missing. Set it to 'summary' or 'summary_large_image' for better Twitter previews.")
    else:
        add("ok", f"Twitter card type is '{meta.get('twitter:card')}'.")

    return feedback

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "No URL provided."}), 400

    url = normalize_url(url)

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (SEO Checker Bot)"})
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error fetching URL: {e}"}), 400

    meta = extract_meta_tags(resp.text, url)
    feedback = generate_feedback(meta)

    parsed = urlparse(url)
    display_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"

    return jsonify({
        "url": url,
        "display_url": display_url,
        "meta": meta,
        "feedback": feedback
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
