"""
====================================================
  6-AGENT TEAM — FULLY AUTOMATED NEWS BLOG
====================================================
  Agent 1: Manager     — coordinates everything
  Agent 2: TrendScout  — finds trending topics
  Agent 3: Writer      — writes full article
  Agent 4: SEO         — optimizes for Google
  Agent 5: Publisher   — posts to Blogger
  Agent 6: Social      — shares on Facebook page

  FREE tools: Claude API, Blogger API, GitHub Actions
  Run: python agent_team.py
====================================================
"""

import os, json, time, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
BLOGGER_BLOG_ID      = os.getenv("BLOGGER_BLOG_ID")
BLOGGER_ACCESS_TOKEN = os.getenv("BLOGGER_ACCESS_TOKEN")
FB_PAGE_TOKEN        = os.getenv("FB_PAGE_TOKEN")   # Optional — Facebook page token
FB_PAGE_ID           = os.getenv("FB_PAGE_ID")      # Optional — Facebook page ID

NICHE    = "cricket IPL news India"   # Change to your niche
COUNTRY  = "IN"
ARTICLES_PER_RUN = 3   # How many articles to publish per day


# ══════════════════════════════════════════════════
# HELPER: Call Claude API
# ══════════════════════════════════════════════════

def ask_claude(prompt, max_tokens=1500):
    """Send a prompt to Claude API and return the text response."""
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        return r.json()["content"][0]["text"]
    except Exception as e:
        print(f"   Claude API error: {e}")
        return None


# ══════════════════════════════════════════════════
# AGENT 1: MANAGER
# ══════════════════════════════════════════════════

class ManagerAgent:
    """
    The boss. Runs daily via GitHub Actions.
    Tells each agent what to do and passes results along.
    """
    def run(self):
        print("\n" + "="*55)
        print(f"  MANAGER AGENT STARTED — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*55)

        if not ANTHROPIC_API_KEY or not BLOGGER_BLOG_ID or not BLOGGER_ACCESS_TOKEN:
            print("ERROR: Missing API keys. Check your GitHub Secrets or .env file.")
            return

        # Initialize all agents
        trend_agent   = TrendScoutAgent()
        writer_agent  = WriterAgent()
        seo_agent     = SEOAgent()
        publisher     = PublisherAgent()
        social_agent  = SocialAgent()

        # Get trending topics
        topics = trend_agent.get_topics(count=ARTICLES_PER_RUN)
        print(f"\n Manager got {len(topics)} topics to process today.")

        results = []
        for i, topic in enumerate(topics, 1):
            print(f"\n--- Article {i}/{len(topics)}: {topic[:60]} ---")

            # Write article
            article = writer_agent.write(topic)
            if not article:
                print("   Skipping — writing failed.")
                continue

            # Optimize for SEO
            article = seo_agent.optimize(article, topic)

            # Publish to Blogger
            url = publisher.publish(article)
            if not url:
                print("   Skipping — publish failed.")
                continue

            # Share on social media
            social_agent.share(article["title"], url, topic)

            results.append({"topic": topic, "title": article["title"], "url": url})
            time.sleep(8)  # Pause between articles

        # Summary
        print(f"\n{'='*55}")
        print(f"  DONE — Published {len(results)} articles today")
        for r in results:
            print(f"  - {r['title'][:50]}...")
            print(f"    {r['url']}")
        print("="*55)
        self._save_log(results)

    def _save_log(self, results):
        log = {"date": datetime.now().isoformat(), "articles": results}
        logs = []
        if os.path.exists("log.json"):
            with open("log.json") as f:
                try: logs = json.load(f)
                except: logs = []
        logs.append(log)
        with open("log.json", "w") as f:
            json.dump(logs[-30:], f, indent=2)  # Keep last 30 days


# ══════════════════════════════════════════════════
# AGENT 2: TREND SCOUT
# ══════════════════════════════════════════════════

class TrendScoutAgent:
    """
    Finds what people in India are searching right now.
    Uses Google Trends (free) and Google News RSS (free).
    """
    def get_topics(self, count=3):
        print("\n[TREND SCOUT] Searching for trending topics...")
        topics = self._from_google_trends(count)
        if not topics:
            topics = self._from_rss(count)
        if not topics:
            topics = self._fallback(count)
        print(f"   Found: {topics}")
        return topics[:count]

    def _from_google_trends(self, count):
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-IN", tz=330)
            df = pt.trending_searches(pn="india")
            return df[0].tolist()[:count]
        except:
            return []

    def _from_rss(self, count):
        try:
            url = f"https://news.google.com/rss/search?q={NICHE.replace(' ','+')}&hl=en-IN&gl=IN&ceid=IN:en"
            content = requests.get(url, timeout=10).text
            items = content.split("<item>")[1:count+1]
            topics = []
            for item in items:
                if "<title>" in item:
                    t = item.split("<title>")[1].split("</title>")[0]
                    t = t.replace("<![CDATA[","").replace("]]>","").strip()
                    topics.append(t)
            return topics
        except:
            return []

    def _fallback(self, count):
        defaults = [
            f"Latest {NICHE} news today",
            f"Top stories in {NICHE} this week",
            f"Breaking: {NICHE} updates"
        ]
        return defaults[:count]


# ══════════════════════════════════════════════════
# AGENT 3: WRITER
# ══════════════════════════════════════════════════

class WriterAgent:
    """
    Uses Claude AI to write a complete, engaging blog article.
    Returns structured article dict with title, content, tags.
    """
    def write(self, topic):
        print(f"\n[WRITER] Writing article: {topic[:50]}...")

        prompt = f"""Write a complete blog article for an Indian news blog about: "{topic}"

Niche: {NICHE}
Target audience: Indian readers, age 18-40

Return ONLY a JSON object with these exact fields (no markdown, no code blocks):
{{
  "title": "SEO-optimized catchy title (max 60 chars)",
  "content": "Full HTML article with <h1>, <h2>, <p> tags. 700-900 words. Engaging, informative, easy to read.",
  "excerpt": "2-sentence summary for social media sharing",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}

Make the title keyword-rich for Google SEO. Write content in simple English."""

        response = ask_claude(prompt, max_tokens=2000)
        if not response:
            return None

        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            article = json.loads(clean)
            print(f"   Written: {article['title'][:55]}...")
            return article
        except Exception as e:
            print(f"   JSON parse error: {e}")
            # Try to extract title from content
            if "<h1>" in response:
                title = response.split("<h1>")[1].split("</h1>")[0]
                return {"title": title, "content": response, "excerpt": topic, "tags": [NICHE]}
            return None


# ══════════════════════════════════════════════════
# AGENT 4: SEO AGENT
# ══════════════════════════════════════════════════

class SEOAgent:
    """
    Optimizes the article for Google search ranking.
    Adds meta description, proper heading structure,
    internal keyword density, and schema markup.
    """
    def optimize(self, article, topic):
        print(f"\n[SEO] Optimizing article for Google...")

        prompt = f"""Improve this HTML blog article for Google SEO. Topic: "{topic}"

Current title: {article['title']}
Current content (first 300 chars): {article['content'][:300]}

Return ONLY a JSON object (no markdown):
{{
  "title": "improved SEO title with main keyword near start, max 60 chars",
  "meta_description": "155-char meta description with keyword",
  "content": "improved HTML content — same article but with: keyword in first paragraph, 2-3 LSI keywords added naturally, proper H2 subheadings every 200 words",
  "excerpt": "{article.get('excerpt', topic[:100])}",
  "tags": {json.dumps(article.get('tags', []))}
}}"""

        response = ask_claude(prompt, max_tokens=2000)
        if not response:
            print("   SEO failed, using original article.")
            return article

        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            optimized = json.loads(clean)
            print(f"   SEO done. Meta: {optimized.get('meta_description','')[:60]}...")
            return optimized
        except:
            print("   SEO parse failed, using original.")
            return article


# ══════════════════════════════════════════════════
# AGENT 5: PUBLISHER
# ══════════════════════════════════════════════════

class PublisherAgent:
    """
    Posts the finished article to Blogger via API.
    Handles labels, status, and returns the live URL.
    """
    def publish(self, article):
        title   = article.get("title", "Untitled")
        content = article.get("content", "")
        tags    = article.get("tags", ["news", NICHE])

        print(f"\n[PUBLISHER] Publishing: {title[:50]}...")

        # Add meta description as hidden HTML if available
        meta = article.get("meta_description", "")
        if meta:
            content = f'<meta name="description" content="{meta}">\n{content}'

        url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
        headers = {
            "Authorization": f"Bearer {BLOGGER_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "kind": "blogger#post",
            "title": title,
            "content": content,
            "labels": tags + ["auto-published"],
            "status": "LIVE"
        }

        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            if r.status_code in [200, 201]:
                post_url = r.json().get("url", "")
                print(f"   PUBLISHED: {post_url}")
                return post_url
            else:
                print(f"   Blogger error {r.status_code}: {r.text[:150]}")
                return None
        except Exception as e:
            print(f"   Publish failed: {e}")
            return None


# ══════════════════════════════════════════════════
# AGENT 6: SOCIAL AGENT
# ══════════════════════════════════════════════════

class SocialAgent:
    """
    Shares the published article on Facebook page.
    Requires a Facebook Page Access Token (free from Meta Developer).
    If no token is set, it just prints the share text instead.
    """
    def share(self, title, url, topic):
        print(f"\n[SOCIAL] Sharing article...")

        # Generate catchy social post using Claude
        prompt = f"""Write a short, engaging Facebook post (max 3 sentences) to share this article:
Title: {title}
URL: {url}
Niche: {NICHE}

Make it catchy, add 3 relevant hashtags at the end. Return only the post text."""

        post_text = ask_claude(prompt, max_tokens=200)
        if not post_text:
            post_text = f"New article: {title}\n\nRead more: {url}\n\n#{NICHE.replace(' ','')}"

        # Post to Facebook Page (if token is set)
        if FB_PAGE_TOKEN and FB_PAGE_ID:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
                    data={
                        "message": post_text,
                        "link": url,
                        "access_token": FB_PAGE_TOKEN
                    },
                    timeout=20
                )
                if r.status_code == 200:
                    print(f"   Facebook post published!")
                else:
                    print(f"   Facebook error: {r.text[:100]}")
            except Exception as e:
                print(f"   Facebook failed: {e}")
        else:
            # Print share text (user can manually post)
            print(f"   Share text ready (no FB token set):")
            print(f"   {post_text[:120]}...")

        # Always save share text to file
        with open("social_posts.txt", "a") as f:
            f.write(f"\n---{datetime.now().strftime('%Y-%m-%d')}\n{post_text}\n{url}\n")
        print("   Saved to social_posts.txt")


# ══════════════════════════════════════════════════
# RUN THE AGENT TEAM
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    manager = ManagerAgent()
    manager.run()
