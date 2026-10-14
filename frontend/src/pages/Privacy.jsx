import { useEffect } from "react";
import { Footer, Nav } from "@/components/landing/Chrome";

const S = [
  ["Responsable", "VozLeads.com, servicio operado por GoRoky.com. Para cualquier consulta sobre tus datos puedes escribirnos desde la página de contacto de GoRoky.com."],
  ["Qué datos tratamos", "Nombre y número de teléfono que nos facilitas en el formulario, la grabación y transcripción de la llamada de información y los datos técnicos mínimos (fecha, página y dirección IP) para evitar abusos."],
  ["Para qué los usamos", "Para llamarte con nuestro agente de voz con IA, darte la información que pediste y que un asesor pueda contactarte. No los vendemos ni los cedemos a terceros con fines comerciales."],
  ["Base legal", "Tu consentimiento expreso al marcar la casilla del formulario (RGPD en España y Ley 19.628 en Chile). Puedes retirarlo en cualquier momento."],
  ["Conservación", "Conservamos la solicitud el tiempo necesario para atenderla y, como máximo, 12 meses, salvo que pases a ser cliente."],
  ["Proveedores", "Usamos proveedores de telefonía, voz e inteligencia artificial que actúan como encargados del tratamiento y solo procesan los datos para prestar el servicio."],
  ["Tus derechos", "Puedes pedir acceso, rectificación, supresión, oposición, limitación y portabilidad. Si no quieres que te volvamos a llamar, díselo al agente durante la llamada y quedarás en la lista de no llamar."],
];

export default function Privacy() {
  useEffect(() => { document.title = "Política de privacidad | VozLeads"; }, []);
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }} data-testid="privacy-page">
      <Nav />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Outfit" }}>Política de privacidad</h1>
        {S.map(([t, p]) => <section key={t} className="mt-8"><h2 className="text-lg font-semibold text-slate-900">{t}</h2><p className="mt-2 leading-relaxed">{p}</p></section>)}
      </main>
      <Footer />
    </div>
  );
}
