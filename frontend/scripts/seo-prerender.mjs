import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { bodyHtml, headFor, headHtml } from "../src/seo/head.mjs";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const cfg = JSON.parse(fs.readFileSync(path.join(root, "src/seo/pages.json"), "utf8"));
const mode = process.argv[2] || "build";

const sitemap = () => {
  const today = new Date().toISOString().slice(0, 10);
  const urls = [...cfg.pages.map((p) => [p.path, p.type === "topic" ? "0.8" : p.type === "sector" ? "0.9" : "1.0"]), ...["/privacidad", "/terminos", "/cookies", "/aviso-legal"].map((p) => [p, "0.3"])];
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls.map(([p, pr]) => `  <url><loc>${cfg.site}${p === "/" ? "/" : p}</loc><lastmod>${today}</lastmod><priority>${pr}</priority></url>`).join("\n") +
    "\n</urlset>\n";
};

if (mode === "sitemap") {
  fs.writeFileSync(path.join(root, "public/sitemap.xml"), sitemap());
  console.log("public/sitemap.xml written");
} else {
  const build = path.join(root, "build");
  const base = fs.readFileSync(path.join(build, "index.html"), "utf8");
  const block = /<title>[\s\S]*?seo-jsonld[^>]*>[\s\S]*?<\/script>/;
  if (!block.test(base)) throw new Error("SEO block missing in index.html");
  for (const page of cfg.pages) {
    const head = headHtml(headFor(cfg, page), cfg);
    const html = base.replace(block, () => head)
      .replace(/<div id="?root"?><\/div>/, () => `<div id="root">${bodyHtml(page, cfg, cfg.pages)}</div>`);
    if (!html.includes("seo-static")) throw new Error("root div not found");
    const dir = page.path === "/" ? build : path.join(build, page.path);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "index.html"), html);
  }
  fs.writeFileSync(path.join(build, "sitemap.xml"), sitemap());
  console.log(`SEO prerender: ${cfg.pages.length} pages`);
}
