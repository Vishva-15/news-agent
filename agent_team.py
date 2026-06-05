"""
====================================================
  6-AGENT TEAM — FULLY AUTOMATED NEWS BLOG
  UPDATED: Uses Refresh Token (never expires)
====================================================
  SECRETS needed in GitHub:
  - ANTHROPIC_API_KEY
  - BLOGGER_BLOG_ID
  - BLOGGER_CLIENT_ID
  - BLOGGER_CLIENT_SECRET
  - BLOGGER_REFRESH_TOKEN
====================================================
"""

import os, json, time, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY")
BLOGGER_BLOG_ID        = os.getenv("BLOGGER_BLOG_ID")
BLOGGER_CLIENT_ID      = os.getenv("BLOGGER_CLIENT_ID")
BLOGGER_CLIENT_SECRET  = os.getenv("BLOGGER_CLIENT_SECRET")
BLOGGER_REFRESH_TOKEN  = os.getenv("BLOGGER_REFRESH_TOKEN")
FB_PAGE_TOKEN          = os.getenv("FB_PAGE_TOKEN")
FB_PAGE_ID             = os.getenv("FB_PAGE_ID")

NICHE            = "cricket IPL news India"
ARTICLES_PER_RUN = 3


def get_access_token():
    print("[AUTH] Getting fresh access token...")
    try:
        r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     BLOGGER_CLIENT_ID,
                "client_secret": BLOGGER_CLIENT_SECRET,
                "refresh_token": BLOGGER_REFRESH_TOKEN,
                "grant_type":    "refresh_token"
            },
            timeout=15
        )
        data = r.json()
        if "access_token" in data:
            print("   Fresh access token obtained!")
            return data["access_token"]
        else:
            print(f"   Token error: {data}")
            return None
    except Exception as e:
        print(f"   Token fetch failed: {e}")
        return None


def ask_claude(prompt, max_tokens=1500):
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


class ManagerAgent:
    def run(self):
        print("\n" + "="*55)
        print(f"  MANAGER AGENT STARTED — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*55)

        missing = [k for k,v in {
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
            "BLOGGER_BLOG_ID": BLOGGER_BLOG_ID,
            "BLOGGER_CLIENT_ID": BLOGGER_CLIENT_ID,
            "BLOGGER_CLIENT_SECRET": BLOGGER_CLIENT_SECRET,
            "BLOGGER_REFRESH_TOKEN": BLOGGER_REFRESH_TOKEN
        }.items() if not v]

        if missing:
            print(f"ERROR: Missing secrets: {', '.join(missing)}")
            return

        access_token = get_access_token()
        if not access_token:
            print("ERROR: Could not get access token.")
            return

        trend_agent  = TrendScoutAgent()
        writer_agent = WriterAgent()
        seo_agent    = SEOAgent()
        publisher    = PublisherAgent(access_token)
        social_agent = SocialAgent()

        topics = trend_agent.get_topics(count=ARTICLES_PER_RUN)
        results = []

        for i, topic in enumerate(topics, 1):
            print(f"\n--- Article {i}/{len(topics)}: {topic[:60]} ---")
            article = writer_agent.write(topic)
            if not article: continue
            article = seo_agent.optimize(article, topic)
            url = publisher.publish(article)
            if not url: continue
            social_agent.share(article["title"], url, topic)
            results.append({"topic": topic, "title": article["title"], "url": url})
            time.sleep(8)

        print(f"\n{'='*55}")
        print(f"  DONE — Published {len(results)} articles")
        for r in results:
            print(f"  + {r['title'][:50]}")
            print(f"    {r['url']}")
        print("="*55)

        logs = []
        if os.path.exists("log.json"):
            with open("log.json") as f:
                try: logs = json.load(f)
                except: pass
        logs.append({"date": datetime.now().isoformat(), "articles": results})
        with open("log.json", "w") as f:
            json.dump(logs[-30:], f, indent=2)


class TrendScoutAgent:
    def get_topics(self, count=3):
        print("\n[TREND SCOUT] Finding trending topics...")
        topics = self._from_google_trends(count) or self._from_rss(count) or self._fallback(count)
        print(f"   Topics: {topics}")
        return topics[:count]

    def _from_google_trends(self, count):
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-IN", tz=330)
            return pt.trending_searches(pn="india")[0].tolist()[:count]
        except: return []

    def _from_rss(self, count):
        try:
            url = f"https://news.google.com/rss/search?q={NICHE.replace(' ','+')}&hl=en-IN&gl=IN&ceid=IN:en"
            content = requests.get(url, timeout=10).text
            topics = []
            for item in content.split("<item>")[1:count+1]:
                if "<title>" in item:
                    t = item.split("<title>")[1].split("</title>")[0]
                    topics.append(t.replace("<![CDATA[","").replace("]]>","").strip())
            return topics
        except: return []

    def _fallback(self, count):
        return [f"Latest {NICHE} news today", f"Top {NICHE} stories", f"Breaking {NICHE} updates"][:count]


class WriterAgent:
    def write(self, topic):
        print(f"\n[WRITER] Writing: {topic[:50]}...")
        prompt = f"""Write a complete blog article for an Indian news blog about: "{topic}"
Niche: {NICHE}
Return ONLY a JSON object (no markdown, no code blocks):
{{"title":"SEO title max 60 chars","content":"Full HTML 700-900 words with h1 h2 p tags","excerpt":"2 sentence summary","tags":["tag1","tag2","tag3"]}}"""

        response = ask_claude(prompt, max_tokens=2000)
        if not response: return None
        try:
            clean = response.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"): clean = clean[4:]
            article = json.loads(clean.strip())
            print(f"   Written: {article['title'][:55]}...")
            return article
        except Exception as e:
            print(f"   Parse error: {e}")
            if "<h1>" in response:
                title = response.split("<h1>")[1].split("</h1>")[0]
                return {"title": title, "content": response, "excerpt": topic, "tags": [NICHE]}
            return None


class SEOAgent:
    def optimize(self, article, topic):
        print(f"\n[SEO] Optimizing...")
        prompt = f"""Given this blog article title: "{article['title']}" about topic: "{topic}"
Return ONLY JSON (no markdown):
{{"title":"improved SEO title keyword near start max 60 chars","meta_description":"155 char meta description","excerpt":"{article.get('excerpt','')}","tags":{json.dumps(article.get('tags',[]))}}}
Keep the content exactly as is."""

        response = ask_claude(prompt, max_tokens=400)
        if not response: return article
        try:
            clean = response.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"): clean = clean[4:]
            optimized = json.loads(clean.strip())
            optimized["content"] = article["content"]  # Always keep original content
            print(f"   SEO done.")
            return optimized
        except:
            return article


class PublisherAgent:
    def __init__(self, access_token):
        self.access_token = access_token

    def publish(self, article):
        title   = article.get("title", "Untitled")
        content = article.get("content", "")
        tags    = article.get("tags", ["news", NICHE])
        meta    = article.get("meta_description", "")

        print(f"\n[PUBLISHER] Publishing: {title[:50]}...")
        if meta:
            content = f'<meta name="description" content="{meta}">\n{content}'

        try:
            r = requests.post(
                f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/",
                headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
                json={"kind": "blogger#post", "title": title, "content": content, "labels": tags, "status": "LIVE"},
                timeout=30
            )
            if r.status_code in [200, 201]:
                url = r.json().get("url", "")
                print(f"   PUBLISHED: {url}")
                return url
            else:
                print(f"   Blogger error {r.status_code}: {r.text[:200]}")
                return None
        except Exception as e:
            print(f"   Publish failed: {e}")
            return None


class SocialAgent:
    def share(self, title, url, topic):
        print(f"\n[SOCIAL] Creating share post...")
        post_text = ask_claude(
            f"Write a short Facebook post (max 3 sentences) to share: '{title}'\nURL: {url}\nAdd 3 hashtags. Return only post text.",
            max_tokens=150
        ) or f"New article: {title}\nRead: {url}\n#{NICHE.replace(' ','')}"

        if FB_PAGE_TOKEN and FB_PAGE_ID:
            try:
                r = requests.post(
                    f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
                    data={"message": post_text, "link": url, "access_token": FB_PAGE_TOKEN},
                    timeout=20
                )
                print("   Facebook posted!" if r.status_code == 200 else f"   FB error: {r.text[:80]}")
            except Exception as e:
                print(f"   Facebook failed: {e}")
        else:
            print("   Saved to social_posts.txt")

        with open("social_posts.txt", "a") as f:
            f.write(f"\n---{datetime.now().strftime('%Y-%m-%d')}\n{post_text}\n{url}\n")


if __name__ == "__main__":
    ManagerAgent().run()
