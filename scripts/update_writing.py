"""
Fetches RSS feeds from Resolution Foundation Substack and VoxEU,
extracts posts by/about Gregory Thwaites, and updates data/writing.json.

Run manually: python scripts/update_writing.py
Or automatically via GitHub Actions (see .github/workflows/update-writing.yml)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from xml.etree import ElementTree

FEEDS = [
    {
        "url": "https://resolutionfoundation.substack.com/feed",
        "source": "rf-substack",
        "sourceName": "Resolution Foundation Substack",
        "filter_author": True,  # Only include if Gregory is the author
        "author_patterns": ["gregory thwaites", "greg thwaites"],
    },
    {
        "url": "https://www.resolutionfoundation.org/feed/",
        "source": "rf",
        "sourceName": "Resolution Foundation",
        "filter_author": True,
        "author_patterns": ["gregory thwaites", "greg thwaites", "thwaites"],
    },
]

DATA_FILE = Path(__file__).parent.parent / "data" / "writing.json"


def fetch_feed(url):
    """Fetch and parse an RSS/Atom feed."""
    req = Request(url, headers={"User-Agent": "gregorythwaites.com feed updater"})
    with urlopen(req, timeout=30) as resp:
        return ElementTree.parse(resp)


def extract_items(tree, feed_config):
    """Extract items from an RSS feed tree."""
    items = []
    root = tree.getroot()

    # Handle RSS 2.0
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        creator_el = item.find("{http://purl.org/dc/elements/1.1/}creator")
        author_el = item.find("author")

        if title_el is None or link_el is None:
            continue

        title = title_el.text or ""
        link = link_el.text or ""

        # Parse date
        date_str = ""
        if pubdate_el is not None and pubdate_el.text:
            try:
                # RSS date format: "Thu, 06 Feb 2026 12:00:00 GMT"
                dt = datetime.strptime(
                    re.sub(r"\s+\w+$", "", pubdate_el.text.strip()),
                    "%a, %d %b %Y %H:%M:%S",
                )
                date_str = dt.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    dt = datetime.strptime(pubdate_el.text.strip()[:10], "%Y-%m-%d")
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = ""

        # Check author filter
        if feed_config["filter_author"]:
            author_text = ""
            if creator_el is not None and creator_el.text:
                author_text = creator_el.text.lower()
            elif author_el is not None and author_el.text:
                author_text = author_el.text.lower()

            # Also check title for attribution
            combined = (author_text + " " + title).lower()
            if not any(p in combined for p in feed_config["author_patterns"]):
                continue

        items.append(
            {
                "title": title.strip(),
                "url": link.strip(),
                "date": date_str,
                "source": feed_config["source"],
                "sourceName": feed_config["sourceName"],
            }
        )

    return items


def main():
    # Load existing data
    existing = []
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_urls = {item["url"] for item in existing}

    # Fetch new items from feeds
    new_count = 0
    for feed_config in FEEDS:
        try:
            print(f"Fetching {feed_config['url']}...")
            tree = fetch_feed(feed_config["url"])
            items = extract_items(tree, feed_config)
            for item in items:
                if item["url"] not in existing_urls:
                    existing.append(item)
                    existing_urls.add(item["url"])
                    new_count += 1
                    print(f"  + {item['title']}")
        except Exception as e:
            print(f"  Warning: could not fetch {feed_config['url']}: {e}")

    # Sort by date descending
    existing.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Write back
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {new_count} new items added. Total: {len(existing)} items.")
    return 0 if new_count == 0 else 1  # Exit 1 if changes to trigger commit


if __name__ == "__main__":
    sys.exit(main())
