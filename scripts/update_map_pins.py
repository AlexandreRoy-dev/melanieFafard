#!/usr/bin/env python3
"""Build / refresh transaction map pins for index.html.

- Keeps historical street-level pins (no civic numbers)
- Adds sold listings from data/properties.json as street-name-only pins
- Geocodes via Nominatim (cached) so pins land on the right street
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
PROPERTIES = ROOT / "data" / "properties.json"
PINS_OUT = ROOT / "data" / "transaction_pins.json"
CACHE_PATH = ROOT / "data" / "geocode_cache.json"
USER_AGENT = "MelanieFafardSiteMapPins/1.0 (contact@codesk.ca)"

AREA_CITY = {
    "Lévis": "Lévis, Québec",
    "Charlesbourg": "Charlesbourg, Québec",
    "Château-Richer": "Château-Richer, Québec",
    "Montmagny": "Montmagny, Québec",
    "Sainte-Marguerite": "Sainte-Marguerite, Québec",
    "Pont-Rouge": "Pont-Rouge, Québec",
    "Sainte-Foy": "Sainte-Foy, Québec",
    "Val-Bélair": "Val-Bélair, Québec",
    "Neuville": "Neuville, Québec",
    "Saint-Raphael": "Saint-Raphaël, Québec",
    "Cap-Rouge": "Cap-Rouge, Québec",
    "Saint-Agapit": "Saint-Agapit, Québec",
    "Québec": "Québec, Québec",
    "Saint-Nicolas": "Saint-Nicolas, Lévis, Québec",
    "Les Rivières": "Les Rivières, Québec",
    "Charny": "Charny, Lévis, Québec",
    "Saint-Augustin": "Saint-Augustin-de-Desmaures, Québec",
    "Beauport": "Beauport, Québec",
    "Vieux-Québec": "Vieux-Québec, Québec",
    "Saint-Apollinaire": "Saint-Apollinaire, Québec",
    "Saint-Roch": "Saint-Roch, Québec",
    "L'Ancienne-Lorette": "L'Ancienne-Lorette, Québec",
    "Lac-Beauport": "Lac-Beauport, Québec",
    "Portneuf": "Portneuf, Québec",
    "Neufchâtel": "Neufchâtel, Québec",
    "Lac-Saint-Charles": "Lac-Saint-Charles, Québec",
    "Saint-Henri": "Saint-Henri-de-Lévis, Québec",
    "Cap-Santé": "Cap-Santé, Québec",
    "Sillery": "Sillery, Québec",
    "Haute-Saint-Charles": "La Haute-Saint-Charles, Québec",
    "Saint-Bernard": "Saint-Bernard, Québec",
    "Saint-Gilles": "Saint-Gilles, Québec",
    "Limoilou": "Limoilou, Québec",
    "Chutes-de-la-Chaudière": "Les Chutes-de-la-Chaudière-Ouest, Lévis, Québec",
    "La Durantaye": "La Durantaye, Québec",
    "Stoneham": "Stoneham-et-Tewkesbury, Québec",
    "Aéroport": "Sainte-Foy, Québec",
    "Saint-Vallier": "Saint-Vallier, Québec",
    "Saint-Romuald": "Saint-Romuald, Lévis, Québec",
    "Saint-Damien": "Saint-Damien-de-Buckland, Québec",
    "Sainte-Catherine-de-la-JC": "Sainte-Catherine-de-la-Jacques-Cartier, Québec",
    "Beaupré": "Beaupré, Québec",
    "Saint-Jean-Chrysostome": "Saint-Jean-Chrysostome, Lévis, Québec",
    "Chutes-Montmorency": "Beauport, Québec",
}

ROAD_CLASSES = {"highway"}
ROAD_TYPES = {
    "residential",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
    "living_street",
    "service",
    "road",
    "trunk",
}

# Drop failed historical geocodes
DROP_TITLES = {"Cadastre du Québec"}

# Normalize abbreviated street titles for better geocoding
STREET_ALIASES = {
    "Boul. Ste-Anne": "Boulevard Sainte-Anne",
    "Boul Taché Ouest": "Boulevard Taché Ouest",
    "Av. Taniata": "Avenue Taniata",
    "Ave des Jésuites": "Avenue des Jésuites",
    "Av. Nordique": "Avenue Nordique",
    "Av. Maguire": "Avenue Maguire",
    "Av. Joffre": "Avenue Joffre",
    "Av. Royale": "Avenue Royale",
    "Av. du Golf-de-Bélair": "Avenue du Golf-de-Bélair",
    "Av. de la Rivière-Jaune": "Avenue de la Rivière-Jaune",
    "Ch. d'Azur": "Chemin d'Azur",
    "Ch. du Sault": "Chemin du Sault",
}

# Rough QuebecCity/Lévis metro bounds – reject far outliers (e.g. Montreal)
QC_BOUNDS = {
    "min_lat": 46.2,
    "max_lat": 47.6,
    "min_lng": -72.3,
    "max_lng": -69.8,
}



def street_name_only(address: str) -> str:
    """Remove civic / unit numbers; keep street name only."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    kept: list[str] = []
    for part in parts:
        # Pure/unit civic numbers: 1618, 1093A, 360-L6, 2106, 305, apt styles
        if re.fullmatch(r"\d+[A-Za-z]?(?:-\w+)?", part):
            continue
        if re.fullmatch(r"(?:app|apt|unit|suite|#)\s*\.?\s*\d+\w*", part, re.I):
            continue
        # Leading civic still glued: "1618 Rue Aladin"
        part = re.sub(r"^\d+[A-Za-z]?(?:-\w+)?\s+", "", part).strip()
        if part:
            kept.append(part)
    return ", ".join(kept) if kept else address.strip()


def area_from_listing(listing: dict) -> str:
    label = (listing.get("cityLabel") or "").strip()
    m = re.search(r"\(([^)]+)\)", label)
    if m:
        return m.group(1).strip()
    if label:
        return label
    city = (listing.get("city") or "").replace("-", " ").strip()
    return city.title() if city else "Québec"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def extract_index_pins(html: str) -> list[dict]:
    match = re.search(r"var properties = (\[.*?\]);", html, re.S)
    if not match:
        return []
    return json.loads(match.group(1))


def nominatim_search(session: requests.Session, query: str) -> list[dict]:
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 5,
        "countrycodes": "ca",
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    time.sleep(1.05)
    return resp.json()


def pick_result(results: list[dict], street: str, area: str) -> dict | None:
    street_l = street.lower()
    tokens = [t for t in re.split(r"[\s\-'.]+", street_l) if len(t) > 2]
    stop = {
        "rue",
        "avenue",
        "ave",
        "av",
        "boulevard",
        "boul",
        "chemin",
        "ch",
        "route",
        "montée",
        "montee",
        "carré",
        "carre",
        "des",
        "de",
        "du",
        "la",
        "le",
        "les",
    }
    tokens = [t for t in tokens if t not in stop]
    area_tok = area.lower().split(",")[0].strip()

    scored: list[tuple[float, dict]] = []
    for item in results:
        display = (item.get("display_name") or "").lower()
        score = 0.0
        if item.get("class") in ROAD_CLASSES:
            score += 5
        if item.get("type") in ROAD_TYPES:
            score += 3
        if item.get("class") == "place":
            score -= 4
        if "cadastre" in display:
            score -= 10
        for tok in tokens:
            if tok in display:
                score += 2
        if area_tok and area_tok in display:
            score += 2
        if "québec" in display or "quebec" in display or "lévis" in display or "levis" in display:
            score += 0.5
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] < 3:
        return None
    return scored[0][1]


def photon_search(session: requests.Session, query: str) -> list[dict]:
    """Fallback geocoder (OSM-based) when Nominatim is rate-limited."""
    params = {"q": query, "limit": 5, "lang": "fr"}
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode(params)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    time.sleep(0.35)
    features = resp.json().get("features") or []
    converted = []
    for feat in features:
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
        lng, lat = coords[0], coords[1]
        if lat is None or lng is None:
            continue
        parts = [
            props.get("name"),
            props.get("street"),
            props.get("city") or props.get("locality"),
            props.get("state"),
            props.get("country"),
        ]
        display = ", ".join(p for p in parts if p)
        osm_key = props.get("osm_key") or ""
        osm_value = props.get("osm_value") or ""
        converted.append(
            {
                "lat": lat,
                "lon": lng,
                "display_name": display,
                "class": osm_key,
                "type": osm_value,
            }
        )
    return converted


def in_qc_bounds(lat: float, lng: float) -> bool:
    return (
        QC_BOUNDS["min_lat"] <= lat <= QC_BOUNDS["max_lat"]
        and QC_BOUNDS["min_lng"] <= lng <= QC_BOUNDS["max_lng"]
    )


def geocode_title(title: str) -> str:
    return STREET_ALIASES.get(title, title)


def geocode(
    session: requests.Session,
    cache: dict,
    title: str,
    area: str,
    *,
    force: bool = False,
) -> tuple[float, float] | None:
    key = f"{title}|{area}"
    if not force and key in cache and cache[key]:
        cached = cache[key]
        if in_qc_bounds(float(cached["lat"]), float(cached["lng"])):
            return float(cached["lat"]), float(cached["lng"])

    city = AREA_CITY.get(area, f"{area}, Québec")
    search_title = geocode_title(title)
    queries = [
        f"{search_title}, {city}, Canada",
        f"{search_title}, {city}",
        f"{search_title}, Québec, QC, Canada",
    ]

    for query in queries:
        try:
            results = photon_search(session, query)
        except requests.RequestException as exc:
            print(f"  WARN photon error ({query}): {exc}")
            results = []
        # Prefer in-bounds quebec results
        filtered = []
        for item in results:
            try:
                lat, lng = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if in_qc_bounds(lat, lng):
                filtered.append(item)
        picked = pick_result(filtered or results, search_title, area) if results else None
        if picked:
            lat, lng = float(picked["lat"]), float(picked["lon"])
            if not in_qc_bounds(lat, lng):
                continue
            cache[key] = {"lat": lat, "lng": lng, "query": query, "source": "photon"}
            return lat, lng

    for query in queries:
        try:
            results = nominatim_search(session, query)
        except requests.RequestException as exc:
            print(f"  WARN nominatim error ({query}): {exc}")
            continue
        filtered = []
        for item in results:
            try:
                lat, lng = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if in_qc_bounds(lat, lng):
                filtered.append(item)
        picked = pick_result(filtered or results, search_title, area)
        if picked:
            lat, lng = float(picked["lat"]), float(picked["lon"])
            if not in_qc_bounds(lat, lng):
                continue
            cache[key] = {"lat": lat, "lng": lng, "query": query, "source": "nominatim"}
            return lat, lng

    cache[key] = None
    return None


def pin_key(pin: dict) -> tuple[str, str]:
    return (pin.get("title") or "").strip().lower(), (pin.get("area") or "").strip().lower()


def build_pins(session: requests.Session, cache: dict, *, regeocode: bool = False) -> list[dict]:
    existing: list[dict] = []
    if PINS_OUT.exists():
        existing = load_json(PINS_OUT, {}).get("pins") or []
    if not existing and INDEX.exists():
        existing = extract_index_pins(INDEX.read_text(encoding="utf-8"))

    pins: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for raw in existing:
        title = street_name_only(raw.get("title") or "")
        area = (raw.get("area") or "").strip()
        if not title or title in DROP_TITLES:
            continue
        key = (title.lower(), area.lower())
        if key in seen:
            continue
        seen.add(key)

        if regeocode:
            coords = geocode(session, cache, title, area)
            if coords:
                lat, lng = coords
            else:
                lat, lng = float(raw["lat"]), float(raw["lng"])
                print(f"  KEEP OLD coords for {title} / {area}")
        else:
            lat, lng = float(raw["lat"]), float(raw["lng"])

        pins.append(
            {
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "title": title,
                "area": area,
                "status": raw.get("status") or "transaction",
            }
        )

    # Sold listings from sync → street-only pins (always refresh coords)
    props = load_json(PROPERTIES, {})
    for listing in props.get("listings") or []:
        if not listing.get("sold"):
            continue
        title = street_name_only(listing.get("address") or "")
        area = area_from_listing(listing)
        if not title:
            continue
        key = (title.lower(), area.lower())

        print(f"Geocoding sold: {title} ({area})...")
        coords = geocode(session, cache, title, area, force=True)
        if not coords:
            print(f"  FAIL: could not geocode {title} / {area}")
            continue
        lat, lng = coords
        pin = {
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "title": title,
            "area": area,
            "status": "vendu",
            "uls": listing.get("uls"),
        }
        if key in seen:
            for i, existing_pin in enumerate(pins):
                if pin_key(existing_pin) == key:
                    pins[i] = pin
                    break
        else:
            seen.add(key)
            pins.append(pin)
        print(f"  -> {lat:.5f}, {lng:.5f}")

    return pins


def write_index_loader(pin_count: int) -> None:
    """Ensure index.html loads pins from data/transaction_pins.json."""
    html = INDEX.read_text(encoding="utf-8")

    new_block = """    // Pins loaded from data/transaction_pins.json (sold + historical, street name only)
    fetch('data/transaction_pins.json')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var properties = (data && data.pins) ? data.pins : [];
        properties.forEach(function(prop) {
          var badge = prop.status === 'vendu' ? 'VENDU' : 'TRANSACTION RÉUSSIE';
          var marker = L.marker([prop.lat, prop.lng], {icon: redIcon})
            .bindPopup(`
              <div class="text-center" style="font-family: inherit;">
                <div class="text-danger text-uppercase fw-bold mb-1" style="font-size: 10px; letter-spacing: 1px;">${prop.area}</div>
                <div class="fw-bold text-dark mb-2" style="font-size: 14px;">${prop.title}</div>
                <div class="badge bg-danger p-2 text-white">${badge}</div>
              </div>
            `);
          markers.addLayer(marker);
        });
        map.addLayer(markers);
      })
      .catch(function(err) {
        console.error('Map pins load failed', err);
      });
"""

    pattern = re.compile(
        r"\s*// Dataset with precise street-level accuracy\s*"
        r"var properties = \[.*?\];\s*"
        r"// Add properties to the Marker Cluster Group\s*"
        r"properties\.forEach\(function\(prop\) \{.*?\}\);\s*"
        r"// Add the Cluster Group to the Map\s*"
        r"map\.addLayer\(markers\);",
        re.S,
    )

    if not pattern.search(html):
        if "transaction_pins.json" in html:
            print("index.html already loads transaction_pins.json")
            return
        raise RuntimeError("Could not find map properties block in index.html")

    html = pattern.sub("\n" + new_block, html, count=1)
    INDEX.write_text(html, encoding="utf-8")
    print(f"Updated index.html map loader ({pin_count} pins)")


def run(*, regeocode: bool = False) -> int:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    cache = load_json(CACHE_PATH, {})

    print("Building transaction pins...")
    pins = build_pins(session, cache, regeocode=regeocode)
    save_json(CACHE_PATH, cache)
    payload = {
        "generatedFrom": "scripts/update_map_pins.py",
        "pinCount": len(pins),
        "pins": pins,
    }
    save_json(PINS_OUT, payload)
    print(f"Wrote {PINS_OUT} ({len(pins)} pins)")
    write_index_loader(len(pins))
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Update transaction map pins")
    parser.add_argument(
        "--regeocode",
        action="store_true",
        help="Re-geocode historical pins (slow; uses Photon/Nominatim)",
    )
    args = parser.parse_args()
    return run(regeocode=args.regeocode)


if __name__ == "__main__":
    raise SystemExit(main())
