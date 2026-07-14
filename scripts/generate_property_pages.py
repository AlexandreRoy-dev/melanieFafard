#!/usr/bin/env python3
"""Generate proprietes.html + SEO detail pages from data/properties.json."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://melaniefafardimmo.com"


def load_registry() -> dict:
    return json.loads((ROOT / "data" / "properties.json").read_text(encoding="utf-8"))


def public_path(listing: dict) -> str:
    return listing.get("publicPath") or (
        f"/{listing['country']}/{listing['province']}/{listing['city']}/"
        f"{listing['sector']}/{listing['street']}/"
    )


def asset_prefix(depth: int) -> str:
    return "../" * depth if depth else ""


def site_chrome(active: str, depth: int = 0) -> tuple[str, str]:
    p = asset_prefix(depth)
    nav_items = [
        ("accueil", f"{p}index.html", "Accueil"),
        ("apropos", f"{p}apropos.html", "À propos"),
        ("proprietes", f"{p}proprietes.html", "Propriétés"),
        ("services", f"{p}services.html", "Services"),
        ("programmes", f"{p}programmes.html", "Programmes"),
        ("temoignages", f"{p}temoignages.html", "Témoignages"),
        ("contact", f"{p}index.html#contact", "Contact"),
    ]

    def nav_class(key: str) -> str:
        return ' class="active"' if key == active else ""

    links = "\n".join(
        f'          <li><a href="{href}"{nav_class(key)}>{label}</a></li>'
        for key, href, label in nav_items
    )

    header = f"""<header id="header" class="header d-flex align-items-center fixed-top">
  <div class="container-fluid position-relative d-flex align-items-center justify-content-between">
    <a href="{p}index.html" class="logo d-flex align-items-center me-auto me-xl-0">
      <img src="{p}assets/img/logo.svg" alt="Mélanie Fafard" class="header-logo">
    </a>
    <nav id="navmenu" class="navmenu">
      <ul>
{links}
        <li class="d-xl-none mt-3 text-center">
          <div class="mobile-social-group">
            <span class="d-block mb-2 text-muted small">Suivez-moi</span>
            <a href="https://www.facebook.com/profile.php?id=61575817391811" class="mx-2"><i class="bi bi-facebook"></i></a>
            <a href="https://www.instagram.com/melaniefafardimmo/" class="mx-2"><i class="bi bi-instagram"></i></a>
            <a href="https://x.com/mfafardimmo" class="mx-2"><i class="bi bi-twitter"></i></a>
            <a href="https://www.linkedin.com/in/m%C3%A9lanie-fafard-b595672a9/" class="mx-2"><i class="bi bi-linkedin"></i></a>
          </div>
        </li>
      </ul>
      <i class="mobile-nav-toggle d-xl-none bi bi-list"></i>
    </nav>
    <div class="header-social-links d-flex align-items-center">
      <div class="d-none d-xl-flex align-items-center">
        <a href="tel:5813054442" class="desktop-phone me-4">(581) 305-4442</a>
        <a href="https://www.facebook.com/profile.php?id=61575817391811" class="channel-link"><i class="bi bi-facebook"></i></a>
        <a href="https://www.instagram.com/melaniefafardimmo/" class="channel-link"><i class="bi bi-instagram"></i></a>
        <a href="https://x.com/mfafardimmo" class="channel-link"><i class="bi bi-twitter"></i></a>
        <a href="https://www.linkedin.com/in/m%C3%A9lanie-fafard-b595672a9/" class="channel-link"><i class="bi bi-linkedin"></i></a>
      </div>
      <a href="tel:5813054442" class="mobile-phone-red d-xl-none"><i class="bi bi-telephone-fill"></i></a>
    </div>
  </div>
</header>"""

    footer = f"""<footer id="footer" class="footer dark-background">
  <div class="container footer-top">
    <div class="row gy-4">
      <div class="col-lg-4 col-md-6 footer-about">
        <a href="{p}index.html" class="d-flex align-items-center"><span class="sitename">Mélanie Fafard</span></a>
        <div class="footer-contact pt-3">
          <p>Québec &amp; Lévis</p>
          <p>Secteurs résidentiels et investissements</p>
          <p class="mt-3"><strong>Téléphone :</strong> <a class="footer-link-accent" href="tel:+15813054442">(581) 305-4442</a></p>
          <p><strong>Courriel :</strong> <a class="footer-link-accent" href="mailto:mfafardimmobilier@gmail.com">mfafardimmobilier@gmail.com</a></p>
        </div>
      </div>
      <div class="col-lg-2 col-md-3 footer-links">
        <h4>Navigation</h4>
        <ul>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}index.html#hero">Accueil</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}apropos.html">À propos</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}proprietes.html">Propriétés</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}temoignages.html">Témoignages</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}index.html#contact">Contact</a></li>
        </ul>
      </div>
      <div class="col-lg-2 col-md-3 footer-links">
        <h4>Types de projets</h4>
        <ul>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}services.html#vente">Vente résidentielle</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}services.html#achat">Achat de propriété</a></li>
          <li><i class="bi bi-chevron-right"></i> <a href="{p}services.html#eval">Évaluation de propriété</a></li>
        </ul>
      </div>
      <div class="col-lg-4 col-md-12">
        <h4>Suivez-moi</h4>
        <p>Pour découvrir les nouveautés, propriétés, conseils et coulisses de mon travail de courtière immobilière.</p>
        <div class="social-links d-flex">
          <a href="https://www.facebook.com/profile.php?id=61575817391811" class="channel-link"><i class="bi bi-facebook"></i></a>
          <a href="https://www.instagram.com/melaniefafardimmo/" class="channel-link"><i class="bi bi-instagram"></i></a>
          <a href="https://x.com/mfafardimmo" class="channel-link"><i class="bi bi-twitter"></i></a>
          <a href="https://www.linkedin.com/in/m%C3%A9lanie-fafard-b595672a9/" class="channel-link"><i class="bi bi-linkedin"></i></a>
        </div>
      </div>
    </div>
  </div>
  <div class="container copyright text-center mt-4">
    <p>© <span>Copyright</span> <strong class="px-1 sitename">Mélanie Fafard</strong> <span>Tous droits réservés</span> - Conception web par <a href="https://roymarketing.ca/">Roy Marketing</a></p>
  </div>
</footer>
<a href="#" id="scroll-top" class="scroll-top d-flex align-items-center justify-content-center"><i class="bi bi-arrow-up-short"></i></a>
<div id="preloader"></div>
<script src="{p}assets/vendor/bootstrap/js/bootstrap.bundle.min.js"></script>
<script src="{p}assets/vendor/aos/aos.js"></script>
<script src="{p}assets/vendor/swiper/swiper-bundle.min.js"></script>
<script src="{p}assets/vendor/glightbox/js/glightbox.min.js"></script>
<script src="{p}assets/js/main.js"></script>
<a href="https://m.me/melanie.fafard.865146" class="messenger-float" target="_blank" title="Discuter sur Messenger"><i class="bi bi-messenger"></i></a>"""

    return header, footer


def head_block(
    *,
    title: str,
    description: str,
    canonical: str,
    og_image: str,
    depth: int = 0,
    extra: str = "",
) -> str:
    p = asset_prefix(depth)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta content="width=device-width, initial-scale=1.0" name="viewport">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <link href="{p}assets/img/favicon.svg" rel="icon">
  <link href="{p}assets/img/favicon.svg" rel="apple-touch-icon">
  <link href="https://fonts.googleapis.com" rel="preconnect">
  <link href="https://fonts.gstatic.com" rel="preconnect" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap" rel="stylesheet">
  <link href="{p}assets/vendor/bootstrap/css/bootstrap.min.css" rel="stylesheet">
  <link href="{p}assets/vendor/bootstrap-icons/bootstrap-icons.css" rel="stylesheet">
  <link href="{p}assets/vendor/aos/aos.css" rel="stylesheet">
  <link href="{p}assets/vendor/swiper/swiper-bundle.min.css" rel="stylesheet">
  <link href="{p}assets/vendor/glightbox/css/glightbox.min.css" rel="stylesheet">
  <link href="{p}assets/css/main.css" rel="stylesheet">
  <link href="{p}assets/css/properties.css" rel="stylesheet">
  <link rel="canonical" href="{escape(canonical)}">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:image" content="{escape(og_image)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:type" content="image/jpeg">
  <meta property="og:url" content="{escape(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="fr_CA">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="{escape(og_image)}">
{extra}
</head>"""


def listing_card_html(listing: dict, depth: int = 0) -> str:
    p = asset_prefix(depth)
    href = public_path(listing)
    img = f"{p}assets/img/proprietes/{listing['fallbackImage']}"
    badge = ""
    if listing.get("sold"):
        badge = '<span class="prop-badge sold">Vendu</span>'
    elif listing.get("isNew"):
        badge = '<span class="prop-badge new">Nouveauté</span>'

    meta_bits = []
    if listing.get("beds"):
        meta_bits.append(
            f'<span><i class="bi bi-door-closed"></i> {escape(str(listing["beds"]))} ch.</span>'
        )
    if listing.get("baths"):
        meta_bits.append(
            f'<span><i class="bi bi-droplet"></i> {escape(str(listing["baths"]))} sdb</span>'
        )
    if listing.get("size"):
        meta_bits.append(
            f'<span><i class="bi bi-bounding-box"></i> {escape(str(listing["size"]))}</span>'
        )

    return f"""
        <div class="col-lg-4 col-md-6" data-aos="fade-up">
          <article class="prop-card h-100">
            <a href="{escape(href)}" class="prop-card-media">
              <img src="{escape(img)}" alt="{escape(listing.get('title') or listing.get('address') or '')}" loading="lazy">
              {badge}
            </a>
            <div class="prop-card-body">
              <span class="prop-subtitle mb-1">{escape(listing.get('propertyType') or 'Propriété')}</span>
              <p class="prop-price">{escape(listing.get('price') or '')}</p>
              <h3 class="prop-address">{escape(listing.get('address') or '')}</h3>
              <p class="prop-city">{escape(listing.get('cityLabel') or '')}</p>
              <div class="prop-meta">{''.join(meta_bits)}</div>
              <a href="{escape(href)}" class="prop-cta">Voir la fiche <i class="bi bi-arrow-right ms-1"></i></a>
            </div>
          </article>
        </div>"""


def generate_listings_page(registry: dict) -> None:
    header, footer = site_chrome("proprietes", depth=0)
    listings = registry.get("listings", [])
    active = [x for x in listings if not x.get("sold")]
    sold = [x for x in listings if x.get("sold")]
    ordered = active + sold

    cards = "\n".join(listing_card_html(item, depth=0) for item in ordered) or (
        '<div class="col-12"><p class="text-center text-muted">Aucune propriété à afficher pour le moment.</p></div>'
    )

    description = (
        "Découvrez les propriétés en vigueur de Mélanie Fafard, courtière immobilière "
        "Proprio Direct à Québec et Lévis."
    )
    og_image = f"{BASE_URL}/assets/img/herobanner.webp"
    if ordered:
        og_image = (
            f"{BASE_URL}/assets/img/proprietes/{ordered[0]['uls']}/og-share.jpg"
        )

    html = f"""{head_block(
        title="Propriétés – Mélanie Fafard, courtière immobilière",
        description=description,
        canonical=f"{BASE_URL}/proprietes.html",
        og_image=og_image,
        depth=0,
    )}
<body class="proprietes-page">
{header}
<main class="main">
  <section class="properties-title-section">
    <div class="container" data-aos="fade-up">
      <div class="section-title-wrapper text-center">
        <h1 class="title-with-lines">Propriétés</h1>
        <p>Découvrez mes inscriptions actuelles à Québec, Lévis et les environs.</p>
      </div>
    </div>
  </section>
  <section class="section properties-grid pt-0">
    <div class="container">
      <div class="row gy-4 gx-4">
{cards}
      </div>
      <div class="text-center properties-external-link" data-aos="fade-up">
        <a href="https://propriodirect.com/melanie-fafard" target="_blank" rel="noopener" class="btn-outline">
          Voir aussi sur Proprio Direct
        </a>
      </div>
    </div>
  </section>
</main>
{footer}
</body>
</html>
"""
    (ROOT / "proprietes.html").write_text(html, encoding="utf-8")
    print("wrote proprietes.html")


def generate_detail_page(listing: dict) -> None:
    depth = 5  # /ca/qc/city/sector/street/index.html
    header, footer = site_chrome("proprietes", depth=depth)
    p = asset_prefix(depth)
    path = public_path(listing)
    canonical = BASE_URL + path
    og_image = f"{BASE_URL}/assets/img/proprietes/{listing['uls']}/og-share.jpg"
    fallback = f"{p}assets/img/proprietes/{listing['fallbackImage']}"
    description = listing.get("description") or listing.get("shareTitle") or listing.get("title")
    if len(description) > 300:
        description = description[:297].rstrip() + "…"

    badge = ""
    if listing.get("sold"):
        badge = '<span class="prop-badge sold">Vendu</span>'
    elif listing.get("isNew"):
        badge = '<span class="prop-badge new">Nouveauté</span>'

    meta_rows = []
    if listing.get("beds"):
        meta_rows.append(f"<li><strong>Chambres</strong><span>{escape(str(listing['beds']))}</span></li>")
    if listing.get("baths"):
        meta_rows.append(
            f"<li><strong>Salles de bain</strong><span>{escape(str(listing['baths']))}</span></li>"
        )
    if listing.get("size"):
        meta_rows.append(
            f"<li><strong>Superficie</strong><span>{escape(str(listing['size']))}</span></li>"
        )
    meta_rows.append(
        f"<li><strong>Inscription</strong><span>{escape(str(listing['uls']))}</span></li>"
    )

    city_label = listing["city"].replace("-", " ").title()
    sector_label = listing["sector"].replace("-", " ").title()

    body = f"""{head_block(
        title=listing.get("shareTitle") or listing.get("title") or "Propriété",
        description=description,
        canonical=canonical,
        og_image=og_image,
        depth=depth,
    )}
<body class="property-details-page">
{header}
<main class="main">
  <section class="section property-detail">
    <div class="container" data-aos="fade-up">
      <nav class="prop-breadcrumb" aria-label="Fil d'Ariane">
        <a href="{p}proprietes.html">Propriétés</a>
        <span>/</span>
        <span>{escape(city_label)}</span>
        <span>/</span>
        <span>{escape(sector_label)}</span>
      </nav>

      <div class="row gy-4 gx-lg-4 align-items-start">
        <div class="col-lg-7" data-aos="fade-up" data-aos-delay="50">
          <section class="property-media"
            data-uls="{escape(listing['uls'])}"
            data-share-title="{escape(listing.get('shareTitle') or '')}"
            data-share-url="{escape(canonical)}"
            data-share-image="{escape(og_image)}"
            data-fallback-image="{escape(fallback)}"
            data-assets-base="{p}assets/img/proprietes/">
            <div class="property-gallery">
              <div class="gallery-main-wrap">
                <img id="property-gallery-main" src="{escape(fallback)}" alt="{escape(listing.get('title') or '')}">
                <button type="button" id="property-gallery-prev" aria-label="Photo précédente"><i class="bi bi-chevron-left"></i></button>
                <button type="button" id="property-gallery-next" aria-label="Photo suivante"><i class="bi bi-chevron-right"></i></button>
                <span id="property-gallery-counter">1 / 1</span>
                {badge}
              </div>
              <div id="property-gallery-thumbs" class="gallery-thumbs"></div>
            </div>
            <div class="property-share">
              <p>Partager cette propriété</p>
              <div id="property-share-buttons"></div>
            </div>
          </section>
        </div>
        <div class="col-lg-5" data-aos="fade-up" data-aos-delay="120">
          <div class="property-summary">
            <span class="prop-subtitle">{escape(listing.get('propertyType') or 'Propriété')}</span>
            <p class="prop-price">{escape(listing.get('price') or '')}</p>
            <h1>{escape(listing.get('address') or listing.get('title') or '')}</h1>
            <p class="prop-city">{escape(listing.get('cityLabel') or '')}</p>
            <ul class="property-facts">
              {''.join(meta_rows)}
            </ul>
            <div class="property-actions">
              <a class="btn-primary" href="{p}index.html#contact">Demander une visite</a>
              <a class="btn-outline" href="{escape(listing.get('proprioUrl') or '#')}" target="_blank" rel="noopener">Voir sur Proprio Direct</a>
              <a class="btn-outline" href="{escape(listing.get('centrisUrl') or '#')}" target="_blank" rel="noopener">Voir sur Centris</a>
            </div>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="col-lg-10" data-aos="fade-up" data-aos-delay="80">
          <div class="property-description">
            <span class="prop-subtitle">À propos</span>
            <h2>Description de la propriété</h2>
            <p>{escape(listing.get('description') or 'Description à venir.')}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</main>
{footer}
<script src="{p}assets/js/property-gallery.js" defer></script>
<script src="{p}assets/js/property-share.js" defer></script>
</body>
</html>
"""

    dest_dir = (
        ROOT
        / listing["country"]
        / listing["province"]
        / listing["city"]
        / listing["sector"]
        / listing["street"]
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "index.html").write_text(body, encoding="utf-8")
    print(f"wrote {dest_dir.relative_to(ROOT) / 'index.html'}")


def prune_stale_detail_pages(registry: dict) -> None:
    active_paths = {
        (
            listing["country"],
            listing["province"],
            listing["city"],
            listing["sector"],
            listing["street"],
        )
        for listing in registry.get("listings", [])
    }
    ca_root = ROOT / "ca" / "qc"
    if not ca_root.exists():
        return
    for index in ca_root.rglob("index.html"):
        rel = index.relative_to(ROOT)
        parts = rel.parts
        if len(parts) != 6:
            continue
        key = parts[:5]
        if key not in active_paths:
            index.unlink()
            # clean empty parents
            parent = index.parent
            for _ in range(5):
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            print(f"removed stale {rel}")


def update_nav_links() -> None:
    """Point nav 'Propriétés' items to the local listings page."""
    targets = [
        "https://propriodirect.com/melanie-fafard",
        "https://www.centris.ca/fr/courtier-immobilier~melanie-fafard~proprio-direct/h9548",
    ]
    pattern = re.compile(
        r'(<li>\s*<a href=")(?:'
        + "|".join(re.escape(t) for t in targets)
        + r')(">\s*Propriétés\s*</a>\s*</li>)',
        re.IGNORECASE,
    )
    for path in ROOT.glob("*.html"):
        if path.name == "proprietes.html":
            continue
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub(r'\1proprietes.html\2', text)
        # Homepage CTA that sent users off-site for properties
        updated = re.sub(
            r'<a href="https://propriodirect\.com/melanie-fafard"\s+target="_blank"\s+(class="btn btn-danger[^"]*")',
            r'<a href="proprietes.html" \1',
            updated,
            count=1,
        )
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"updated Propriétés links in {path.name}")


def generate_all() -> None:
    registry = load_registry()
    generate_listings_page(registry)
    for listing in registry.get("listings", []):
        generate_detail_page(listing)
    prune_stale_detail_pages(registry)
    update_nav_links()


if __name__ == "__main__":
    generate_all()
