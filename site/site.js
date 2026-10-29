/* essun site — progressive enhancement only.
   Without this file the site renders and works fully; with it, code
   blocks gain a copy button. No dependencies, no tracking. */
(function () {
  "use strict";

  if (!navigator.clipboard || !navigator.clipboard.writeText) {
    return; // no clipboard API — stay static
  }

  document.querySelectorAll("pre").forEach(function (pre) {
    // skip the decorative hero terminal (its content is aria-hidden)
    if (pre.getAttribute("aria-hidden") === "true") {
      return;
    }

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "copy";

    btn.addEventListener("click", function () {
      var text = pre.innerText;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "copied";
        setTimeout(function () { btn.textContent = "copy"; }, 1400);
      }, function () {
        btn.textContent = "failed";
        setTimeout(function () { btn.textContent = "copy"; }, 1400);
      });
    });

    pre.appendChild(btn);
  });
})();
