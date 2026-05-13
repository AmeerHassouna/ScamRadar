import { FaqsSection } from "@/components/ui/faqs-1";

export function FAQSection() {
    return (
        <section id="faq" className="relative bg-black border-t border-white/5" style={{ overflow: "visible" }}>
            <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-6%", left: "5%", width: "45%", height: "45%", background: "radial-gradient(ellipse at 20% 20%, rgba(34,197,94,0.10) 0%, transparent 65%)", filter: "blur(70px)" }} />
            <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "35%", right: "0%", width: "45%", height: "45%", background: "radial-gradient(ellipse at 85% 50%, rgba(34,197,94,0.08) 0%, transparent 65%)", filter: "blur(70px)" }} />
            <div className="relative" style={{ zIndex: 10 }}>
                <FaqsSection />
            </div>
        </section>
    );
}
