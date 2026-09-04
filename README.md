# NASA SWEHB Revision D (SWEHBVD) Sitemap & URL Index

This repository provides an XML sitemap and complete URL index for **Revision D** of the NASA Software Engineering Handbook (SWEHB) located on Confluence at `https://swehb.nasa.gov`.

## Files

- `swehbvd_sitemap.xml`: Full standard XML sitemap containing all 1,255 pages of Revision D.
- `swehbvd_urls.txt`: Plain text list of all 1,255 URLs (one per line).
- `generate_swehbvd_sitemap.py`: Python script used to crawl Confluence's hierarchy API (`/pages/children.action`) and regenerate the sitemap.

## Usage with Onyx Web Connector

To index NASA SWEHB Rev D in Onyx without indexing previous revisions (Rev A, B, C):

1. Copy the **Raw** URL of `swehbvd_sitemap.xml`:
   ```
   https://raw.githubusercontent.com/Oht8wooWi8yait9n/swehb/main/swehbvd_sitemap.xml
   ```
2. In Onyx Admin UI (**Connectors** -> **Web**):
   - **Connector Name**: `SWEHB`
   - **Base URL**: `https://raw.githubusercontent.com/Oht8wooWi8yait9n/swehb/main/swehbvd_sitemap.xml`
   - **Scrape Method**: `sitemap`
3. Click **Create Connector**.

## Regenerating the Sitemap

```bash
python3 generate_swehbvd_sitemap.py
```
