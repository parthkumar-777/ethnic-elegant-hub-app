document.addEventListener("DOMContentLoaded", function () {
  // wishlist heart toggle - AJAX so the page never reloads/scrolls to top,
  // with a small toast for instant feedback since there's no page-load flash anymore
  document.querySelectorAll(".heart-btn").forEach(function (btn) {
    var form = btn.closest("form");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var onWishlistPage = window.location.pathname === "/wishlist";
      fetch(form.action, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (res) {
          if (!res.ok) {
            window.location.href = form.action;
            return;
          }
          if (onWishlistPage) {
            var card = btn.closest(".card");
            if (card) {
              card.style.transition = "opacity .25s";
              card.style.opacity = "0";
              setTimeout(function () { card.remove(); }, 250);
            }
            showToast("Removed from wishlist");
          } else {
            var isActive = btn.classList.toggle("active");
            btn.textContent = isActive ? "❤️" : "🤍";
            showToast(isActive ? "Added to wishlist" : "Removed from wishlist");
          }
        })
        .catch(function () { window.location.href = form.action; });
    });
  });

  function showToast(message) {
    var existing = document.getElementById("eehToast");
    if (existing) existing.remove();
    var toast = document.createElement("div");
    toast.id = "eehToast";
    toast.className = "eeh-toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(function () { toast.classList.add("show"); });
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () { toast.remove(); }, 300);
    }, 1800);
  }

  // App-style splash screen - shows once per browser session (like an app launch),
  // not on every internal page click, then auto-hides
  var splash = document.getElementById("splashScreen");
  if (splash) {
    if (sessionStorage.getItem("eeh_splash_shown")) {
      splash.style.display = "none";
    } else {
      sessionStorage.setItem("eeh_splash_shown", "1");
      setTimeout(function () {
        splash.classList.add("hide");
      }, 1300);
    }
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
