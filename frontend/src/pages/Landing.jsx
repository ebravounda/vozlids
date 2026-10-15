import { useEffect } from "react";
import { Pricing } from "@/components/Pricing";
import { Seo, pageByPath } from "@/components/Seo";
import { GeoProvider, useMarket } from "@/lib/geo";
import { Footer, MobileCta, Nav } from "@/components/landing/Chrome";
import { ApiBlock, Compatible, Faq, FinalCta, Hero, Steps, TopicSections, TrustBar, Uses, WhyNow } from "@/components/landing/Sections";


function useReveal(path) {
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } }), { threshold: 0.12 });
    document.querySelectorAll(".vl-reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [path]);
}

export default function Landing(props) {
  return <GeoProvider><LandingPage {...props} /></GeoProvider>;
}

const MARKET_PAGE = { ES: "/es", CL: "/cl" };

function LandingPage({ path = "/" }) {
  const page = pageByPath(path);
  const m = useMarket(page.country);
  const view = path === "/" && MARKET_PAGE[m.market] ? { ...pageByPath(MARKET_PAGE[m.market]), path: "/" } : page;
  useReveal(path);
  const topic = page.type === "topic";
  return (
    <div className="min-h-screen bg-white text-slate-700" style={{ fontFamily: "'DM Sans', sans-serif" }} data-testid={`marketing-page-${path === "/" ? "home" : path.slice(1)}`}>
      <Seo page={page} />
      <Nav />
      <main>
        <Hero page={view} m={m} />
        <TrustBar m={m} />
        {page.sections?.length > 0 && <TopicSections sections={page.sections} />}
        <WhyNow />
        <Uses m={m} />
        {!topic && <Compatible m={m} />}
        <Steps m={m} />
        {!topic && <ApiBlock />}
        <Pricing m={m} />
        <Faq items={view.faq} />
        <FinalCta page={view} m={m} />
      </main>
      <Footer m={m} />
      <MobileCta />
    </div>
  );
}
