import { PageHeader } from "@/components/Common";
import { MyNumber } from "@/pages/dashboard/Telephony";
import { AgentNumbers } from "@/components/numbers/AgentNumbers";
import { KycPanel } from "@/components/kyc/KycPanel";

export default function MyNumberPage() {
  return (
    <div data-testid="my-number-page">
      <PageHeader eyebrow="Telefonía incluida" title="Mi número" desc="Tu número de España o Chile incluido en el plan: tus agentes llaman desde él y tu recepcionista contesta cuando te llaman." />
      <div className="max-w-2xl space-y-6"><KycPanel /><MyNumber /><AgentNumbers /></div>
    </div>
  );
}
