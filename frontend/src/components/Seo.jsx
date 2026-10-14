import { useEffect } from "react";
import cfg from "@/seo/pages.json";
import { headFor } from "@/seo/head.mjs";

const setMeta = (key, attr, name, content) => {
  let el = document.head.querySelector(`[data-seo="${key}"]`);
  if (!el) { el = document.createElement("meta"); el.setAttribute(attr, name); el.dataset.seo = key; document.head.appendChild(el); }
  el.setAttribute("content", content);
};

export function Seo({ page }) {
  useEffect(() => {
    const h = headFor(cfg, page);
    document.title = h.title;
    setMeta("description", "name", "description", h.description);
    setMeta("keywords", "name", "keywords", h.keywords || "");
    setMeta("og:title", "property", "og:title", h.title);
    setMeta("og:description", "property", "og:description", h.description);
    setMeta("og:url", "property", "og:url", h.url);
    setMeta("og:locale", "property", "og:locale", h.locale);
    setMeta("twitter:title", "name", "twitter:title", h.title);
    setMeta("twitter:description", "name", "twitter:description", h.description);
    let can = document.head.querySelector('[data-seo="canonical"]');
    if (!can) { can = document.createElement("link"); can.rel = "canonical"; can.dataset.seo = "canonical"; document.head.appendChild(can); }
    can.href = h.url;
    document.head.querySelectorAll('[data-seo="alt"]').forEach((e) => e.remove());
    h.alternates.forEach(([l, u]) => {
      const a = document.createElement("link");
      Object.assign(a, { rel: "alternate", hreflang: l, href: u });
      a.dataset.seo = "alt";
      document.head.appendChild(a);
    });
    let ld = document.getElementById("seo-jsonld");
    if (!ld) { ld = document.createElement("script"); ld.type = "application/ld+json"; ld.id = "seo-jsonld"; document.head.appendChild(ld); }
    ld.textContent = h.jsonld;
  }, [page]);
  return null;
}

export const pageByPath = (path) => cfg.pages.find((p) => p.path === path);
export const SEO_PAGES = cfg.pages;
