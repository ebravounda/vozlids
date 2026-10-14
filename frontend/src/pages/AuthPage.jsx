import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/Common";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";

const Field = ({ id, label, ...props }) => (
  <div className="space-y-2">
    <Label htmlFor={id} className="text-slate-300">{label}</Label>
    <Input id={id} data-testid={`auth-${id}-input`} className="h-11 bg-slate-950/60" required {...props} />
  </div>
);

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", business_name: "", email: "", password: "", country: "ES" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isLogin) {
        await login(form.email, form.password);
        navigate("/app");
      } else {
        await register(form);
        toast.success("Cuenta creada. Vamos a crear tu primer agente.");
        navigate("/app/agentes/nuevo");
      }
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grain relative grid min-h-screen lg:grid-cols-2">
      <div className="relative z-10 flex flex-col px-6 py-8 sm:px-12">
        <Link to="/" className="mb-16 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white" data-testid="auth-back-link">
          <ArrowLeft className="h-4 w-4" /> Volver
        </Link>
        <div className="mx-auto w-full max-w-md fade-up">
          <Logo className="mb-8" />
          <h1 className="text-4xl font-bold tracking-tight text-white">{isLogin ? "Bienvenido de nuevo" : "Crea tu cuenta"}</h1>
          <p className="mt-2 text-slate-400">
            {isLogin ? "Entra para ver tus llamadas y agentes." : "En 5 minutos tendrás un agente llamando a tus leads."}
          </p>
          <form onSubmit={submit} className="mt-10 space-y-5" data-testid="auth-form">
            {!isLogin && (
              <>
                <Field id="name" label="Tu nombre" value={form.name} onChange={set("name")} placeholder="Laura García" />
                <Field id="business" label="Nombre del negocio" value={form.business_name} onChange={set("business_name")} placeholder="Clínica Dental Sonrisa" />
              </>
            )}
            {!isLogin && (
              <div className="space-y-2">
                <Label className="text-slate-300">País del negocio</Label>
                <div className="grid grid-cols-2 gap-2">
                  {[["ES", "España"], ["CL", "Chile"]].map(([c, n]) => (
                    <button key={c} type="button" onClick={() => setForm({ ...form, country: c })} data-testid={`auth-country-${c}`}
                      className={`h-11 rounded-lg border text-sm font-semibold transition-colors ${form.country === c ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-300 hover:border-slate-500"}`}>{n}</button>
                  ))}
                </div>
              </div>
            )}
            <Field id="email" label="Email" type="email" value={form.email} onChange={set("email")} placeholder="tu@negocio.es" />
            <Field id="password" label="Contraseña" type="password" minLength={isLogin ? undefined : 8} value={form.password} onChange={set("password")} placeholder={isLogin ? "" : "Mínimo 8 caracteres"} />
            {error && <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300" data-testid="auth-error">{error}</p>}
            <Button type="submit" disabled={loading} className="h-11 w-full rounded-full text-base font-semibold" data-testid="auth-submit-button">
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isLogin ? "Entrar" : "Crear cuenta gratis"}
            </Button>
          </form>
          <p className="mt-6 text-sm text-slate-400">
            {isLogin ? "¿No tienes cuenta? " : "¿Ya tienes cuenta? "}
            <Link to={isLogin ? "/registro" : "/login"} className="font-semibold text-emerald-400 hover:text-emerald-300" data-testid="auth-switch-link">
              {isLogin ? "Regístrate" : "Inicia sesión"}
            </Link>
          </p>
        </div>
      </div>
      <div className="relative hidden overflow-hidden lg:block">
        <img src="https://images.unsplash.com/photo-1622675363311-3e1904dc1885?crop=entropy&cs=srgb&fm=jpg&q=80&w=1400" alt="Oficina" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0B0F17] via-[#0B0F17]/50 to-transparent" />
        <blockquote className="absolute bottom-12 left-12 right-12 rounded-2xl border border-slate-700/60 bg-slate-950/70 p-6 backdrop-blur-xl">
          <p className="font-display text-xl text-white">“Llamamos a cada lead en 20 segundos. Las citas se duplicaron el primer mes.”</p>
          <p className="mt-3 text-sm text-slate-400">Ejemplo de resultado típico en clínicas y academias</p>
        </blockquote>
      </div>
    </div>
  );
}
