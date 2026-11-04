// Copy / Share buttons, households drag-and-drop, and checkbox-gated buttons.
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


  // Browsers skip autofocus when the URL has #add, so focus the box ourselves,
  // after the browser has finished jumping to #add (that jump clears focus).
  var auto = document.querySelector("[autofocus]");
  if (auto) window.addEventListener("load", function () {
    setTimeout(function () { auto.focus({ preventScroll: true }); }, 50);
  });

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

  // A small tap on the phone. Android: vibrate. iPhone has no vibrate for websites, but
  // iOS 18+ ticks when an on/off switch is toggled. iPhone only allows that while a finger
  // is lifting or tapping, so there we hold the tick until the touch ends.
  var canVibrate = typeof navigator.vibrate === "function";
  var pendingTick = false;
  function switchTick() {
    var label = document.createElement("label");
    label.setAttribute("aria-hidden", "true");
    label.style.display = "none";
    var sw = document.createElement("input");
    sw.type = "checkbox";
    sw.setAttribute("switch", "");
    label.appendChild(sw);
    document.head.appendChild(label);
    label.click();
    document.head.removeChild(label);
  }
  function haptic(now) {
    if (canVibrate) {
      try { navigator.vibrate(12); } catch (e) { /* not allowed right now */ }
    } else if (now) {
      try { switchTick(); } catch (e) { /* no haptics here */ }
    } else {
      pendingTick = true;
    }
  }
  document.addEventListener("touchend", function () {
    if (pendingTick) { pendingTick = false; try { switchTick(); } catch (e) { /* no haptics */ } }
  }, true);

  // Households page: drag names between household boxes, or tap a name then tap a box.
  // Each name carries a hidden dropdown; moving a name sets it, and the form posts those.
  function households(form) {
    form.classList.add("js-on");
    var loose = form.querySelector(".hh-loose");
    var groupsEl = form.querySelector(".hh-groups");
    var template = document.getElementById("hh-new");
    var addBtn = form.querySelector("[data-add-household]");
    var unsaved = form.querySelector("[data-unsaved]");
    var counter = 0;
    var dirty = false;
    var selected = null;

    addBtn.hidden = false;
    form.querySelectorAll("[data-delete-household]").forEach(function (b) { b.hidden = false; });

    function joinNames(names) {
      if (names.length < 2) return names.join("");
      return names.slice(0, -1).join(", ") + " & " + names[names.length - 1];
    }

    function chipsIn(box) { return box.querySelectorAll(".chip"); }

    function refresh() {
      form.querySelectorAll(".hh-box").forEach(function (box) {
        var chips = chipsIn(box);
        box.querySelector(".hh-empty").hidden = chips.length > 0;
        if (box === loose) return;
        var names = Array.prototype.map.call(chips, function (c) { return c.querySelector(".chip-name").textContent; });
        var title = box.querySelector(".hh-title");
        title.textContent = names.length === 0 ? "New household"
          : names.length === 1 ? names[0] + " (add one more person)" : joinNames(names);
      });
    }

    function markDirty() {
      dirty = true;
      unsaved.hidden = false;
    }

    function setSelectValue(select, key) {
      if (key && !select.querySelector('option[value="' + key + '"]')) {
        var opt = document.createElement("option");
        opt.value = key;
        opt.textContent = key;
        select.appendChild(opt);
      }
      select.value = key;
    }

    function move(chip, box) {
      if (chip.parentNode !== box.querySelector(".hh-chips")) {
        box.querySelector(".hh-chips").appendChild(chip);
        setSelectValue(chip.querySelector("select"), box.getAttribute("data-key"));
        markDirty();
      }
      refresh();
    }

    function select(chip) {
      if (selected) selected.classList.remove("selected");
      selected = chip === selected ? null : chip;
      if (selected) selected.classList.add("selected");
      form.classList.toggle("picking", !!selected);
    }

    function wireDelete(box) {
      box.querySelector("[data-delete-household]").addEventListener("click", function (e) {
        e.stopPropagation();
        Array.prototype.slice.call(chipsIn(box)).forEach(function (c) { move(c, loose); });
        box.parentNode.removeChild(box);
        markDirty();
        refresh();
      });
    }
    groupsEl.querySelectorAll(".hh-box").forEach(wireDelete);

    addBtn.addEventListener("click", function () {
      var box = template.content.firstElementChild.cloneNode(true);
      counter += 1;
      box.setAttribute("data-key", "n" + counter);
      groupsEl.appendChild(box);
      wireDelete(box);
      refresh();
      box.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    // Tap a box (not a name) while a name is picked: move it there.
    form.addEventListener("click", function (e) {
      if (!selected || e.target.closest(".chip") || e.target.closest("button")) return;
      var box = e.target.closest(".hh-box");
      if (!box) return;
      move(selected, box);
      select(selected);
      haptic(true);
    });

    // Dragging, with pointer events so it works with fingers and mice alike.
    var drag = null;

    function boxAt(x, y) {
      var el = document.elementFromPoint(x, y);
      return el && el.closest(".hh-box");
    }

    function autoScroll() {
      if (!drag || !drag.ghost) return;
      var edge = 70, y = drag.y, step = 0;
      if (y < edge) step = -Math.ceil((edge - y) / 6);
      else if (y > window.innerHeight - edge) step = Math.ceil((y - (window.innerHeight - edge)) / 6);
      if (step) window.scrollBy(0, step);
      drag.raf = requestAnimationFrame(autoScroll);
    }

    function startGhost() {
      var rect = drag.chip.getBoundingClientRect();
      var ghost = drag.chip.cloneNode(true);
      ghost.classList.add("chip-ghost");
      ghost.classList.remove("selected");
      var dropdown = ghost.querySelector("select");
      if (dropdown) dropdown.parentNode.removeChild(dropdown);
      ghost.style.width = rect.width + "px";
      drag.dx = drag.x0 - rect.left;
      drag.dy = drag.y0 - rect.top;
      document.body.appendChild(ghost);
      drag.ghost = ghost;
      drag.chip.classList.add("placeholder");
      drag.raf = requestAnimationFrame(autoScroll);
      if (canVibrate) haptic(); // picked up (iPhone can't tick mid-drag)
    }

    function endDrag(cancelled) {
      if (!drag) return;
      cancelAnimationFrame(drag.raf);
      form.querySelectorAll(".hh-box.over").forEach(function (b) { b.classList.remove("over"); });
      if (drag.ghost) {
        drag.ghost.parentNode.removeChild(drag.ghost);
        drag.chip.classList.remove("placeholder");
        var box = cancelled ? null : boxAt(drag.x, drag.y);
        if (box) { move(drag.chip, box); haptic(); } // dropped
        if (selected) select(selected);
      } else if (!cancelled) {
        select(drag.chip); // a tap, not a drag
        haptic();
      }
      drag = null;
    }

    form.addEventListener("pointerdown", function (e) {
      var chip = e.target.closest(".chip");
      if (!chip || (e.pointerType === "mouse" && e.button !== 0)) return;
      e.preventDefault();
      chip.setPointerCapture(e.pointerId);
      drag = { chip: chip, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, ghost: null, raf: 0 };
    });

    form.addEventListener("pointermove", function (e) {
      if (!drag) return;
      drag.x = e.clientX;
      drag.y = e.clientY;
      if (!drag.ghost && Math.abs(drag.x - drag.x0) + Math.abs(drag.y - drag.y0) > 8) startGhost();
      if (!drag.ghost) return;
      drag.ghost.style.left = drag.x - drag.dx + "px";
      drag.ghost.style.top = drag.y - drag.dy + "px";
      var over = boxAt(drag.x, drag.y);
      form.querySelectorAll(".hh-box").forEach(function (b) { b.classList.toggle("over", b === over); });
    });

    form.addEventListener("pointerup", function () { endDrag(false); });
    form.addEventListener("pointercancel", function () { endDrag(true); });

    form.addEventListener("submit", function () { dirty = false; });
    window.addEventListener("beforeunload", function (e) {
      if (dirty) { e.preventDefault(); e.returnValue = ""; }
    });

    refresh();
  }

  var board = document.querySelector("[data-households]");
  if (board) households(board);

  document.querySelectorAll("[data-gate]").forEach(function (form) {
    var box = form.querySelector("[data-gate-box]");
    var button = form.querySelector("[data-gate-button]");
    if (!box || !button) return;
    var sync = function () { button.disabled = !box.checked; };
    box.addEventListener("change", sync);
    sync();
  });
})();
