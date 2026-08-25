import { NavBar } from './NavBar';
import { HeroSection } from './HeroSection';
import { LifecycleShowcase } from './LifecycleShowcase';
import { EvidenceShowcase } from './EvidenceShowcase';
import { MetricsStrip } from './MetricsStrip';
import { FeatureGrid } from './FeatureGrid';
import { CtaBand } from './CtaBand';
import { Logomark } from './Brand';

function Footer() {
    return (
        <footer className="border-t border-white/[0.06] py-8 px-6">
            <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-primary">
                    <Logomark className="w-4 h-4" />
                    <span className="text-[12px] font-medium text-text-secondary">NemoGuard Command Center</span>
                </div>
                <span className="text-[11px] text-text-muted">Agentic incident response, coordinated end to end.</span>
            </div>
        </footer>
    );
}

export function LandingPage() {
    return (
        <div className="bg-app-bg min-h-screen w-full">
            <NavBar />
            <HeroSection />
            <LifecycleShowcase />
            <EvidenceShowcase />
            <MetricsStrip />
            <FeatureGrid />
            <CtaBand />
            <Footer />
        </div>
    );
}
