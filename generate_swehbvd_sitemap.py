#!/usr/bin/env python3
"""
Generate a complete Sitemap (XML) and URL list (TXT) for NASA SWEHB Revision D (SWEHBVD).
This queries the Confluence hierarchy API endpoints to retrieve all 1,200+ pages
strictly within the SWEHBVD space, excluding earlier revisions (Rev A, B, C).
"""

import os
import sys
import time
import requests

BASE_URL = "https://swehb.nasa.gov"
SPACE_KEY = "SWEHBVD"
ROOT_PAGE_ID = "100598340"  # Book A. Introduction

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_children(session: requests.Session, page_id: str, retries: int = 5):
    url = f"{BASE_URL}/pages/children.action?pageId={page_id}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                return r.json(), True
            elif r.status_code == 429:
                sleep_time = 3 * (attempt + 1)
                print(f"    [!] Rate limited (429) on pageId {page_id}. Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                time.sleep(2 ** attempt)
        except Exception as e:
            sleep_time = 2 ** attempt
            print(f"    [!] Error fetching pageId {page_id} (attempt {attempt+1}/{retries}): {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    print(f"    [ERROR] Failed to fetch children for pageId {page_id} after {retries} attempts.")
    return [], False


def main():
    print(f"[*] Starting crawl of NASA SWEHB Rev D ({SPACE_KEY})...")
    session = requests.Session()
    session.headers.update(HEADERS)

    visited_pages = set()
    to_visit = [ROOT_PAGE_ID]
    all_urls = set()
    failed_nodes = []

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

        children, success = fetch_children(session, current_id)
        if not success:
            failed_nodes.append(current_id)

        for child in children:
            cid = child.get("pageId")
            href = child.get("href")
            if href:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                all_urls.add(full_url)
            if cid and cid not in visited_pages:
                to_visit.append(cid)

        count += 1
        if count % 25 == 0:
            print(f"    Crawled {count} nodes... Discovered {len(all_urls)} URLs so far.")

    sorted_urls = sorted(list(all_urls))
    print(f"[+] Crawl complete! Discovered {len(sorted_urls)} total pages in Rev D.")

    # Guard: Do not allow partial crawls or dropped branches to overwrite the sitemap
    if failed_nodes:
        print(f"[!] ERROR: {len(failed_nodes)} nodes failed to load during crawl: {failed_nodes}")
        print("[!] Aborting to prevent publishing a truncated sitemap.")
        sys.exit(1)

    if len(sorted_urls) < 1200:
        print(f"[!] ERROR: Discovered only {len(sorted_urls)} URLs (expected >= 1,200).")
        print("[!] Aborting to prevent publishing a truncated sitemap.")
        sys.exit(1)

    out_sitemap = "swehbvd_sitemap.xml"
    out_txt = "swehbvd_urls.txt"

    with open(out_txt, "w") as f:
        for u in sorted_urls:
            f.write(u + "\n")

    with open(out_sitemap, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in sorted_urls:
            f.write(f"  <url><loc>{u}</loc></url>\n")
        f.write("</urlset>\n")

    print(f"[+] Saved sitemap XML: {os.path.abspath(out_sitemap)}")
    print(f"[+] Saved URLs list:   {os.path.abspath(out_txt)}")


if __name__ == "__main__":
    main()

