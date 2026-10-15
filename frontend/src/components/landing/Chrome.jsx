import { Link } from "react-router-dom";
import { PhoneCall } from "lucide-react";
import { Logo } from "@/components/Common";
import { SEO_PAGES } from "@/components/Seo";

const H = { fontFamily: "Plus Jakarta Sans" };
const LINKS = [["#soluciones", "Soluciones"], ["#como", "Cómo funciona"], ["#precios", "Precios"], ["#faq", "Preguntas"]];

export const Brand = () => (
  <Link to="/" className="flex items-center" data-testid="landing-brand"><Logo /></Link>
);

export const Nav = () => (
  <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
    <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-6">
      <Brand />
      <nav className="hidden gap-7 text-sm text-slate-600 lg:flex" aria-label="Secciones">
        {LINKS.map(([h, l]) => <a key={h} href={h} className="hover:text-slate-900" data-testid={`landing-nav-${h.slice(1)}-link`}>{l}</a>)}
      </nav>
      <div className="flex items-center gap-2">
        <Link to="/login" data-testid="landing-nav-login-button" className="hidden px-3 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 sm:block">Acceder</Link>
        <a href="#solicitar" data-testid="landing-nav-info-button" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700">Solicita información</a>
      </div>
    </div>
  </header>
);

export const MobileCta = () => (
  <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 p-3 backdrop-blur md:hidden">
    <a href="#solicitar" className="flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 font-semibold text-white" data-testid="mobile-info-cta">
      <PhoneCall className="h-4 w-4" /> Solicita información ahora
    </a>
  </div>
);

export const Footer = () => (
  <footer className="border-t border-slate-200 bg-slate-50 pb-24 md:pb-0">
    <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.2fr_2fr]">
      <div>
        <Brand />
        <p className="mt-4 max-w-xs text-sm text-slate-600">Agentes de voz con inteligencia artificial que llaman a tus leads en segundos. España y Chile.</p>
        <p className="mt-4 text-sm text-slate-500" data-testid="footer-owner">VozLeads.com by <a href="https://goroky.com" rel="noopener" className="font-semibold text-slate-700 hover:underline">GoRoky.com</a></p>
      </div>
      <nav aria-label="Páginas" className="grid gap-2 text-sm sm:grid-cols-2">
        {SEO_PAGES.filter((p) => p.path !== "/").map((p) => (
          <Link key={p.path} to={p.path} className="text-slate-600 hover:text-slate-900" data-testid={`footer-link-${p.path.slice(1)}`}>{p.h1}</Link>
        ))}
        <Link to="/privacidad" className="text-slate-600 hover:text-slate-900" data-testid="footer-link-privacidad">Política de privacidad</Link>
        <Link to="/registro" className="text-slate-600 hover:text-slate-900">Crear cuenta</Link>
      </nav>
    </div>
    <div className="border-t border-slate-200 py-5 text-center text-xs text-slate-500">© {new Date().getFullYear()} VozLeads.com by GoRoky.com · España · Chile</div>
  </footer>
);
