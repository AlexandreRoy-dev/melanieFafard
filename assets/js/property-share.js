(function () {
  function encode(value) {
    return encodeURIComponent(value || "");
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
        label: "Facebook",
        className: "share-btn share-facebook",
        href: "https://www.facebook.com/sharer/sharer.php?u=" + encode(shareUrl),
      },
      {
        id: "x",
        label: "X",
        className: "share-btn share-x",
        href:
          "https://twitter.com/intent/tweet?url=" +
          encode(shareUrl) +
          "&text=" +
          encode(shareText),
      },
      {
        id: "linkedin",
        label: "LinkedIn",
        className: "share-btn share-linkedin",
        href:
          "https://www.linkedin.com/sharing/share-offsite/?url=" + encode(shareUrl),
      },
      {
        id: "whatsapp",
        label: "WhatsApp",
        className: "share-btn share-whatsapp",
        href: "https://wa.me/?text=" + encode(shareText + " " + shareUrl),
      },
      {
        id: "email",
        label: "Courriel",
        className: "share-btn share-email",
        href:
          "mailto:?subject=" +
          encode(shareText) +
          "&body=" +
          encode(shareText + "\n\n" + shareUrl),
      },
    ];

    networks.forEach(function (network) {
      var link = document.createElement("a");
      link.href = network.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = network.className;
      link.textContent = network.label;
      container.appendChild(link);
    });

    var copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "share-btn share-copy";
    copyBtn.textContent = "Copier le lien";
    copyBtn.addEventListener("click", function () {
      navigator.clipboard.writeText(shareUrl).then(function () {
        copyBtn.textContent = "Lien copié!";
        setTimeout(function () {
          copyBtn.textContent = "Copier le lien";
        }, 1800);
      });
    });
    container.appendChild(copyBtn);

    if (navigator.share) {
      var nativeBtn = document.createElement("button");
      nativeBtn.type = "button";
      nativeBtn.className = "share-btn share-native";
      nativeBtn.textContent = "Partager";
      nativeBtn.addEventListener("click", function () {
        navigator.share({
          title: shareTitle,
          text: shareText,
          url: shareUrl,
        });
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
