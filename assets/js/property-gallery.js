(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function initPropertyGallery() {
    var root = document.querySelector(".property-media");
    if (!root) return;

    var uls = root.getAttribute("data-uls");
    var fallback = root.getAttribute("data-fallback-image") || "";
    var assetsBase = root.getAttribute("data-assets-base") || "/assets/img/proprietes/";
    var main = byId("property-gallery-main");
    var thumbs = byId("property-gallery-thumbs");
    var counter = byId("property-gallery-counter");
    var prevBtn = byId("property-gallery-prev");
    var nextBtn = byId("property-gallery-next");
    if (!main || !thumbs || !counter) return;

    var photos = [];
    var activeIndex = 0;

    function basePath() {
      return assetsBase + uls + "/";
    }

    function setPhoto(index) {
      if (!photos.length) return;
      activeIndex = (index + photos.length) % photos.length;
      main.src = basePath() + photos[activeIndex];
      main.alt = root.getAttribute("data-share-title") || "Photo de la propriété";
      counter.textContent = activeIndex + 1 + " / " + photos.length;
      thumbs.querySelectorAll("[data-index]").forEach(function (btn) {
        btn.classList.toggle("is-active", Number(btn.getAttribute("data-index")) === activeIndex);
      });
    }

    function renderThumbs() {
      thumbs.innerHTML = "";
      photos.forEach(function (file, index) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.setAttribute("data-index", String(index));
        btn.className = "gallery-thumb";
        btn.innerHTML =
          '<img src="' +
          basePath() +
          file +
          '" alt="" loading="lazy">';
        btn.addEventListener("click", function () {
          setPhoto(index);
        });
        thumbs.appendChild(btn);
      });
    }

    function useFallback() {
      photos = [];
      if (fallback) {
        main.src = fallback;
      }
      counter.textContent = "1 / 1";
      thumbs.innerHTML =
        '<p class="gallery-empty">Galerie complète bientôt disponible.</p>';
    }

    fetch(basePath() + "manifest.json", { cache: "no-store" })
      .then(function (resp) {
        if (!resp.ok) throw new Error("manifest missing");
        return resp.json();
      })
      .then(function (manifest) {
        photos = Array.isArray(manifest.photos) ? manifest.photos : [];
        if (!photos.length) {
          useFallback();
          return;
        }
        renderThumbs();
        setPhoto(0);
      })
      .catch(function () {
        useFallback();
      });

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        setPhoto(activeIndex - 1);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        setPhoto(activeIndex + 1);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPropertyGallery);
  } else {
    initPropertyGallery();
  }
})();
