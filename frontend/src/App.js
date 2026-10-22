import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import ApiDocs from "@/pages/ApiDocs";
import Landing from "@/pages/Landing";
import Legal, { LEGAL } from "@/pages/Legal";
import { SEO_PAGES } from "@/components/Seo";
import AuthPage from "@/pages/AuthPage";
import PublicForm from "@/pages/PublicForm";
import DashboardLayout from "@/pages/dashboard/DashboardLayout";
import Leads from "@/pages/dashboard/Leads";
import Agents from "@/pages/dashboard/Agents";
import AgentBuilder from "@/pages/dashboard/AgentBuilder";
import Agenda from "@/pages/dashboard/Agenda";
import DoNotCall from "@/pages/dashboard/DoNotCall";
import Telephony from "@/pages/dashboard/Telephony";
import MyNumberPage from "@/pages/dashboard/MyNumberPage";
import AdminCosts from "@/pages/dashboard/AdminCosts";
import AdminLines from "@/pages/dashboard/AdminLines";
import AdminVapi from "@/pages/dashboard/AdminVapi";
import AdminPayments from "@/pages/dashboard/AdminPayments";
import AdminMonitor from "@/pages/dashboard/AdminMonitor";
import WebWidget from "@/pages/dashboard/WebWidget";
import Welcome from "@/pages/dashboard/Welcome";
import Outbound from "@/pages/dashboard/Outbound";
import Support from "@/pages/dashboard/Support";
import Developers from "@/pages/dashboard/Developers";
import Privacy from "@/pages/dashboard/Privacy";
import PublicAppointment from "@/pages/PublicAppointment";
import { Gate } from "@/components/PlanGate";
import SuperAdmin from "@/pages/dashboard/SuperAdmin";
import Billing from "@/pages/dashboard/Billing";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null)
    return <div className="min-h-screen grid place-items-center text-slate-400" data-testid="auth-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {SEO_PAGES.map((p) => <Route key={p.path} path={p.path} element={<Landing key={p.path} path={p.path} />} />)}
          {Object.keys(LEGAL).map((p) => <Route key={p} path={p} element={<Legal path={p} />} />)}
          <Route path="/desarrolladores" element={<ApiDocs />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/registro" element={<AuthPage mode="register" />} />
          <Route path="/f/:agentId" element={<PublicForm />} />
          <Route path="/cita/:token" element={<PublicAppointment />} />
          <Route path="/app" element={<Protected><DashboardLayout /></Protected>}>
            <Route index element={<Leads />} />
            <Route path="agentes" element={<Agents />} />
            <Route path="agentes/nuevo" element={<AgentBuilder />} />
            <Route path="agentes/:agentId" element={<AgentBuilder />} />
            <Route path="agenda" element={<Agenda />} />
            <Route path="no-llamar" element={<DoNotCall />} />
            <Route path="numero" element={<MyNumberPage />} />
            <Route path="telefonia" element={<Telephony />} />
            <Route path="costes" element={<AdminCosts />} />
            <Route path="lineas" element={<AdminLines />} />
            <Route path="vapi" element={<AdminVapi />} />
            <Route path="pagos" element={<AdminPayments />} />
            <Route path="monitor" element={<AdminMonitor />} />
            <Route path="boton-web" element={<Gate f="widget"><WebWidget /></Gate>} />
            <Route path="bienvenida" element={<Welcome />} />
            <Route path="llamadas" element={<Gate f="outbound"><Outbound /></Gate>} />
            <Route path="asistencia" element={<Support />} />
            <Route path="api" element={<Gate f="api"><Developers /></Gate>} />
            <Route path="privacidad" element={<Privacy />} />
            <Route path="admin" element={<SuperAdmin />} />
            <Route path="plan" element={<Billing />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}

export default App;
