# Proprio Direct → Centris listing sync

Discovers listings from [Mélanie’s Proprio Direct page](https://propriodirect.com/melanie-fafard), downloads full photo galleries from Centris (fallback: Proprio Direct CDN), generates a **1200×630** social share image per property, rebuilds `proprietes.html` + SEO detail pages, and can run daily via GitHub Actions.

This mirrors the CDF Centris sync / property gallery setup.

## Generated files

- `data/properties.json`
- `data/listings_sync.json`
- `assets/img/proprietes/<uls>/01.jpg`, `02.jpg`, …
- `assets/img/proprietes/<uls>/og-share.jpg`
- `assets/img/proprietes/<uls>/manifest.json`
- `assets/img/proprietes/<uls>.jpg` (hero / card image)
- `proprietes.html`
- `/ca/qc/{city}/{sector}/{street}/`

## Run manually

From the project root:

```bash
pip install -r scripts/requirements.txt
python scripts/proprio_sync.py --max-listings 30
```

Include sold listings shown on the broker page:

```bash
python scripts/proprio_sync.py --include-sold
```

Rebuild HTML only (after editing `data/properties.json`):

```bash
python scripts/generate_property_pages.py
```

## GitHub Actions

Workflow: `.github/workflows/proprio-sync.yml`

- Runs daily at 08:00 Eastern
- Also available via **Actions → Sync Proprio Direct listings → Run workflow**

### Optional repository variable

| Name | Purpose |
|------|---------|
| `PROPRIO_AGENT_URL` | Override scrape URL (default: `https://propriodirect.com/melanie-fafard`) |

## Notes

- Active (non-sold) listings are synced by default.
- Centris `window.MosaicPhotoUrls` is preferred for galleries; Proprio Direct large CDN images are the fallback.
- Nav “Propriétés” links point to `proprietes.html` on this site.
