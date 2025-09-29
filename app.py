from collections import defaultdict
from datetime import datetime, timedelta, timezone
import os

from flask import Flask, request, jsonify, render_template_string
import snscrape.modules.twitter as sntwitter

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>X Trends - snscrape</title>
</head>
<body>
  <h1>גרפים לפי מילות מפתח בטוויטר - בלי API</h1>
  <form id="qform" onsubmit="run(event)">
    <input id="q" type="text" placeholder="לדוגמה: ישראל lang:he" required>
    <button type="submit">שלח</button>
  </form>
  <pre id="out"></pre>
  <script>
    async function run(e){
      e.preventDefault();
      const q = document.getElementById("q").value;
      const resp = await fetch("/api/counts?q="+encodeURIComponent(q));
      document.getElementById("out").textContent = await resp.text();
    }
  </script>
</body>
</html>
"""

def x_counts_snscrape(query: str, granularity: str = "hour") -> dict:
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(days=7)

    since_str = start_utc.strftime('%Y-%m-%d')
    until_str = (now_utc + timedelta(days=1)).strftime('%Y-%m-%d')
    q = f"{query} since:{since_str} until:{until_str}"

    max_items = int(os.getenv("SNSCRAPE_MAX_TWEETS", "2000"))
    stamps = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(q).get_items()):
        if i >= max_items:
            break
        if tweet.date:
            stamps.append(tweet.date)

    buckets = defaultdict(int)
    if granularity == "hour":
        for ts in stamps:
            key = ts.replace(minute=0, second=0, microsecond=0)
            buckets[key] += 1
        data = []
        cur = start_utc.replace(minute=0, second=0, microsecond=0)
        endh = now_utc.replace(minute=0, second=0, microsecond=0)
        while cur <= endh:
            nxt = cur + timedelta(hours=1)
            data.append({"start": cur.isoformat(), "end": nxt.isoformat(),
                         "tweet_count": buckets.get(cur, 0)})
            cur = nxt
        return {"data": data}

    if granularity == "day":
        day_buckets = defaultdict(int)
        for ts in stamps:
            day_buckets[ts.date()] += 1
        data = []
        cur = start_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        endd = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        while cur <= endd:
            nxt = cur + timedelta(days=1)
            data.append({"start": cur.isoformat(), "end": nxt.isoformat(),
                         "tweet_count": day_buckets.get(cur.date(), 0)})
            cur = nxt
        return {"data": data}

    raise ValueError("granularity must be 'hour' or 'day'")

@app.get("/")
def index():
    return render_template_string(INDEX_HTML)

@app.get("/api/counts")
def counts():
    q = request.args.get("q", type=str, default="").strip()
    if not q:
        return ("Missing q", 400)
    hourly = x_counts_snscrape(q, "hour").get("data", [])
    daily = x_counts_snscrape(q, "day").get("data", [])
    return jsonify({"hourly": hourly[-24:], "daily": daily})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
