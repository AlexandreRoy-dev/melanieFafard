#!/usr/bin/env python3
"""Sync Mélanie Fafard listings from Proprio Direct + Centris photo galleries.

Mirrors the CDF Centris sync flow:
1. Discover active listings from the broker Proprio Direct page
2. Download full photo galleries from Centris (fallback: Proprio Direct CDN)
3. Generate 1200x630 social share images
4. Write data/properties.json + data/listings_sync.json
5. Rebuild proprietes.html and SEO detail pages
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://melaniefafardimmo.com"
DEFAULT_AGENT_URL = "https://propriodirect.com/melanie-fafard"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
OG_WIDTH = 1200
OG_HEIGHT = 630


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "centre"


def http_get(url: str, session: requests.Session) -> requests.Response:
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp


def parse_agent_listings(html: str) -> list[dict]:
    parts = re.split(r'(?=<div class="card" data-listing-id=)', html)
    cards = [p for p in parts if p.startswith('<div class="card" data-listing-id=')]
    listings: list[dict] = []

    for card in cards:
        id_match = re.search(r'data-listing-id="(\d+)"', card)
        slug_match = re.search(r'data-slug-url="([^"]+)"', card)
        if not id_match or not slug_match:
            continue

        listing_id = id_match.group(1)
        slug = slug_match.group(1).strip()
        if not slug.startswith("/"):
            slug = "/" + slug

        sold = bool(re.search(r'class="message[^"]*\bsold\b', card))
        is_new = bool(re.search(r'class="message[^"]*new-listing', card))

        price_match = re.search(
            r'class="price"[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )
        address_match = re.search(
            r'class="address"[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )
        city_match = re.search(
            r'class="city_nbhd"[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )
        type_match = re.search(
            r'class="type"[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )
        size_match = re.search(
            r'class="size"[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )

        detail_bits = re.findall(
            r'class="details"[^>]*>\s*<span[^>]*>\s*([^<]+)',
            card,
            re.IGNORECASE,
        )
        if not detail_bits:
            # Fallback: sequential numbers near bath icons / svgs area
            detail_bits = re.findall(
                r'class="(?:bath|bed|rooms?)"[^>]*>\s*([^<]+)',
                card,
                re.IGNORECASE,
            )

        # Common Proprio Direct card: beds then baths as bare numbers inside .svgs
        numbers = re.findall(
            r'<div class="svgs[^"]*"[\s\S]*?</div>',
            card,
            re.IGNORECASE,
        )
        beds = baths = None
        if numbers:
            nums = re.findall(r">\s*(\d+)\s*<", numbers[0])
            if len(nums) >= 1:
                beds = nums[0]
            if len(nums) >= 2:
                baths = nums[1]

        imgs = re.findall(
            r'(?:data-src|src)="(https://cdn\.propriodirect\.com/properties/[^"]+)"',
            card,
        )
        seen: set[str] = set()
        photo_urls: list[str] = []
        for url in imgs:
            large = url.replace("/medium/", "/large/").replace("/small/", "/large/")
            if large not in seen:
                seen.add(large)
                photo_urls.append(large)

        price_raw = html_lib.unescape(price_match.group(1)).strip() if price_match else ""
        if sold:
            # Never expose sold listing prices on the site
            price_raw = ""

        listings.append(
            {
                "uls": listing_id,
                "slug": slug,
                "proprioUrl": "https://propriodirect.com" + slug.rstrip("/") + "/",
                "sold": sold,
                "isNew": is_new,
                "price": price_raw,
                "address": html_lib.unescape(address_match.group(1)).strip()
                if address_match
                else "",
                "city": html_lib.unescape(city_match.group(1)).strip()
                if city_match
                else "",
                "propertyType": html_lib.unescape(type_match.group(1)).strip()
                if type_match
                else "",
                "size": html_lib.unescape(size_match.group(1)).strip()
                if size_match
                else "",
                "beds": beds,
                "baths": baths,
                "photoUrls": photo_urls,
            }
        )

    return listings


def locality_to_city_sector(locality: str) -> tuple[str, str]:
    for prefix in ("quebec-", "levis-"):
        if locality.startswith(prefix):
            return prefix.rstrip("-"), locality[len(prefix) :]
    return locality, "centre"


def seo_fields_from_slug(slug: str, listing_id: str) -> dict:
    parts = [p for p in slug.strip("/").split("/") if p]
    if len(parts) < 4:
        street = f"inscription-{listing_id}"
        return {
            "country": "ca",
            "province": "qc",
            "city": "quebec",
            "sector": "centre",
            "street": street,
        }

    _region, locality, _ptype, street_id = parts[0], parts[1], parts[2], parts[3]
    city, sector = locality_to_city_sector(locality)
    street = re.sub(rf"-{re.escape(listing_id)}$", "", street_id) or street_id
    return {
        "country": "ca",
        "province": "qc",
        "city": slugify(city),
        "sector": slugify(sector),
        "street": slugify(street),
    }


def listing_public_path(listing: dict) -> str:
    return (
        f"/{listing['country']}/{listing['province']}/{listing['city']}/"
        f"{listing['sector']}/{listing['street']}/"
    )


def upgrade_photo_url(url: str, width: int = 1260, height: int = 1024) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    try:
        current_w = int(query.get("w", ["0"])[0])
    except ValueError:
        current_w = 0
    if current_w >= width:
        width = current_w
        height = int(query.get("h", [str(height)])[0])
    query["w"] = [str(width)]
    query["h"] = [str(height)]
    if "sm" in query:
        query["sm"] = ["c"]
    new_query = urllib.parse.urlencode({k: v[0] for k, v in query.items()})
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def extract_mosaic_photo_urls(html: str) -> list[str]:
    # Sold / missing Centris pages only expose the site logo as og:image
    if "listingnotfound" in html.lower() or "logo-centris-ca-social" in html.lower():
        return []

    match = re.search(r"window\.MosaicPhotoUrls\s*=\s*(\[[^\]]+\])", html)
    if match:
        raw = match.group(1).replace("\\u0026", "&")
        try:
            urls = json.loads(raw)
            if isinstance(urls, list) and urls:
                upgraded = []
                for index, url in enumerate(urls):
                    if is_centris_placeholder_url(url):
                        continue
                    if index == 0:
                        upgraded.append(upgrade_photo_url(url, width=1260, height=1024))
                    else:
                        upgraded.append(upgrade_photo_url(url, width=640, height=480))
                return upgraded
        except json.JSONDecodeError:
            pass

    og_match = re.search(
        r'<meta\s+property="og:image"\s+content="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    if og_match:
        url = og_match.group(1).replace("&amp;", "&")
        if not is_centris_placeholder_url(url):
            return [upgrade_photo_url(url)]
    return []


def is_centris_placeholder_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "logo-centris" in lowered or "/logos/" in lowered


def extract_proprio_photo_urls(html: str, listing_id: str) -> list[str]:
    """Pull full Proprio CDN gallery for one ULS (large size preferred)."""
    pattern = (
        rf"https://cdn\.propriodirect\.com/properties/{re.escape(listing_id)}/"
        r"(?:large|medium|small)/[^\"'?\s]+"
    )
    seen: set[str] = set()
    urls: list[str] = []
    for match in re.findall(pattern, html, flags=re.I):
        url = re.sub(r"/(?:medium|small)/", "/large/", match, count=1)
        url = url.split("?", 1)[0]
        if url not in seen:
            seen.add(url)
            urls.append(url)
    # Prefer numeric 001_, 002_ order when available
    def sort_key(u: str) -> tuple:
        m = re.search(r"/(\d{3})_", u)
        return (int(m.group(1)) if m else 9999, u)

    return sorted(urls, key=sort_key)


def extract_centris_meta(html: str) -> dict:
    title = None
    description = None
    og_image = None
    price = None

    m = re.search(
        r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE
    )
    if m:
        title = html_lib.unescape(m.group(1))

    m = re.search(
        r'<meta\s+property="og:description"\s+content="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    if m:
        description = html_lib.unescape(m.group(1))

    m = re.search(
        r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE
    )
    if m:
        og_image = m.group(1).replace("&amp;", "&")

    for block in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        html,
        re.IGNORECASE,
    ):
        price_match = re.search(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', block)
        if price_match:
            price = price_match.group(1)
            break

    return {
        "ogTitle": title,
        "description": description,
        "ogImage": og_image,
        "centrisPrice": price,
    }


def centris_urls_for_id(listing_id: str) -> list[str]:
    return [
        f"https://www.centris.ca/fr/propriete~a-vendre/{listing_id}",
        f"https://www.centris.ca/fr/propriete~a-louer/{listing_id}",
        f"https://www.centris.ca/fr/inscription/{listing_id}",
    ]


def fetch_centris_html(listing_id: str, session: requests.Session) -> str | None:
    for url in centris_urls_for_id(listing_id):
        try:
            resp = http_get(url, session)
            html = resp.text
            final = (resp.url or url).lower()
            if "listingnotfound" in final or "listingnotfound" in html.lower():
                continue
            if "MosaicPhotoUrls" in html:
                return html
            if 'property="og:image"' in html and "logo-centris" not in html.lower():
                return html
        except requests.RequestException:
            continue
    return None


HIGHLIGHT_LABELS = [
    "Année de construction",
    "Superficie habitable",
    "Superficie brute",
    "Aire habitable",
    "Niveau",
    "Frais de copropriété",
    "Facilité d'accès",
    "Stationnement (total)",
    "Stationnement",
    "Chambres à coucher",
    "Salles de bain",
    "Salles d'eau",
    "Garage",
    "Nombre de pièces",
]

DETAIL_LABELS = [
    "Équipement disponible",
    "Equipement disponible",
    "Appareils en location",
    "Toiture",
    "Zonage",
    "Mode de chauffage",
    "Garage",
    "Armoires",
    "Système d'égouts",
    "Systeme d'egouts",
    "Stationnement (total)",
    "Énergie pour le chauffage",
    "Energie pour le chauffage",
    "Fenêtres",
    "Fenetres",
    "Particularités",
    "Particularites",
    "Approvisionnement en eau",
    "Facilité d'accès",
    "Facilite d'acces",
    "Vue",
    "Piscine",
    "Foyer",
    "Climatisation",
    "Genre de propriété",
    "Type de bâtiment",
]


def html_to_lines(html: str) -> list[str]:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</(tr|li|p|h\d|div|td|th|section)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def slice_section(lines: list[str], start: str, ends: list[str]) -> list[str]:
    start_l = start.lower()
    end_set = {e.lower() for e in ends}
    begin = None
    for i, line in enumerate(lines):
        if line.lower() == start_l or line.lower().startswith(start_l + " "):
            begin = i + 1
            break
    if begin is None:
        return []
    out: list[str] = []
    for line in lines[begin:]:
        low = line.lower()
        if low in end_set:
            break
        out.append(line)
    return out


def pairs_from_labels(section_lines: list[str], labels: list[str]) -> dict[str, str]:
    label_map = {label.lower(): label for label in labels}
    result: dict[str, str] = {}
    i = 0
    while i < len(section_lines):
        line = section_lines[i]
        key = label_map.get(line.lower())
        if key and i + 1 < len(section_lines):
            value = section_lines[i + 1].strip()
            # skip if next line is also a known label
            if value.lower() not in label_map and value.lower() not in {
                "détails",
                "details",
                "inclusions",
                "exclusions",
                "inclus",
                "pièces",
                "pieces",
            }:
                result[key] = value
                i += 2
                continue
        i += 1
    return result


def parse_rooms(section_lines: list[str]) -> list[dict]:
    flooring_tokens = (
        "céramique",
        "ceramique",
        "bois",
        "flottant",
        "vinyle",
        "tapis",
        "béton",
        "beton",
        "marbre",
        "linoléum",
        "linoleum",
        "autre",
        "flexible",
    )
    rooms: list[dict] = []
    i = 0
    while i < len(section_lines) - 3:
        name, level, dims, flooring = section_lines[i : i + 4]
        level_l = level.lower()
        flooring_l = flooring.lower()
        has_floor = any(
            token in level_l
            for token in (
                "étage",
                "etage",
                "niveau",
                "rdc",
                "sous-sol",
                "rez-de",
                "ss",
            )
        ) or bool(re.search(r"\b\d+(er|ère|e|ieme|ième)?\b", level_l))
        has_dims = bool(re.search(r"\d", dims)) and (
            "x" in dims.lower() or "×" in dims or "p" in dims.lower()
        )
        has_flooring = any(token in flooring_l for token in flooring_tokens)
        if has_floor and has_dims and has_flooring:
            rooms.append(
                {
                    "name": name,
                    "level": level,
                    "dimensions": dims,
                    "flooring": flooring,
                }
            )
            i += 4
            continue
        i += 1
    return rooms


def parse_taxes(section_lines: list[str]) -> dict[str, str]:
    joined = "\n".join(section_lines)
    taxes: dict[str, str] = {}
    patterns = [
        (r"Taxes municipales[^\n]*\n\s*([\d][\d\s,\.]*\s*\$)", "Taxes municipales"),
        (r"Taxes scolaires[^\n]*\n\s*([\d][\d\s,\.]*\s*\$)", "Taxes scolaires"),
        (
            r"Évaluation municipale[^\n]*\n[\s\S]*?Terrain\n\s*([\d][\d\s,\.]*\s*\$)",
            "Terrain",
        ),
        (r"Bâtiment\n\s*([\d][\d\s,\.]*\s*\$)", "Bâtiment"),
        (
            r"Évaluation municipale[\s\S]*?Total\n\s*([\d][\d\s,\.]*\s*\$)",
            "Évaluation totale",
        ),
    ]
    # Also catch annual tax total that appears before assessment
    tax_total = re.search(
        r"Taxes scolaires[\s\S]*?Total\n\s*([\d][\d\s,\.]*\s*\$)",
        joined,
        re.I,
    )
    if tax_total:
        taxes["Total taxes"] = re.sub(r"\s+", " ", tax_total.group(1)).strip()

    for pattern, label in patterns:
        m = re.search(pattern, joined, re.I)
        if m:
            taxes[label] = re.sub(r"\s+", " ", m.group(1)).strip()
    return taxes


def parse_proprio_listing_html(html: str) -> dict:
    """Extract full listing details from a Proprio Direct property page."""
    detail: dict = {
        "description": "",
        "postalCode": "",
        "highlights": {},
        "details": {},
        "inclusions": "",
        "exclusions": "",
        "rooms": [],
        "taxes": {},
        "additionalInfo": "",
        "datePosted": "",
    }

    m = re.search(
        r'<meta\s+property="og:description"\s+content="([^"]+)"',
        html,
        re.I,
    )
    if m:
        detail["description"] = html_lib.unescape(m.group(1).replace("&amp;", "&"))

    for block in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>',
        html,
        re.I,
    ):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "RealEstateListing":
            detail["datePosted"] = str(data.get("datePosted") or "")
            entity = data.get("mainEntity") or {}
            address = entity.get("address") or {}
            if address.get("postalCode"):
                detail["postalCode"] = address["postalCode"]
            if not detail["description"] and data.get("description"):
                detail["description"] = data["description"]
            if entity.get("numberOfRooms") is not None:
                detail["bedsFromSchema"] = str(entity.get("numberOfRooms"))
            if entity.get("numberOfBathroomsTotal") is not None:
                detail["bathsFromSchema"] = str(entity.get("numberOfBathroomsTotal"))

    lines = html_to_lines(html)

    # Description paragraph after heading if OG missing
    if not detail["description"]:
        desc_lines = slice_section(
            lines, "Description", ["Points saillants", "Détails", "Pièces", "Inclus"]
        )
        if desc_lines:
            detail["description"] = " ".join(desc_lines[:3]).strip()

    highlight_lines = slice_section(
        lines,
        "Points saillants",
        ["Détails", "Details", "Pièces", "Pieces", "Inclus", "Coûts et évaluation"],
    )
    detail["highlights"] = pairs_from_labels(highlight_lines, HIGHLIGHT_LABELS)

    detail_lines = slice_section(
        lines,
        "Détails",
        ["Inclus", "Inclusions", "Exclusions", "Pièces", "Pieces", "Coûts et évaluation"],
    )
    if not detail_lines:
        detail_lines = slice_section(
            lines,
            "Details",
            ["Inclus", "Inclusions", "Exclusions", "Pièces", "Pieces", "Coûts et évaluation"],
        )
    detail["details"] = pairs_from_labels(detail_lines, DETAIL_LABELS)

    incl_lines = slice_section(
        lines,
        "Inclus",
        ["Exclusions", "Pièces", "Pieces", "Coûts et évaluation", "Info supplémentaire"],
    )
    if not incl_lines:
        incl_lines = slice_section(
            lines,
            "Inclusions",
            ["Exclusions", "Pièces", "Pieces", "Coûts et évaluation", "Info supplémentaire"],
        )
    if incl_lines:
        detail["inclusions"] = " ".join(incl_lines).strip()

    excl_lines = slice_section(
        lines,
        "Exclusions",
        ["Pièces", "Pieces", "Coûts et évaluation", "Info supplémentaire", "Inclus"],
    )
    if excl_lines:
        detail["exclusions"] = " ".join(excl_lines).strip()

    room_lines = slice_section(
        lines,
        "Pièces",
        ["Coûts et évaluation", "Taxes", "Info supplémentaire", "Style de vie"],
    )
    if not room_lines:
        room_lines = slice_section(
            lines,
            "Pieces",
            ["Coûts et évaluation", "Taxes", "Info supplémentaire", "Style de vie"],
        )
    detail["rooms"] = parse_rooms(room_lines)

    tax_lines = slice_section(
        lines,
        "Coûts et évaluation",
        ["Info supplémentaire", "Style de vie", "Propriétés suggérées", "Street view"],
    )
    if not tax_lines:
        tax_lines = slice_section(
            lines,
            "Taxes",
            ["Info supplémentaire", "Style de vie", "Propriétés suggérées"],
        )
    detail["taxes"] = parse_taxes(tax_lines)

    info_lines = slice_section(
        lines,
        "Info supplémentaire",
        ["Style de vie", "Propriétés suggérées", "Calculatrice hypothécaire", "Street view"],
    )
    if info_lines:
        # Keep broker disclaimer but clean whitespace
        detail["additionalInfo"] = " ".join(info_lines).strip()

    # Convenience aliases for cards/summary
    highlights = detail["highlights"]
    detail["yearBuilt"] = highlights.get("Année de construction", "")
    detail["livingArea"] = (
        highlights.get("Superficie habitable")
        or highlights.get("Aire habitable")
        or highlights.get("Superficie brute")
        or ""
    )
    detail["floorLevel"] = highlights.get("Niveau", "")
    detail["condoFees"] = highlights.get("Frais de copropriété", "")
    detail["parking"] = (
        highlights.get("Stationnement (total)")
        or highlights.get("Stationnement")
        or detail["details"].get("Stationnement (total)", "")
    )

    return detail


def fetch_proprio_detail(url: str, session: requests.Session) -> dict:
    try:
        html = http_get(url, session).text
    except requests.RequestException:
        return {}
    return parse_proprio_listing_html(html)


def download_bytes(url: str, session: requests.Session) -> bytes:
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def save_og_share_image(image_bytes: bytes, destination: Path) -> None:
    with Image.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        src_w, src_h = img.size
        target_ratio = OG_WIDTH / OG_HEIGHT
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            box = (left, 0, left + new_w, src_h)
        else:
            new_h = int(src_w / target_ratio)
            top = (src_h - new_h) // 2
            box = (0, top, src_w, top + new_h)

        cropped = img.crop(box).resize((OG_WIDTH, OG_HEIGHT), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(destination, format="JPEG", quality=88, optimize=True)


def cleanup_listing_folder(listing_dir: Path, saved_photos: list[str]) -> None:
    if not listing_dir.is_dir():
        return
    allowed = set(saved_photos) | {"og-share.jpg", "manifest.json"}
    for path in listing_dir.iterdir():
        if path.name in allowed:
            continue
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".webp", ".png"}:
            path.unlink()


def cleanup_stale_properties(images_root: Path, active_uls: set[str]) -> list[str]:
    removed: list[str] = []
    if not images_root.exists():
        return removed
    for path in sorted(images_root.iterdir()):
        if path.is_dir() and path.name.isdigit() and path.name not in active_uls:
            shutil.rmtree(path)
            removed.append(str(path))
        elif path.is_file() and path.stem.isdigit() and path.stem not in active_uls:
            path.unlink()
            removed.append(str(path))
    return removed


def sync_listing_images(
    listing: dict,
    session: requests.Session,
    images_root: Path,
) -> dict:
    listing_id = listing["uls"]
    print(f"Fetching gallery {listing_id}...")

    photo_urls: list[str] = []
    centris_meta: dict = {}
    source = "proprio"
    is_sold = bool(listing.get("sold"))

    # Active listings: prefer Centris mosaic. Sold ones are usually gone from Centris.
    if not is_sold:
        centris_html = fetch_centris_html(listing_id, session)
        if centris_html:
            photo_urls = extract_mosaic_photo_urls(centris_html)
            centris_meta = extract_centris_meta(centris_html)
            if photo_urls:
                source = "centris"

    # Proprio Direct CDN gallery (full set on detail page)
    if len(photo_urls) < 2:
        proprio_urls = list(listing.get("photoUrls") or [])
        # Card thumbnails are incomplete; scrape the detail page for sold / weak galleries
        detail_url = listing.get("proprioUrl")
        if detail_url and (is_sold or len(proprio_urls) < 2):
            try:
                detail_html = http_get(detail_url, session).text
                detail_photos = extract_proprio_photo_urls(detail_html, listing_id)
                if len(detail_photos) > len(proprio_urls):
                    proprio_urls = detail_photos
            except requests.RequestException as exc:
                print(f"  WARN: proprio detail photos failed: {exc}", file=sys.stderr)

        if proprio_urls and (is_sold or len(photo_urls) < 2):
            photo_urls = proprio_urls
            source = "proprio"

    if centris_meta.get("description") and not listing.get("description"):
        listing["description"] = centris_meta["description"]
    if centris_meta.get("ogTitle"):
        listing["centrisTitle"] = centris_meta["ogTitle"]

    listing_dir = images_root / listing_id
    listing_dir.mkdir(parents=True, exist_ok=True)

    saved_photos: list[str] = []
    first_bytes: bytes | None = None

    for index, photo_url in enumerate(photo_urls, start=1):
        filename = f"{index:02d}.jpg"
        dest = listing_dir / filename
        try:
            photo_bytes = download_bytes(photo_url, session)
            if len(photo_bytes) < 1024:
                raise requests.RequestException("empty or too-small image payload")
            # Skip obvious Centris logo placeholders if they slip through
            if is_centris_placeholder_url(photo_url):
                continue
            dest.write_bytes(photo_bytes)
            saved_photos.append(filename)
            if first_bytes is None:
                first_bytes = photo_bytes
            print(f"  downloaded {filename} ({source})")
        except requests.RequestException as exc:
            print(f"  WARN: failed {filename}: {exc}", file=sys.stderr)

    og_share = "og-share.jpg"
    if first_bytes:
        save_og_share_image(first_bytes, listing_dir / og_share)
        (images_root / f"{listing_id}.jpg").write_bytes(first_bytes)
        print(f"  wrote {og_share}")

    public_path = listing_public_path(listing)
    manifest = {
        "uls": listing_id,
        "photos": saved_photos,
        "ogShare": og_share if first_bytes else None,
        "count": len(saved_photos),
        "publicPath": public_path,
        "source": source,
        "ogImageUrl": (
            f"{BASE_URL}/assets/img/proprietes/{listing_id}/{og_share}"
            if first_bytes
            else None
        ),
    }
    (listing_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cleanup_listing_folder(listing_dir, saved_photos)

    return {
        "uls": listing_id,
        "photoCount": len(saved_photos),
        "photos": saved_photos,
        "source": source,
        "publicPath": public_path,
        "ogShareImage": (
            f"assets/img/proprietes/{listing_id}/{og_share}" if first_bytes else None
        ),
    }


def enrich_listing(raw: dict) -> dict:
    seo = seo_fields_from_slug(raw["slug"], raw["uls"])
    title = raw["address"] or f"Inscription {raw['uls']}"
    if raw.get("city"):
        share_title = f"{raw.get('propertyType') or 'Propriété'} - {title}, {raw['city']}"
    else:
        share_title = f"{raw.get('propertyType') or 'Propriété'} - {title}"

    size = raw.get("size") or raw.get("livingArea") or ""
    beds = raw.get("beds") or raw.get("bedsFromSchema") or ""
    baths = raw.get("baths") or raw.get("bathsFromSchema") or ""

    return {
        **seo,
        "uls": raw["uls"],
        "slug": raw["slug"],
        "proprioUrl": raw["proprioUrl"],
        "centrisUrl": f"https://www.centris.ca/fr/propriete~a-vendre/{raw['uls']}",
        "sold": raw["sold"],
        "isNew": raw["isNew"],
        "price": raw["price"],
        "address": raw["address"],
        "cityLabel": raw["city"],
        "propertyType": raw["propertyType"],
        "size": size,
        "beds": beds,
        "baths": baths,
        "description": raw.get("description") or "",
        "title": f"{title} - {raw['city']}" if raw.get("city") else title,
        "shareTitle": share_title,
        "fallbackImage": f"{raw['uls']}.jpg",
        "photoUrls": raw.get("photoUrls") or [],
        "postalCode": raw.get("postalCode") or "",
        "datePosted": raw.get("datePosted") or "",
        "yearBuilt": raw.get("yearBuilt") or "",
        "livingArea": raw.get("livingArea") or size,
        "floorLevel": raw.get("floorLevel") or "",
        "condoFees": raw.get("condoFees") or "",
        "parking": raw.get("parking") or "",
        "highlights": raw.get("highlights") or {},
        "details": raw.get("details") or {},
        "inclusions": raw.get("inclusions") or "",
        "exclusions": raw.get("exclusions") or "",
        "rooms": raw.get("rooms") or [],
        "taxes": raw.get("taxes") or {},
        "additionalInfo": raw.get("additionalInfo") or "",
    }


def write_properties_registry(listings: list[dict]) -> Path:
    payload = {
        "baseUrl": BASE_URL,
        "agentUrl": DEFAULT_AGENT_URL,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "listings": [
            {
                "uls": item["uls"],
                "country": item["country"],
                "province": item["province"],
                "city": item["city"],
                "sector": item["sector"],
                "street": item["street"],
                "title": item["title"],
                "shareTitle": item["shareTitle"],
                "price": item["price"],
                "address": item["address"],
                "cityLabel": item["cityLabel"],
                "propertyType": item["propertyType"],
                "size": item["size"],
                "beds": item["beds"],
                "baths": item["baths"],
                "sold": item["sold"],
                "isNew": item["isNew"],
                "description": item.get("description") or "",
                "proprioUrl": item["proprioUrl"],
                "centrisUrl": item["centrisUrl"],
                "fallbackImage": item["fallbackImage"],
                "publicPath": listing_public_path(item),
                "postalCode": item.get("postalCode") or "",
                "datePosted": item.get("datePosted") or "",
                "yearBuilt": item.get("yearBuilt") or "",
                "livingArea": item.get("livingArea") or "",
                "floorLevel": item.get("floorLevel") or "",
                "condoFees": item.get("condoFees") or "",
                "parking": item.get("parking") or "",
                "highlights": item.get("highlights") or {},
                "details": item.get("details") or {},
                "inclusions": item.get("inclusions") or "",
                "exclusions": item.get("exclusions") or "",
                "rooms": item.get("rooms") or [],
                "taxes": item.get("taxes") or {},
                "additionalInfo": item.get("additionalInfo") or "",
            }
            for item in listings
        ],
    }
    path = ROOT / "data" / "properties.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Proprio Direct listings + Centris galleries for Mélanie Fafard."
    )
    parser.add_argument("--agent-url", default=DEFAULT_AGENT_URL)
    parser.add_argument("--max-listings", type=int, default=30)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--include-sold",
        action="store_true",
        default=True,
        help="Sync sold listings from the broker page (default: on)",
    )
    parser.add_argument(
        "--exclude-sold",
        action="store_true",
        help="Only sync active listings (hide sold)",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Only sync images/JSON; do not rebuild HTML pages",
    )
    parser.add_argument(
        "--output-images-dir",
        default=str(ROOT / "assets" / "img" / "proprietes"),
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "data" / "listings_sync.json"),
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    print(f"Fetching agent page: {args.agent_url}")
    agent_html = http_get(args.agent_url, session).text
    discovered = parse_agent_listings(agent_html)
    if not discovered:
        raise RuntimeError("No listings found on Proprio Direct agent page.")

    include_sold = args.include_sold and not args.exclude_sold
    if not include_sold:
        active = [item for item in discovered if not item["sold"]]
        if active:
            discovered = active
        else:
            print("WARN: no active listings; keeping sold ones for sync")
            include_sold = True

    if args.max_listings > 0:
        discovered = discovered[: args.max_listings]

    print(f"Discovered {len(discovered)} listing(s):")
    for item in discovered:
        flag = "SOLD" if item["sold"] else "ACTIVE"
        print(f" - {item['uls']} [{flag}] {item['address']} - {item['price']}")

    enriched = [enrich_listing(item) for item in discovered]

    # Pull full Proprio Direct details (rooms, taxes, inclusions, etc.)
    for item in enriched:
        print(f"Fetching details {item['uls']}...")
        detail = fetch_proprio_detail(item["proprioUrl"], session)
        if not detail:
            time.sleep(0.4)
            continue
        if detail.get("description"):
            item["description"] = detail["description"]
        for key in (
            "postalCode",
            "datePosted",
            "yearBuilt",
            "livingArea",
            "floorLevel",
            "condoFees",
            "parking",
            "highlights",
            "details",
            "inclusions",
            "exclusions",
            "rooms",
            "taxes",
            "additionalInfo",
        ):
            if detail.get(key):
                item[key] = detail[key]
        if detail.get("livingArea") and not item.get("size"):
            item["size"] = detail["livingArea"]
        if detail.get("bedsFromSchema") and not item.get("beds"):
            item["beds"] = detail["bedsFromSchema"]
        if detail.get("bathsFromSchema") and not item.get("baths"):
            item["baths"] = detail["bathsFromSchema"]
        time.sleep(0.4)

    images_root = Path(args.output_images_dir)
    images_root.mkdir(parents=True, exist_ok=True)
    results = []

    for item in enriched:
        try:
            result = sync_listing_images(item, session, images_root)
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: failed listing {item['uls']}: {exc}", file=sys.stderr)
            results.append({"uls": item["uls"], "error": str(exc)})
        time.sleep(args.delay_seconds)

    active_uls = {item["uls"] for item in enriched}
    removed = cleanup_stale_properties(images_root, active_uls)

    registry_path = write_properties_registry(enriched)
    print(f"Wrote {registry_path}")

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "agentUrl": args.agent_url,
        "includeSold": include_sold,
        "maxListings": args.max_listings,
        "removedStale": removed,
        "listings": results,
    }
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {output_json}")

    if not args.skip_generate:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from generate_property_pages import generate_all

        generate_all()

        try:
            from update_map_pins import run as update_map_pins

            update_map_pins()
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: map pins update failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
