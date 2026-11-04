// Copy / Share buttons, phone-specific Home Screen tips, and checkbox-gated buttons.
// No dependencies. Everything still works (server-side) if this script fails.
(function () {
  "use strict";

  function flash(button, text) {
    var original = button.textContent;
    button.textContent = text;
    setTimeout(function () { button.textContent = original; }, 2000);
  }

  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var text = button.getAttribute("data-copy");
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(
          function () { flash(button, "Copied!"); },
          function () { flash(button, fallbackCopy(text) ? "Copied!" : "Press and hold the link to copy"); }
        );
      } else {
        flash(button, fallbackCopy(text) ? "Copied!" : "Press and hold the link to copy");
      }
    });
  });

  if (navigator.share) {
    document.querySelectorAll("[data-share]").forEach(function (button) {
      button.hidden = false;
      button.addEventListener("click", function () {
        navigator.share({
          title: button.getAttribute("data-share-title") || document.title,
          url: button.getAttribute("data-share"),
        }).catch(function () { /* person closed the share sheet */ });
      });
    });
  }

  var ua = navigator.userAgent || "";
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/.test(ua);
  var standalone = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
  if (!standalone) {
    document.querySelectorAll('[data-tip="ios"]').forEach(function (el) { el.hidden = !isIOS; });
    document.querySelectorAll('[data-tip="android"]').forEach(function (el) { el.hidden = !isAndroid; });
  }

  // Back button restores a page with disabled buttons; reload it fresh instead.
  window.addEventListener("pageshow", function (e) { if (e.persisted) window.location.reload(); });

  // Stop double-taps from sending a form twice.
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      setTimeout(function () {
        form.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      }, 0);
    });
  });

  document.querySelectorAll("[data-gate]").forEach(function (form) {
    var box = form.querySelector("[data-gate-box]");
    var button = form.querySelector("[data-gate-button]");
    if (!box || !button) return;
    var sync = function () { button.disabled = !box.checked; };
    box.addEventListener("change", sync);
    sync();
  });
})();
