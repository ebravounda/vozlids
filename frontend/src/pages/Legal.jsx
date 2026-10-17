import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Footer, Nav } from "@/components/landing/Chrome";

export const COMPANY = {
  group: "Grupo GoRoky", legal: "GoRoky LLC", countries: "Estados Unidos, España, Chile",
  address: "Raimundo Fernández Villaverde 39, Madrid, España", email: "soporte@goroky.com",
};
const OWNER = `${COMPANY.legal} (${COMPANY.countries}), con domicilio en ${COMPANY.address} y correo de contacto ${COMPANY.email}`;

export const LEGAL = {
  "/privacidad": ["Política de privacidad", [
    ["Responsable", `VozLeads.com forma parte del ${COMPANY.group}. El responsable del tratamiento es ${OWNER}.`],
    ["Qué datos tratamos", "Nombre y número de teléfono que nos facilitas en el formulario, la grabación y transcripción de la llamada de información y los datos técnicos mínimos (fecha, página y dirección IP) para evitar abusos. Si eres cliente, también los datos de tu cuenta y de facturación."],
    ["Para qué los usamos", "Para llamarte con nuestro agente de voz con IA, darte la información que pediste, prestarte el servicio contratado y que un asesor pueda contactarte. No los vendemos ni los cedemos a terceros con fines comerciales."],
    ["Base legal", "Tu consentimiento expreso al marcar la casilla del formulario y, si eres cliente, la ejecución del contrato (RGPD en España y Ley 19.628 en Chile). Puedes retirar tu consentimiento en cualquier momento."],
    ["Conservación", "Conservamos la solicitud el tiempo necesario para atenderla y, como máximo, 12 meses, salvo que pases a ser cliente. Los datos de facturación se guardan el tiempo que exige la ley."],
    ["Proveedores", "Usamos proveedores de telefonía, voz, inteligencia artificial, pagos y correo que actúan como encargados del tratamiento y solo procesan los datos para prestar el servicio, con las garantías adecuadas para transferencias internacionales."],
    ["Tus derechos", `Puedes pedir acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo a ${COMPANY.email}. Si no quieres que te volvamos a llamar, díselo al agente durante la llamada y quedarás en la lista de no llamar. También puedes reclamar ante la autoridad de protección de datos de tu país.`],
  ]],
  "/terminos": ["Términos y condiciones", [
    ["Titular del servicio", `VozLeads.com es un servicio del ${COMPANY.group}, prestado por ${OWNER}.`],
    ["Objeto", "Estos términos regulan el uso de la web y de la plataforma VozLeads: agentes de voz con inteligencia artificial que realizan y atienden llamadas telefónicas en nombre de las empresas clientes."],
    ["Cuenta y uso", "Para usar la plataforma necesitas una cuenta con datos veraces. Eres responsable de las credenciales de tu cuenta y de la actividad que se realice con ella."],
    ["Uso permitido", "Solo puedes llamar a personas que hayan dado su consentimiento o con las que tengas una relación que lo permita, respetando las listas de exclusión y la normativa de tu país (RGPD y LSSI en España, Ley 19.628 y Ley 19.496 en Chile). Está prohibido usar el servicio para spam, fraude, suplantación o contenidos ilícitos."],
    ["Planes, pagos y cancelación", "Los planes son mensuales, sin permanencia, y se cobran por adelantado con tarjeta. Los minutos no consumidos no se acumulan. Puedes cancelar cuando quieras desde el panel; la cancelación tiene efecto al final del periodo pagado."],
    ["Números de teléfono", "Los números incluidos en los planes se asignan mientras la suscripción esté activa y pueden liberarse si la cuenta se cancela o queda impagada."],
    ["Responsabilidad", "Ponemos todos los medios razonables para que el servicio funcione de forma continua, pero no garantizamos la ausencia total de interrupciones por causas ajenas (operadores, proveedores o fuerza mayor). Cada cliente es responsable de los guiones, la información y las promesas que su agente comunique."],
    ["Cambios", "Podemos actualizar estos términos; te avisaremos con antelación razonable de los cambios relevantes."],
    ["Contacto y ley aplicable", `Para cualquier duda escribe a ${COMPANY.email}. Se aplicará la normativa de protección al consumidor del país del cliente cuando corresponda.`],
  ]],
  "/cookies": ["Política de cookies", [
    ["Qué son", "Las cookies y tecnologías similares (como el almacenamiento local del navegador) son pequeños archivos que la web guarda en tu dispositivo para funcionar correctamente o recordar tus preferencias."],
    ["Qué usamos", "VozLeads solo utiliza cookies y almacenamiento técnicos, necesarios para el funcionamiento de la web: mantener tu sesión iniciada en el panel, recordar preferencias como la moneda y proteger la web frente a abusos y ataques. No usamos cookies de publicidad ni de seguimiento de terceros."],
    ["Consentimiento", "Al ser estrictamente necesarias, estas cookies están exentas de consentimiento según la normativa europea (art. 22.2 LSSI). Si en el futuro añadimos cookies de análisis o marketing, te pediremos permiso antes de usarlas."],
    ["Cómo desactivarlas", "Puedes borrar o bloquear las cookies desde la configuración de tu navegador (Chrome, Safari, Firefox o Edge). Si las bloqueas, es posible que no puedas iniciar sesión en el panel."],
    ["Responsable", `${OWNER}.`],
  ]],
  "/aviso-legal": ["Aviso legal", [
    ["Datos del titular", `VozLeads.com forma parte del ${COMPANY.group}. Titular: ${COMPANY.legal} · ${COMPANY.countries}. Dirección: ${COMPANY.address}. Correo: ${COMPANY.email}.`],
    ["Propiedad intelectual", "Los textos, diseños, marcas, logotipos y software de esta web pertenecen al Grupo GoRoky o se usan con licencia. No se permite su reproducción sin autorización."],
    ["Uso de la web", "Te comprometes a usar la web de forma lícita y a no introducir virus ni realizar acciones que puedan dañarla o impedir su uso a otras personas."],
    ["Enlaces", "Los enlaces a webs de terceros se ofrecen solo como referencia; no somos responsables de su contenido."],
    ["Más información", "Consulta también nuestros términos y condiciones, la política de privacidad y la política de cookies."],
  ]],
};

export default function Legal({ path }) {
  const [title, sections] = LEGAL[path];
  useEffect(() => { document.title = `${title} | VozLeads`; window.scrollTo(0, 0); }, [title]);
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'DM Sans', sans-serif" }} data-testid={`legal-page-${path.slice(1)}`}>
      <Nav home />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "Plus Jakarta Sans" }}>{title}</h1>
        <p className="mt-3 text-sm text-slate-500">Última actualización: octubre de 2026</p>
        {sections.map(([t, p]) => <section key={t} className="mt-8"><h2 className="text-lg font-semibold text-slate-900">{t}</h2><p className="mt-2 leading-relaxed">{p}</p></section>)}
        <nav className="mt-12 flex flex-wrap gap-4 border-t border-slate-200 pt-6 text-sm" aria-label="Páginas legales">
          {Object.entries(LEGAL).filter(([p]) => p !== path).map(([p, [t]]) => <Link key={p} to={p} className="font-semibold text-blue-700 hover:underline" data-testid={`legal-nav-${p.slice(1)}`}>{t}</Link>)}
        </nav>
      </main>
      <Footer />
    </div>
  );
}
