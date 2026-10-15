import { PageHeader } from "@/components/Common";
import { MyNumber } from "@/pages/dashboard/Telephony";

export default function MyNumberPage() {
  return (
    <div data-testid="my-number-page">
      <PageHeader eyebrow="Telefonía incluida" title="Mi número" desc="Tu número de España o Chile incluido en el plan: tus agentes llaman desde él y tu recepcionista contesta cuando te llaman." />
      <div className="max-w-xl"><MyNumber /></div>
    </div>
  );
}
