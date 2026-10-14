# VozLead — Agentes de voz IA que llaman a tus leads en segundos

Plataforma SaaS donde cualquier negocio crea su agente de voz con IA, pega un formulario en su web y cada lead nuevo recibe una llamada telefónica real en menos de 30 segundos.
El agente habla en español de España con voz natural y ambiente de oficina de fondo (teclados, murmullo), y califica, agenda o vende según lo configure cada negocio.

## Para quién es
- **Negocios en España con leads que se enfrían** (clínicas, inmobiliarias, academias, servicios locales) que quieren contactar a cada interesado al instante sin ampliar el equipo.
- **Tú, como dueño del SaaS**, que gestionas la plataforma y das de alta a los negocios clientes.

## Funcionalidades principales y experiencia
- **Cuentas de empresa**: cada negocio se registra con email y contraseña y solo ve sus propios agentes, leads y llamadas.
- **Creador de agente**:
  - Nombre del agente (ej. "Marta"), nombre del negocio y descripción del producto o servicio.
  - **Objetivo de la llamada**, a elegir por agente: *Calificar y agendar cita*, *Solo calificar interés* o *Vender y cerrar en la llamada*.
  - Preguntas de calificación propias (ej. "¿qué presupuesto tienes?").
  - Elección de voz en español de España (varias voces masculinas y femeninas para escuchar antes de elegir).
  - **Ambiente de fondo**: oficina con teclados, call center o sin ambiente, con control de volumen.
  - Saludo inicial editable.
- **Formulario web incrustable**: cada agente genera un código para pegar en la web del negocio (nombre, teléfono +34, email y casilla de consentimiento). Al enviarlo, la llamada sale al momento.
- **Llamadas reales**: salen desde un número español; la IA escucha, responde con pausas naturales, deja que la interrumpan y cuelga con educación.
- **Agenda propia**: el negocio fija sus horarios disponibles y la IA ofrece y reserva huecos reales durante la llamada, sin dobles reservas.
- **Panel de llamadas**: lista de leads con su estado (llamando, sin respuesta, calificado, no interesado, cita agendada, venta, no volver a llamar), transcripción completa, grabación y un resumen generado por la IA con la puntuación de interés.
- **Prueba rápida**: botón "Llamarme ahora" para que el negocio pruebe su agente en su propio móvil antes de publicarlo.
- **Lista de no llamar**: si alguien pide que no le llamen, queda bloqueado al momento.

## Flujo de usuario
1. El negocio se registra y entra a su panel.
2. Crea su agente: objetivo, producto, preguntas, voz y ambiente de fondo.
3. Configura su horario de citas (si el objetivo incluye agendar).
4. Pulsa "Llamarme ahora" y escucha cómo suena el agente en su móvil.
5. Copia el código del formulario y lo pega en su web.
6. Un lead rellena el formulario → recibe la llamada en segundos → la IA califica, agenda o vende.
7. El negocio ve en su panel el resultado, la grabación, la transcripción y las citas.

## Sensación UI/UX
- Panel limpio, profesional y moderno, pensado para dueños de negocio no técnicos.
- Estados de llamada visibles en tiempo casi real, con colores claros por resultado.
- Reproductor de grabación junto a la transcripción, tipo chat.
- Landing pública del SaaS en español que explica el producto y lleva al registro.

## Fases de implementación
**Fase 1 — MVP (se construye ahora)**
- Registro e inicio de sesión de empresas, datos separados por negocio.
- Creador de agente con los tres objetivos, voces es-ES, ambiente de oficina con volumen y saludo editable.
- Formulario incrustable que dispara la llamada real al instante.
- Llamadas reales vía Vapi con número español de Zadarma.
- Agenda propia con reserva de huecos durante la llamada.
- Panel de leads y llamadas con estado, transcripción, grabación, resumen y puntuación.
- Botón "Llamarme ahora" y lista de no llamar.
- Landing pública del SaaS.

**Fase 2**
- Planes de suscripción y cobro a los negocios (Stripe), con límite de minutos por plan.
- Reintentos automáticos si el lead no contesta (seguimiento durante varios días).
- Confirmación y recordatorio de cita por SMS o WhatsApp.
- Conexión con Google Calendar.
- Subida de listas de leads (Excel/CSV) para campañas de llamadas.

**Fase 3**
- Seguimiento por WhatsApp con IA tras la llamada.
- Pasar la llamada a una persona del equipo cuando haga falta.
- Conexión con CRMs (HubSpot, etc.) y webhooks.
- Panel de administrador del SaaS con uso y costes por negocio.
- Agentes que contestan llamadas entrantes.

## Supuestos
- **Proveedor de voz: Vapi** para la conversación y el ambiente de oficina de fondo. Se eligió porque trae el ambiente de teclados/oficina integrado.
- **Operador telefónico: Zadarma** (en lugar de Twilio), con un número español +34 conectado a Vapi por troncal SIP (Vapi tiene una guía oficial para Zadarma). Se eligió porque llamar a móviles españoles sale más barato (unos 0,02–0,025 $/min con un identificador de llamada de la UE), porque Zadarma es una empresa europea con soporte en español y porque dar de alta un número +34 suele ser más sencillo. Twilio sigue siendo la alternativa si hiciera falta. Hacen falta tu clave de Vapi y los datos SIP de tu número de Zadarma; cada minuto tiene coste en esas cuentas.
- El número de Zadarma debe tener activado un identificador de llamada español/UE; si no, la tarifa sube mucho (unos 0,40 $/min).
- Coste estimado: unos 0,09–0,14 $ por minuto en total (0,05 $ de Vapi + transcripción, modelo de IA y voz al coste del proveedor + 0,02–0,025 $ de Zadarma). Se empieza con el plan gratuito de Vapi (5 $ de crédito, 4 llamadas simultáneas). Para más llamadas simultáneas está el plan Core (29 $/mes, 10 llamadas).
- Todas las llamadas de todos los negocios salen desde tus cuentas de Vapi/Zadarma (las de la plataforma), no desde cuentas de cada negocio.
- Idioma fijo: español de España; zona horaria Europa/Madrid; solo números +34.
- Los tres objetivos pedidos se ofrecen como opción a elegir en cada agente, no los tres a la vez en la misma llamada.
- "Vender y cerrar" en el MVP significa que la IA consigue el sí y lo registra como venta; el cobro dentro de la llamada queda fuera.
- **La IA dirá al inicio que es un asistente virtual** del negocio, y el formulario incluye una casilla de consentimiento obligatoria. La normativa española (AEPD/RGPD) exige consentimiento previo para llamadas comerciales automatizadas y la normativa europea de IA exige avisar de que se habla con una IA. Que la voz suene real sí es posible; ocultar que es una IA no lo es.
- Se avisa al lead de que la llamada se graba; las grabaciones solo las ven el negocio dueño.
- Acceso con email y contraseña; sin login de Google en el MVP.
- Nombre provisional del SaaS: "VozLead" (se puede cambiar).
- Sin cobro a los negocios en el MVP: el registro es libre.
