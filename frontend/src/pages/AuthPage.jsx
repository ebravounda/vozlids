import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";
import { SignupForm } from "@/components/SignupForm";

const Field = ({ id, label, ...props }) => (
  <div className="space-y-2">
    <Label htmlFor={id} className="text-slate-700">{label}</Label>
    <Input id={id} data-testid={`auth-${id}-input`} className="h-11 rounded-lg border-slate-200 bg-white shadow-sm focus-visible:ring-blue-600/30" required {...props} />
  </div>
);

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.email, form.password);
      navigate("/app");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1fr_1.05fr]" style={{ fontFamily: "'DM Sans', sans-serif" }}>
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between">
          <Link to="/" data-testid="auth-logo-link"><Logo /></Link>
          <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900" data-testid="auth-back-link"><ArrowLeft className="h-4 w-4" /> Volver a la web</Link>
        </div>
        <div className={`mx-auto my-auto w-full ${isLogin ? "max-w-sm" : "max-w-xl"} py-12 fade-up`}>
          <div className="mb-8 grid grid-cols-2 rounded-xl bg-slate-100 p-1 text-sm font-semibold" role="tablist">
            {[["/login", "Iniciar sesión", true], ["/registro", "Crear cuenta", false]].map(([to, l, lg]) => (
              <Link key={to} to={to} role="tab" aria-selected={isLogin === lg} data-testid={`auth-tab-${lg ? "login" : "register"}`}
                className={`rounded-lg py-2 text-center transition-[background-color,color,box-shadow] ${isLogin === lg ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"}`}>{l}</Link>
            ))}
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{isLogin ? "Bienvenido de nuevo" : "Crea tu cuenta"}</h1>
          <p className="mt-2 text-slate-500">{isLogin ? "Entra para ver tus llamadas, agentes y citas." : "Elige tu plan, completa tus datos y activa tu línea con IA."}</p>
          {!isLogin ? <SignupForm /> : <form onSubmit={submit} className="mt-8 space-y-4" data-testid="auth-form">
            <Field id="email" label="Email" type="email" value={form.email} onChange={set("email")} placeholder="tu@negocio.es" autoComplete="email" />
            <Field id="password" label="Contraseña" type="password" minLength={isLogin ? undefined : 8} value={form.password} onChange={set("password")} placeholder={isLogin ? "••••••••" : "Mínimo 8 caracteres"} autoComplete={isLogin ? "current-password" : "new-password"} />
            {error && <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700" data-testid="auth-error">{error}</p>}
            <Button type="submit" disabled={loading} className="h-11 w-full rounded-lg text-base font-semibold shadow-sm transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-md" data-testid="auth-submit-button">
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isLogin ? "Entrar" : "Crear cuenta gratis"}
            </Button>
          </form>}
          <p className="mt-6 text-sm text-slate-500">
            {isLogin ? "¿No tienes cuenta? " : "¿Ya tienes cuenta? "}
            <Link to={isLogin ? "/registro" : "/login"} className="font-semibold text-blue-600 hover:text-blue-700" data-testid="auth-switch-link">{isLogin ? "Regístrate" : "Inicia sesión"}</Link>
          </p>
        </div>
        <p className="text-xs text-slate-400">© {new Date().getFullYear()} VozLeads.com by GoRoky.com</p>
      </div>
      <AuthShowcase />
    </div>
  );
}

function AuthShowcase() {
  return (
    <div className="relative hidden overflow-hidden bg-slate-900 text-slate-200 lg:flex lg:flex-col lg:justify-between lg:p-12" data-testid="auth-showcase">
      <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:radial-gradient(#334155_1px,transparent_1px)] [background-size:22px_22px]" aria-hidden />
      <p className="relative inline-flex w-fit items-center gap-2 rounded-md border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs font-semibold text-slate-200">
        <span className="h-2 w-2 rounded-full bg-emerald-400 vl-pulse" /> Líneas operativas · España +34 · Chile +56
      </p>
      <div className="relative mx-auto w-full max-w-md vl-float rounded-2xl border border-slate-700 bg-slate-800/70 p-6 backdrop-blur">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-white">Llamada en curso · Nuevo lead</p>
          <span className="rounded-full bg-emerald-400/15 px-2.5 py-1 text-[11px] font-semibold text-emerald-300">00:18</span>
        </div>
        <div className="my-6 flex h-14 items-center justify-center gap-[3px]" aria-hidden>
          {Array.from({ length: 40 }).map((_, i) => (
            <span key={i} className="vl-wave w-[3px] rounded-full bg-blue-400" style={{ height: 10 + ((i * 29) % 34), animationDelay: `${(i % 8) * 0.1}s` }} />
          ))}
        </div>
        <p className="vl-type text-sm text-slate-300">“Perfecto, te reservo el jueves a las 10:30 y te envío la confirmación por email.”</p>
      </div>
      <div className="relative">
        <p className="text-2xl font-bold leading-snug text-white" style={{ fontFamily: "Plus Jakarta Sans" }}>Cada lead recibe una llamada en menos de 30 segundos.</p>
        <div className="mt-6 grid grid-cols-3 gap-4 border-t border-slate-700 pt-6 text-sm">
          {[["< 30 s", "primer contacto"], ["24/7", "en tu horario"], ["100 %", "grabado y transcrito"]].map(([k, v]) => <div key={k}><p className="text-xl font-bold text-white">{k}</p><p className="text-slate-400">{v}</p></div>)}
        </div>
      </div>
    </div>
  );
}
