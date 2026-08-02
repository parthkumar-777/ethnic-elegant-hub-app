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

  // banner carousel auto-rotate
  var bannerTrack = document.getElementById("bannerTrack");
  if (bannerTrack) {
    var slides = bannerTrack.querySelectorAll(".banner-slide");
    var dots = document.querySelectorAll(".banner-dot");
    var current = 0;
    function showSlide(i) {
      current = i;
      bannerTrack.style.transform = "translateX(-" + (i * 100) + "%)";
      dots.forEach(function (d, idx) { d.classList.toggle("active", idx === i); });
    }
    dots.forEach(function (d, idx) {
      d.addEventListener("click", function () { showSlide(idx); });
    });
    if (slides.length > 1) {
      setInterval(function () {
        showSlide((current + 1) % slides.length);
      }, 4000);
    }
  }

  // password show/hide eye toggle
  document.querySelectorAll(".toggle-password").forEach(function (icon) {
    icon.addEventListener("click", function () {
      var target = document.getElementById(icon.getAttribute("data-target"));
      if (!target) return;
      if (target.type === "password") {
        target.type = "text";
        icon.textContent = "🙈";
      } else {
        target.type = "password";
        icon.textContent = "👁️";
      }
    });
  });

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
