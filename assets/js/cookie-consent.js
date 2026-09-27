/**
 * Cookie consent + gated Google Ads tag (AW-17751777472)
 * Values in localStorage key "cookieConsent": "accepted" | "rejected"
 */
(function () {
  var KEY = "cookieConsent";
  var ADS_ID = "AW-17751777472";
  var PRIVACY_HREF = (function () {
    var scripts = document.getElementsByTagName("script");
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].src || "";
      if (src.indexOf("cookie-consent.js") !== -1) {
        return src.replace(/assets\/js\/cookie-consent\.js.*$/, "politique-de-confidentialite.html");
      }
    }
    return "politique-de-confidentialite.html";
  })();

  function loadAnalytics() {
    if (window.__mfAdsLoaded) return;
    window.__mfAdsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag =
      window.gtag ||
      function () {
        window.dataLayer.push(arguments);
      };
    window.gtag("js", new Date());
    window.gtag("config", ADS_ID);
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + ADS_ID;
    document.head.appendChild(s);
  }

  function ensureBanner() {
    if (document.getElementById("cookie-consent")) return document.getElementById("cookie-consent");

    var banner = document.createElement("div");
    banner.id = "cookie-consent";
    banner.className = "cookie-consent";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-live", "polite");
    banner.setAttribute("aria-label", "Bannière de consentement aux cookies");
    banner.innerHTML =
      '<div class="cc-inner">' +
      '<p class="cc-title">Respect de votre vie privée</p>' +
      "<p class=\"cc-text\">Nous utilisons des cookies pour améliorer votre expérience et mesurer la performance du site " +
      '(publicité Google). <a href="' +
      PRIVACY_HREF +
      '#temoins">En savoir plus</a>.</p>' +
      '<div class="cc-actions">' +
      '<button type="button" id="cc-accept" class="cc-btn cc-btn-accept">Accepter</button>' +
      '<button type="button" id="cc-decline" class="cc-btn cc-btn-decline">Refuser</button>' +
      "</div>" +
      '<p class="cc-small">Vous pourrez modifier votre choix en effaçant les données du site.</p>' +
      "</div>";
    document.body.appendChild(banner);
    return banner;
  }

  function hideBanner(banner) {
    banner.classList.remove("show");
  }

  function showBanner(banner) {
    banner.classList.add("show");
  }

  function init() {
    var banner = ensureBanner();
    var consent = localStorage.getItem(KEY);

    document.getElementById("cc-accept").addEventListener("click", function () {
      localStorage.setItem(KEY, "accepted");
      hideBanner(banner);
      loadAnalytics();
    });

    document.getElementById("cc-decline").addEventListener("click", function () {
      localStorage.setItem(KEY, "rejected");
      hideBanner(banner);
    });

    if (consent === "accepted") {
      loadAnalytics();
      return;
    }
    if (consent === "rejected") {
      return;
    }
    showBanner(banner);
  }

  window.shouldLoadAnalytics = function () {
    return localStorage.getItem(KEY) === "accepted";
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
