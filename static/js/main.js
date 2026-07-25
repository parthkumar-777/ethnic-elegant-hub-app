document.addEventListener("DOMContentLoaded", function () {
  // Welcome popup - show once per browser using localStorage
  var overlay = document.getElementById("welcomeOverlay");
  if (overlay) {
    if (!localStorage.getItem("eeh_welcomed")) {
      overlay.style.display = "flex";
      localStorage.setItem("eeh_welcomed", "1");
    } else {
      overlay.style.display = "none";
    }
    var closeBtn = document.getElementById("welcomeClose");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        overlay.style.display = "none";
      });
    }
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.style.display = "none";
    });
  }

  // quantity selector on product page
  var qtyInput = document.getElementById("qtyInput");
  var qtyMinus = document.getElementById("qtyMinus");
  var qtyPlus = document.getElementById("qtyPlus");
  if (qtyInput && qtyMinus && qtyPlus) {
    qtyMinus.addEventListener("click", function () {
      var v = parseInt(qtyInput.value || "1");
      if (v > 1) qtyInput.value = v - 1;
    });
    qtyPlus.addEventListener("click", function () {
      var v = parseInt(qtyInput.value || "1");
      qtyInput.value = v + 1;
    });
  }
});
