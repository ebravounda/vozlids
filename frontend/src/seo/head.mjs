const LATAM = ["mx", "ar", "co", "pe", "ec", "uy", "ve", "pa", "cr", "gt", "hn", "sv", "ni", "do", "bo", "py"];
const HREFLANG = [["es-ES", "/es"], ["es-CL", "/cl"], ...LATAM.map((c) => [`es-${c.toUpperCase()}`, `/${c}`]), ["es", "/"], ["x-default", "/"]];
const NAMES = { ES: "España", CL: "Chile", MX: "México", AR: "Argentina", CO: "Colombia", PE: "Perú", EC: "Ecuador", UY: "Uruguay", VE: "Venezuela", PA: "Panamá", CR: "Costa Rica", GT: "Guatemala", HN: "Honduras", SV: "El Salvador", NI: "Nicaragua", DO: "República Dominicana", BO: "Bolivia", PY: "Paraguay" };

export function headFor(cfg, page) {
  const url = cfg.site + (page.path === "/" ? "/" : page.path);
  const org = { "@type": "Organization", "@id": `${cfg.site}/#org`, name: cfg.brand, url: cfg.site, logo: `${cfg.site}/logo.png`,
    parentOrganization: { "@type": "Organization", name: "GoRoky LLC", url: `https://${cfg.owner.toLowerCase()}` },
    email: "soporte@goroky.com",
    address: { "@type": "PostalAddress", streetAddress: "Raimundo Fernández Villaverde 39", addressLocality: "Madrid", addressCountry: "ES" },
    contactPoint: { "@type": "ContactPoint", contactType: "customer support", email: "soporte@goroky.com", availableLanguage: "es" },
    areaServed: Object.values(NAMES).map((name) => ({ "@type": "Country", name })) };
  const graph = [org,
    { "@type": "WebSite", "@id": `${cfg.site}/#web`, url: cfg.site, name: cfg.brand, inLanguage: "es", publisher: { "@id": `${cfg.site}/#org` } },
    { "@type": "SoftwareApplication", name: `${cfg.brand} · Agente de voz con IA`, applicationCategory: "BusinessApplication",
      operatingSystem: "Web", url, description: page.description, publisher: { "@id": `${cfg.site}/#org` },
      offers: [{ "@type": "Offer", priceCurrency: "EUR", areaServed: "ES", url: `${cfg.site}/es#precios` },
        { "@type": "Offer", priceCurrency: "CLP", areaServed: "CL", url: `${cfg.site}/cl#precios` }] },
    { "@type": "WebPage", "@id": `${url}#page`, url, name: page.title, description: page.description, inLanguage: NAMES[page.country] ? `es-${page.country}` : "es" }];
  if (page.faq?.length) {
    graph.push({ "@type": "FAQPage", mainEntity: page.faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });
  }
  const sector = page.type === "sector";
  if (sector) {
    const cp = `${cfg.site}/${page.country.toLowerCase()}`;
    graph.push({ "@type": "Service", name: page.h1, serviceType: "Recepcionista virtual y asistente telefónico con IA",
      audience: { "@type": "BusinessAudience", name: page.name }, areaServed: { "@type": "Country", name: NAMES[page.country] },
      provider: { "@id": `${cfg.site}/#org` }, url });
    graph.push({ "@type": "AudioObject", name: `Llamada de ejemplo: ${page.biz}`, encodingFormat: "audio/mpeg", inLanguage: `es-${page.country}`,
      contentUrl: `${cfg.site}/api/public/sector-demo/${page.country.toLowerCase()}/${page.sector}.mp3`,
      transcript: page.dialog.map(([w, t]) => `${w === "caller" ? "Cliente" : "Agente"}: ${t}`).join("\n") });
    graph.push({ "@type": "BreadcrumbList", itemListElement: [
      { "@type": "ListItem", position: 1, name: cfg.brand, item: `${cfg.site}/` },
      { "@type": "ListItem", position: 2, name: NAMES[page.country], item: cp },
      { "@type": "ListItem", position: 3, name: page.name, item: url }] });
  } else if (page.path !== "/") {
    graph.push({ "@type": "BreadcrumbList", itemListElement: [
      { "@type": "ListItem", position: 1, name: cfg.brand, item: `${cfg.site}/` },
      { "@type": "ListItem", position: 2, name: page.h1, item: url }] });
  }
  const pair = (c) => `${cfg.site}/${c}/${page.sector}`;
  return {
    title: page.title, description: page.description, keywords: page.keywords, url,
    alternates: sector ? [["es-ES", pair("es")], ["es-CL", pair("cl")], ["x-default", pair("es")]]
      : ["home", "country"].includes(page.type) ? HREFLANG.map(([l, p]) => [l, cfg.site + p]) : [],
    image: page.img,
    locale: NAMES[page.country] ? `es_${page.country}` : "es_ES",
    jsonld: JSON.stringify({ "@context": "https://schema.org", "@graph": graph }),
  };
}

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function headHtml(h, cfg) {
  return [
    `<title>${esc(h.title)}</title>`,
    `<meta name="description" content="${esc(h.description)}" data-seo="description" />`,
    `<meta name="keywords" content="${esc(h.keywords || "")}" data-seo="keywords" />`,
    `<meta name="robots" content="index, follow, max-image-preview:large" />`,
    `<link rel="canonical" href="${h.url}" data-seo="canonical" />`,
    ...h.alternates.map(([l, u]) => `<link rel="alternate" hreflang="${l}" href="${u}" data-seo="alt" />`),
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="${esc(cfg.brand)}" />`,
    `<meta property="og:locale" content="${h.locale}" data-seo="og:locale" />`,
    `<meta property="og:title" content="${esc(h.title)}" data-seo="og:title" />`,
    `<meta property="og:description" content="${esc(h.description)}" data-seo="og:description" />`,
    `<meta property="og:url" content="${h.url}" data-seo="og:url" />`,
    `<meta property="og:image" content="${h.image || `${cfg.site}/og-image.jpg`}" data-seo="og:image" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${esc(h.title)}" data-seo="twitter:title" />`,
    `<meta name="twitter:description" content="${esc(h.description)}" data-seo="twitter:description" />`,
    `<script type="application/ld+json" id="seo-jsonld">${h.jsonld.replace(/</g, "\\u003c")}</script>`,
  ].join("\n        ");
}

export function bodyHtml(page, cfg, all) {
  const sec = (page.sections || []).map(([t, p]) => `<h2>${esc(t)}</h2><p>${esc(p)}</p>`).join("") +
    (page.dialog ? `<h2>Ejemplo de llamada en ${esc(page.biz)}</h2><ol>${page.dialog.map(([w, t]) => `<li>${w === "caller" ? "Cliente" : "Agente"}: ${esc(t)}</li>`).join("")}</ol>` : "");
  const faq = (page.faq || []).map(([q, a]) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join("");
  const links = all.filter((p) => p.path !== page.path).map((p) => `<li><a href="${p.path}">${esc(p.h1)}</a></li>`).join("");
  return `<main class="seo-static"><p>${esc(page.eyebrow)}</p><h1>${esc(page.h1)}</h1><p>${esc(page.intro)}</p>${sec}` +
    `<h2>Solicita información ahora</h2><p>Déjanos tu nombre y teléfono y nuestro agente de voz te llama en segundos.</p>` +
    `<h2>Preguntas frecuentes</h2>${faq}<nav><ul>${links}</ul></nav><p>${esc(cfg.brand)}.com by ${esc(cfg.owner)}</p></main>`;
}
