(function () {
  function encode(value) {
    return encodeURIComponent(value || "");
  }

  function iconHtml(name) {
    return '<i class="bi ' + name + '" aria-hidden="true"></i>';
  }

  function initPropertyShare() {
    var root = document.querySelector(".property-media");
    var container = document.getElementById("property-share-buttons");
    if (!root || !container) return;

    var shareUrl = root.getAttribute("data-share-url") || window.location.href;
    var shareTitle = root.getAttribute("data-share-title") || document.title;
    var shareImage = root.getAttribute("data-share-image") || "";
    var shareText = shareTitle;

    var networks = [
      {
        id: "facebook",
        label: "Partager sur Facebook",
        icon: "bi-facebook",
        className: "share-btn share-facebook",
        href: "https://www.facebook.com/sharer/sharer.php?u=" + encode(shareUrl),
      },
      {
        id: "x",
        label: "Partager sur X",
        icon: "bi-twitter-x",
        className: "share-btn share-x",
        href:
          "https://twitter.com/intent/tweet?url=" +
          encode(shareUrl) +
          "&text=" +
          encode(shareText),
      },
      {
        id: "linkedin",
        label: "Partager sur LinkedIn",
        icon: "bi-linkedin",
        className: "share-btn share-linkedin",
        href:
          "https://www.linkedin.com/sharing/share-offsite/?url=" + encode(shareUrl),
      },
      {
        id: "pinterest",
        label: "Partager sur Pinterest",
        icon: "bi-pinterest",
        className: "share-btn share-pinterest",
        href:
          "https://pinterest.com/pin/create/button/?url=" +
          encode(shareUrl) +
          "&media=" +
          encode(shareImage) +
          "&description=" +
          encode(shareText),
      },
      {
        id: "whatsapp",
        label: "Partager sur WhatsApp",
        icon: "bi-whatsapp",
        className: "share-btn share-whatsapp",
        href: "https://wa.me/?text=" + encode(shareText + " " + shareUrl),
      },
      {
        id: "email",
        label: "Partager par courriel",
        icon: "bi-envelope",
        className: "share-btn share-email",
        href:
          "mailto:?subject=" +
          encode(shareText) +
          "&body=" +
          encode(shareText + "\n\n" + shareUrl + (shareImage ? "\n\n" + shareImage : "")),
      },
    ];

    networks.forEach(function (network) {
      if (network.id === "pinterest" && !shareImage) return;
      var link = document.createElement("a");
      link.href = network.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = network.className;
      link.setAttribute("aria-label", network.label);
      link.title = network.label;
      link.innerHTML = iconHtml(network.icon);
      container.appendChild(link);
    });

    var copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "share-btn share-copy";
    copyBtn.setAttribute("aria-label", "Copier le lien");
    copyBtn.title = "Copier le lien";
    copyBtn.innerHTML = iconHtml("bi-link-45deg");
    copyBtn.addEventListener("click", function () {
      navigator.clipboard.writeText(shareUrl).then(function () {
        copyBtn.innerHTML = iconHtml("bi-check-lg");
        copyBtn.title = "Lien copié!";
        copyBtn.setAttribute("aria-label", "Lien copié");
        setTimeout(function () {
          copyBtn.innerHTML = iconHtml("bi-link-45deg");
          copyBtn.title = "Copier le lien";
          copyBtn.setAttribute("aria-label", "Copier le lien");
        }, 1800);
      });
    });
    container.appendChild(copyBtn);

    if (navigator.share) {
      var nativeBtn = document.createElement("button");
      nativeBtn.type = "button";
      nativeBtn.className = "share-btn share-native";
      nativeBtn.setAttribute("aria-label", "Partager");
      nativeBtn.title = "Partager";
      nativeBtn.innerHTML = iconHtml("bi-share-fill");
      nativeBtn.addEventListener("click", function () {
        var payload = {
          title: shareTitle,
          text: shareText,
          url: shareUrl,
        };
        navigator.share(payload).catch(function () {});
      });
      container.appendChild(nativeBtn);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPropertyShare);
  } else {
    initPropertyShare();
  }
})();
