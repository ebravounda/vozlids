import { Pricing } from "@/components/Pricing";
import { Seo, pageByPath } from "@/components/Seo";
import { Footer, MobileCta, Nav } from "@/components/landing/Chrome";
import { ApiBlock, Compatible, Countries, Faq, FinalCta, Hero, Steps, TopicSections, TrustBar, Uses, WhyNow } from "@/components/landing/Sections";

const CUR = { ES: "EUR", CL: "CLP" };

export default function Landing({ path = "/" }) {
  const page = pageByPath(path);
  const topic = page.type === "topic";
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }} data-testid={`marketing-page-${path === "/" ? "home" : path.slice(1)}`}>
      <Seo page={page} />
      <Nav />
      <main>
        <Hero page={page} />
        <TrustBar />
        {topic && <TopicSections sections={page.sections} />}
        <WhyNow />
        <Uses />
        {!topic && <Compatible />}
        <Steps />
        {page.type !== "country" && <Countries />}
        {!topic && <ApiBlock />}
        <Pricing initial={CUR[page.country]} />
        <Faq items={page.faq} />
        <FinalCta page={page} />
      </main>
      <Footer />
      <MobileCta />
    </div>
  );
}
