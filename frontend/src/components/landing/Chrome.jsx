import { Link } from "react-router-dom";
import { useState } from "react";
import { Menu, PhoneCall } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Logo } from "@/components/Common";
import { SEO_PAGES } from "@/components/Seo";
import { COMPANY } from "@/pages/Legal";

const H = { fontFamily: "Plus Jakarta Sans" };
const LINKS = [["#plataforma", "Plataforma"], ["#citas", "Citas"], ["#voces", "Voces"], ["#funciones", "Funciones"], ["#sectores", "Sectores"], ["#clientes", "Clientes"], ["#precios", "Precios"], ["#faq", "Preguntas"]];

export const Brand = () => (
  <Link to="/" className="flex items-center" data-testid="landing-brand"><Logo /></Link>
);

export const Nav = ({ home = false }) => (
  <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
    <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-6">
      <Brand />
      <nav className="hidden gap-5 whitespace-nowrap text-sm text-slate-600 xl:flex" aria-label="Secciones">
        {LINKS.map(([h, l]) => <a key={h} href={home ? `/${h}` : h} className="hover:text-slate-900" data-testid={`landing-nav-${h.slice(1)}-link`}>{l}</a>)}
      </nav>
      <div className="flex items-center gap-2">
        <Link to="/login" data-testid="landing-nav-login-button" className="hidden whitespace-nowrap px-3 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 sm:block">Acceder</Link>
        <a href="#solicitar" data-testid="landing-nav-info-button" className="hidden whitespace-nowrap rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-50 md:block">Llamada demo</a>
        <Link to="/registro" data-testid="landing-nav-register-button" className="hidden whitespace-nowrap rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700 sm:block">Empezar ahora</Link>
        <MobileMenu home={home} />
      </div>
    </div>
  </header>
);

function MobileMenu({ home }) {
  const [open, setOpen] = useState(false);
  const item = "block rounded-lg px-3 py-3 text-base font-medium text-slate-800 hover:bg-slate-50";
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button type="button" aria-label="Abrir menú" className="grid h-10 w-10 place-items-center rounded-md border border-slate-300 text-slate-800 xl:hidden" data-testid="landing-mobile-menu-button"><Menu className="h-5 w-5" /></button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[300px] bg-white" data-testid="landing-mobile-menu">
        <SheetHeader><SheetTitle className="text-left"><Logo /></SheetTitle></SheetHeader>
        <nav className="mt-6 space-y-1" aria-label="Menú móvil">
          {LINKS.map(([h, l]) => <a key={h} href={home ? `/${h}` : h} onClick={() => setOpen(false)} className={item} data-testid={`landing-mobile-nav-${h.slice(1)}-link`}>{l}</a>)}
        </nav>
        <div className="mt-6 space-y-2 border-t border-slate-200 pt-6">
          <Link to="/login" className={item} data-testid="landing-mobile-login-link">Acceder</Link>
          <a href={home ? "/#solicitar" : "#solicitar"} onClick={() => setOpen(false)} className="flex h-12 items-center justify-center gap-2 rounded-lg border border-slate-300 text-sm font-semibold text-slate-800" data-testid="landing-mobile-demo-link"><PhoneCall className="h-4 w-4" /> Llamada demo</a>
          <Link to="/registro" className="flex h-12 items-center justify-center rounded-lg bg-blue-600 text-sm font-semibold text-white" data-testid="landing-mobile-register-link">Empezar ahora</Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export const MobileCta = () => (
  <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 p-3 backdrop-blur md:hidden">
    <div className="grid grid-cols-2 gap-2">
      <a href="#solicitar" className="flex h-12 items-center justify-center gap-2 rounded-lg border border-slate-300 text-sm font-semibold text-slate-800" data-testid="mobile-info-cta"><PhoneCall className="h-4 w-4" /> Llamada demo</a>
      <Link to="/registro" className="flex h-12 items-center justify-center rounded-lg bg-blue-600 text-sm font-semibold text-white" data-testid="mobile-register-cta">Empezar ahora</Link>
    </div>
  </div>
);

export const Footer = ({ m }) => (
  <footer className="border-t border-slate-200 bg-slate-50 pb-24 md:pb-0">
    <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.2fr_2fr]">
      <div>
        <Brand />
        <p className="mt-4 max-w-xs text-sm text-slate-600">Agentes de voz con inteligencia artificial que llaman a tus leads en segundos, en español.</p>
        <p className="mt-4 text-sm text-slate-500" data-testid="footer-owner">VozLeads.com by <a href="https://goroky.com" rel="noopener" className="font-semibold text-slate-700 hover:underline">GoRoky.com</a></p>
      </div>
      <div className="grid gap-8 text-sm sm:grid-cols-3">
        {[["Sectores", SEO_PAGES.filter((p) => p.type === "sector" && p.country === (m?.market === "CL" ? "CL" : "ES"))],
          ["Soluciones", SEO_PAGES.filter((p) => p.type === "topic" && (m?.market === "INT" || [m?.market, "AUTO"].includes(p.country)))], ["Países", m?.market === "INT" ? SEO_PAGES.filter((p) => p.type === "country") : []]].filter(([, l]) => l.length).map(([t, list]) => (
          <nav key={t} aria-label={t} className={t === "Países" ? "sm:col-span-2" : ""}>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{t}</p>
            <ul className={`grid gap-2 ${t === "Países" ? "grid-cols-2" : ""}`}>
              {list.map((p) => <li key={p.path}><Link to={p.path} className="text-slate-600 hover:text-slate-900" data-testid={`footer-link-${p.path.slice(1).replace("/", "-")}`}>{t === "Sectores" ? `IA para ${p.name.toLowerCase()}` : t === "Países" ? p.h1.replace(/^.* (en|de|para empresas de|para empresas en) /, "") : p.h1}</Link></li>)}
            </ul>
          </nav>
        ))}
      </div>
    </div>
    <div className="border-t border-slate-200">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-6 text-xs text-slate-500 md:flex-row md:items-center md:justify-between" data-testid="footer-legal">
        <div className="space-y-1">
          <p data-testid="footer-company">VozLeads es parte del <a href="https://goroky.com" rel="noopener" className="font-semibold text-slate-700 hover:underline">{COMPANY.group}</a> · {COMPANY.legal} · {COMPANY.countries}</p>
          <p data-testid="footer-address">{COMPANY.address} · <a href={`mailto:${COMPANY.email}`} className="hover:underline" data-testid="footer-email">{COMPANY.email}</a></p>
        </div>
        <nav aria-label="Legal" className="flex flex-wrap gap-x-4 gap-y-1">
          {[["/terminos", "Términos y condiciones"], ["/privacidad", "Privacidad"], ["/cookies", "Cookies"], ["/aviso-legal", "Aviso legal"]].map(([to, l]) => <Link key={to} to={to} className="hover:text-slate-900 hover:underline" data-testid={`footer-link-${to.slice(1)}`}>{l}</Link>)}
          <span>© {new Date().getFullYear()} VozLeads.com</span>
        </nav>
      </div>
    </div>
  </footer>
);
