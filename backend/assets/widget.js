(function () {
  var s = document.currentScript || document.querySelector('script[src*="/api/public/widget.js"]');
  var id = s && s.getAttribute("data-id");
  if (!id || window.__vozleadsWidget) return;
  window.__vozleadsWidget = true;
  var API = "__API__";
  fetch(API + "/api/public/widget/" + encodeURIComponent(id)).then(function (r) { return r.ok ? r.json() : null; }).then(function (c) {
    if (!c || !c.show) return;
    var track = function (t) {
      var u = API + "/api/public/widget/" + encodeURIComponent(id) + "/event", b = JSON.stringify({ t: t });
      try { if (navigator.sendBeacon && navigator.sendBeacon(u, new Blob([b], { type: "text/plain" }))) return; } catch (e) {}
      fetch(u, { method: "POST", body: b, keepalive: true, headers: { "Content-Type": "text/plain" } }).catch(function () {});
    };
    track("view");
    var host = document.createElement("div");
    host.id = "vozleads-widget";
    document.body.appendChild(host);
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
    var side = c.position === "left" ? "left" : "right";
    var esc = function (t) { var d = document.createElement("div"); d.textContent = t; return d.innerHTML; };
    root.innerHTML =
      '<style>' +
      '*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
      '.b{position:fixed;bottom:20px;' + side + ':20px;z-index:2147483000;display:flex;align-items:center;gap:8px;border:0;border-radius:999px;padding:14px 20px;background:' + c.color + ';color:#fff;font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 10px 30px -8px rgba(0,0,0,.45);transition:transform .2s}' +
      '.b:hover{transform:translateY(-2px)}' +
      '.b svg{width:18px;height:18px}' +
      '.p{position:fixed;bottom:20px;' + side + ':20px;z-index:2147483000;width:min(380px,calc(100vw - 24px));height:min(540px,calc(100vh - 40px));background:#fff;border-radius:18px;box-shadow:0 30px 80px -20px rgba(0,0,0,.5);overflow:hidden;display:none;flex-direction:column;animation:u .25s ease}' +
      '.p.o{display:flex}' +
      '.h{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:' + c.color + ';color:#fff;font-size:14px;font-weight:600}' +
      '.x{background:transparent;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer}' +
      'iframe{border:0;width:100%;flex:1}' +
      '.g{position:fixed;bottom:84px;' + side + ':20px;z-index:2147483000;max-width:260px;background:#fff;color:#0f172a;font-size:14px;line-height:1.4;padding:12px 30px 12px 14px;border-radius:14px;box-shadow:0 12px 34px -10px rgba(0,0,0,.35);display:none;animation:u .3s ease;cursor:pointer}' +
      '.g .c{position:absolute;top:4px;right:8px;border:0;background:transparent;font-size:16px;color:#64748b;cursor:pointer}' +
      '@keyframes u{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}' +
      '</style>' +
      '<div class="g" part="greeting">' + esc(c.greeting || "") + '<button class="c" aria-label="Cerrar">×</button></div>' +
      '<button class="b" part="button" aria-label="' + esc(c.text) + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg>' + esc(c.text) + '</button>' +
      '<div class="p" role="dialog" aria-label="' + esc(c.text) + '"><div class="h"><span>' + esc(c.business_name || c.text) + '</span><button class="x" aria-label="Cerrar">×</button></div></div>';
    var btn = root.querySelector(".b"), panel = root.querySelector(".p"), greet = root.querySelector(".g");
    var frame = null;
    var open = function () {
      greet.style.display = "none";
      if (!frame) track("open");
      if (!frame) {
        frame = document.createElement("iframe");
        frame.src = c.form_url + "?embed=1&src=widget&color=" + encodeURIComponent(c.color);
        frame.title = c.text;
        frame.allow = "clipboard-write";
        panel.appendChild(frame);
      }
      panel.classList.add("o");
      btn.style.display = "none";
    };
    btn.onclick = open;
    greet.onclick = open;
    root.querySelector(".x").onclick = function () { panel.classList.remove("o"); btn.style.display = "flex"; };
    greet.querySelector(".c").onclick = function (e) { e.stopPropagation(); greet.style.display = "none"; };
    if (c.greeting) setTimeout(function () { if (!panel.classList.contains("o")) greet.style.display = "block"; }, (c.greeting_delay || 6) * 1000);
  }).catch(function () {});
})();
