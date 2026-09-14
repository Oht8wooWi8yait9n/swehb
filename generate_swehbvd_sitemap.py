#!/usr/bin/env python3
"""
Generate a complete Sitemap (XML) and URL list (TXT) for NASA SWEHB Revision D (SWEHBVD).
This queries the Confluence hierarchy API endpoints to retrieve all 1,200+ pages
strictly within the SWEHBVD space, excluding earlier revisions (Rev A, B, C).
Includes robust retry logic, connection resets on SSL drop, rate pacing, and caching.
"""

import os
import sys
import time
import json
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

BASE_URL = "https://swehb.nasa.gov"
SPACE_KEY = "SWEHBVD"
ROOT_PAGE_ID = "100598340"  # Book A. Introduction
REQUEST_DELAY_SEC = 0.2     # Respectful delay between requests to avoid WAF / rate limiting

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def create_session():
    """Create a resilient requests.Session with retries and connection limits."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_children(session_holder, page_id: str, retries: int = 5):
    """Fetch child nodes from Confluence. Recreates session on SSL/connection drops."""
    url = f"{BASE_URL}/pages/children.action?pageId={page_id}"
    for attempt in range(retries):
        try:
            r = session_holder["session"].get(url, timeout=25)
            if r.status_code == 200:
                return r.json(), True
            elif r.status_code == 429:
                sleep_time = 3 * (attempt + 1)
                print(f"    [!] Rate limited (429) on pageId {page_id}. Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
        except Exception as e:
            sleep_time = 2 * (attempt + 1)
            print(f"    [!] Connection/SSL error on pageId {page_id} (attempt {attempt+1}/{retries}): {e}")
            print(f"        Resetting connection session and retrying in {sleep_time}s...")
            try:
                session_holder["session"].close()
            except Exception:
                pass
            session_holder["session"] = create_session()
            time.sleep(sleep_time)

    print(f"    [ERROR] Failed to fetch children for pageId {page_id} after {retries} attempts.")
    return [], False


def main():
    print(f"[*] Starting crawl of NASA SWEHB Rev D ({SPACE_KEY})...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(base_dir, "swehbvd_cache.json")
    out_sitemap = os.path.join(base_dir, "swehbvd_sitemap.xml")
    out_txt = os.path.join(base_dir, "swehbvd_urls.txt")

    # Load cache if available for fallback
    tree_cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                tree_cache = json.load(f)
            print(f"[*] Loaded tree cache with {len(tree_cache):,} cached parent nodes.")
        except Exception as e:
            print(f"[!] Could not load cache: {e}")

    session_holder = {"session": create_session()}

    visited_pages = set()
    to_visit = [ROOT_PAGE_ID]
    all_urls = set()
    failed_nodes = set()
    updated_cache = {}

    # Known top-level entrypoints
    landing_paths = [
        "/spaces/SWEHBVD/overview",
        "/display/SWEHBVD",
        "/display/SWEHBVD/B.+Institutional+Requirements",
        "/display/SWEHBVD/C.+Project+Software+Requirements",
        "/display/SWEHBVD/D.+Topics",
        "/display/SWEHBVD/E.+Tools%2C+References%2C+and+Terms",
    ]
    for p in landing_paths:
        all_urls.add(f"{BASE_URL}{p}")

    root_href = f"/spaces/SWEHBVD/pages/{ROOT_PAGE_ID}/Book+A.+Introduction"
    all_urls.add(f"{BASE_URL}{root_href}")

    count = 0
    while to_visit:
        current_id = to_visit.pop(0)
        if current_id in visited_pages:
            continue
        visited_pages.add(current_id)

        children, success = fetch_children(session_holder, current_id)
        if not success:
            failed_nodes.add(current_id)
        else:
            updated_cache[current_id] = children

        for child in children:
            cid = child.get("pageId")
            href = child.get("href")
            if href:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                all_urls.add(full_url)
            if cid and cid not in visited_pages:
                to_visit.append(cid)

        count += 1
        if count % 50 == 0:
            print(f"    Crawled {count} nodes... Discovered {len(all_urls)} URLs so far.")

        # Respectful delay between requests
        time.sleep(REQUEST_DELAY_SEC)

    # Secondary Pass: retry failed nodes with longer cooldown
    if failed_nodes:
        print(f"\n[*] Re-attempting {len(failed_nodes)} failed nodes in Phase 2 cooldown pass...")
        time.sleep(5.0)
        still_failed = []
        for fid in list(failed_nodes):
            children, success = fetch_children(session_holder, fid, retries=3)
            if success:
                print(f"    [+] Successfully recovered node {fid}!")
                updated_cache[fid] = children
                for child in children:
                    cid = child.get("pageId")
                    href = child.get("href")
                    if href:
                        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                        all_urls.add(full_url)
                    if cid and cid not in visited_pages:
                        visited_pages.add(cid)
                        to_visit.append(cid)
            else:
                still_failed.append(fid)
            time.sleep(0.5)

        # Fallback to cache for any nodes that still failed
        for fid in still_failed:
            if fid in tree_cache:
                print(f"    [!] Fallback to cache for node {fid} ({len(tree_cache[fid])} children)")
                cached_children = tree_cache[fid]
                updated_cache[fid] = cached_children
                for child in cached_children:
                    cid = child.get("pageId")
                    href = child.get("href")
                    if href:
                        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                        all_urls.add(full_url)
            else:
                print(f"    [ERROR] Node {fid} could not be resolved or found in cache.")

    # Save updated tree cache
    if updated_cache:
        tree_cache.update(updated_cache)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(tree_cache, f)
            print(f"[*] Updated tree cache saved ({len(tree_cache):,} parent nodes).")
        except Exception as e:
            print(f"[!] Warning: Could not save tree cache: {e}")

    sorted_urls = sorted(list(all_urls))
    print(f"\n[+] Crawl complete! Discovered {len(sorted_urls)} total pages in Rev D.")

    # Validation check: require at least 1,200 URLs
    if len(sorted_urls) < 1200:
        print(f"[!] ERROR: Discovered only {len(sorted_urls)} URLs (expected >= 1,200).")
        print("[!] Aborting to prevent publishing a truncated sitemap.")
        sys.exit(1)

    with open(out_txt, "w", encoding="utf-8") as f:
        for u in sorted_urls:
            f.write(u + "\n")

    with open(out_sitemap, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in sorted_urls:
            f.write(f"  <url><loc>{u}</loc></url>\n")
        f.write("</urlset>\n")

    print(f"[+] Saved sitemap XML: {out_sitemap}")
    print(f"[+] Saved URLs list:   {out_txt}")


if __name__ == "__main__":
    main()
