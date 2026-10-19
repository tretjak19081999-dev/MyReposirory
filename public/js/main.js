(function () {
  var nav = document.getElementById("nav");
  var burger = document.getElementById("burger");
  if (burger && nav) {
    burger.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      burger.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var params = new URLSearchParams(location.search);
  var utm = {};
  params.forEach(function (value, key) {
    if (/^(utm_|vk_|rb_)/.test(key) || key === "yclid" || key === "erid") utm[key] = value.slice(0, 200);
  });
  if (Object.keys(utm).length) sessionStorage.setItem("np_utm", JSON.stringify(utm));

  var consent = read("np_consent");
  var banner = document.getElementById("cookie");
  if (banner && !consent) banner.classList.add("show");

  document.querySelectorAll("[data-consent]").forEach(function (button) {
    button.addEventListener("click", function () {
      var mode = button.getAttribute("data-consent");
      if (mode === "settings") {
        document.getElementById("cookie-settings").classList.toggle("show");
        return;
      }
      var geo = mode === "geo";
      var marketing = mode === "all";
      if (mode === "custom") {
        geo = document.getElementById("opt-geo").checked;
        marketing = document.getElementById("opt-ads").checked;
      }
      saveConsent({ necessary: true, geo: geo, marketing: marketing, at: new Date().toISOString() });
      banner.classList.remove("show");
      if (geo) askGeo();
    });
  });

  if (consent && consent.geo) askGeo();

  document.querySelectorAll(".city").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".city").forEach(function (item) {
        item.setAttribute("aria-pressed", "false");
      });
      button.setAttribute("aria-pressed", "true");
      var card = document.getElementById("city-card");
      if (!card) return;
      card.hidden = false;
      document.getElementById("city-name").textContent = button.getAttribute("data-city");
      document.getElementById("city-note").textContent = button.getAttribute("data-note") || "Офиса агентства в этом городе нет. Заявку разбираем удалённо, оформление идёт в выбранном городе.";
      var cta = document.getElementById("city-cta");
      cta.href = "/kontakty.html?city=" + encodeURIComponent(button.getAttribute("data-city"));
    });
  });

  document.querySelectorAll("form.lead-form").forEach(function (form) {
    var city = params.get("city");
    if (city && form.city && !form.city.value) form.city.value = city;
    var storedGeo = read("np_geo");
    if (storedGeo && form.city && !form.city.value && storedGeo.city) form.city.value = storedGeo.city;
    if (storedGeo && form.region && !form.region.value && storedGeo.region) form.region.value = storedGeo.region;
    var otherLabel = form.querySelector(".citizenship-other");
    function syncCitizenship() {
      var show = form.citizenship && form.citizenship.value === "Другое";
      if (!otherLabel) return;
      otherLabel.hidden = !show;
      if (form.citizenship_other) form.citizenship_other.required = show;
    }
    if (form.citizenship) {
      form.citizenship.addEventListener("change", syncCitizenship);
      syncCitizenship();
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var status = form.querySelector(".form-status");
      var data = {
        name: form.name.value.trim(),
        phone: form.phone.value.trim(),
        city: form.city.value.trim(),
        region: form.region.value.trim(),
        age_years: form.age_years.value.trim(),
        citizenship: form.citizenship.value,
        citizenship_other: form.citizenship_other ? form.citizenship_other.value.trim() : "",
        profession: form.profession.value.trim(),
        direction: form.direction.value,
        status: form.status.value,
        message: form.message.value.trim(),
        age: form.age.checked ? "yes" : "",
        consent: form.consent.checked ? "yes" : "",
        ads: form.ads && form.ads.checked ? "yes" : "",
        website: form.website.value,
        page: location.pathname,
        referrer: document.referrer || "",
        utm: read("np_utm") || {},
        geo: read("np_geo")
      };
      status.className = "form-status";
      status.textContent = "Отправляем…";
      fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      }).then(function (response) {
        return response.json().then(function (body) {
          return { ok: response.ok, body: body };
        });
      }).then(function (result) {
        if (!result.ok) throw new Error((result.body && result.body.error) || "Не отправилось");
        form.reset();
        syncCitizenship();
        status.className = "form-status ok";
        status.textContent = "Заявка принята. Мы свяжемся с вами по мере обработки.";
      }).catch(function (error) {
        status.className = "form-status bad";
        status.textContent = error.message || "Не отправилось. Позвоните нам.";
      });
    });
  });

  function saveConsent(value) {
    localStorage.setItem("np_consent", JSON.stringify(value));
  }
  function read(key) {
    try { return JSON.parse(localStorage.getItem(key) || sessionStorage.getItem(key) || "null"); }
    catch (error) { return null; }
  }
  var hitKey = "np_hit_" + location.pathname;
  if (!sessionStorage.getItem(hitKey)) {
    sessionStorage.setItem(hitKey, "1");
    var refHost = "";
    try { refHost = document.referrer ? new URL(document.referrer).host : ""; } catch (error) { refHost = ""; }
    fetch("/api/hit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: location.pathname,
        ref: refHost,
        utm: read("np_utm") || {},
        device: window.innerWidth < 800 ? "телефон" : "компьютер"
      })
    }).catch(function () {});
  }

  function askGeo() {
    if (!navigator.geolocation || sessionStorage.getItem("np_geo")) return;
    navigator.geolocation.getCurrentPosition(function (position) {
      fetch("/api/geo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          consent: "yes"
        })
      }).then(function (response) { return response.json(); }).then(function (body) {
        if (!body || !body.city) return;
        var geo = { city: body.city, region: body.region || "", country: body.country || "", source: "browser" };
        sessionStorage.setItem("np_geo", JSON.stringify(geo));
        document.querySelectorAll("form.lead-form").forEach(function (form) {
          if (form.city && !form.city.value) form.city.value = geo.city;
          if (form.region && !form.region.value && geo.region) form.region.value = geo.region;
        });
      }).catch(function () {});
    }, function () {}, { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 });
  }
})();
