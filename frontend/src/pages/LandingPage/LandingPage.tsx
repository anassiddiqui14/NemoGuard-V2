import { Suspense, lazy } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Sparkles, ArrowRight, Radio } from 'lucide-react';
import { LifecycleShowcase } from './LifecycleShowcase';
import { EvidenceShowcase } from './EvidenceShowcase';
import { MetricsStrip } from './MetricsStrip';
import { FeatureGrid } from './FeatureGrid';
import { CtaBand } from './CtaBand';

const HeroScene = lazy(() => import('./HeroScene').then((m) => ({ default: m.HeroScene })));

function HeroSection() {
    const navigate = useNavigate();
    const { scrollY } = useScroll();
    const heroOpacity = useTransform(scrollY, [0, 500], [1, 0]);
    const heroY = useTransform(scrollY, [0, 500], [0, 80]);
    const hasToken = !!localStorage.getItem('nemoguard_token');

    const handlePrimary = () => {
        navigate(hasToken ? '/app' : '/login');
    };

    return (
        <section className="relative h-screen w-full overflow-hidden flex items-center justify-center">
            <Suspense fallback={null}>
                <HeroScene />
            </Suspense>

            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-app-bg pointer-events-none" />

            <motion.div
                style={{ opacity: heroOpacity, y: heroY }}
                className="relative z-10 text-center px-8 py-12 max-w-3xl"
            >
                <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="inline-flex items-center gap-2 mb-7 px-3.5 py-1.5 rounded-full bg-white/[0.04] ring-1 ring-white/[0.1]"
                >
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-healthy opacity-60" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-healthy" />
                    </span>
                    <Radio className="w-3 h-3 text-text-muted" />
                    <span className="text-[11px] font-semibold text-text-secondary tracking-wide uppercase">
                        Live agentic incident response
                    </span>
                </motion.div>

                <h1
                    className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight leading-[1.1] mb-5"
                    style={{ textShadow: '0 2px 30px var(--app-bg), 0 2px 8px var(--app-bg)' }}
                >
                    <span className="text-text-primary">Agentic incident response,</span>
                    <br />
                    <motion.span
                        className="inline-block bg-clip-text text-transparent bg-[length:200%_auto]"
                        style={{
                            backgroundImage: 'linear-gradient(90deg, #A5B4FC, #F0ABFC, #6366F1, #A5B4FC)',
                        }}
                        animate={{ backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'] }}
                        transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
                    >
                        coordinated end to end.
                    </motion.span>
                </h1>

                <p
                    className="text-[14.5px] sm:text-[15.5px] text-text-muted leading-relaxed mb-7 max-w-xl mx-auto"
                    style={{ textShadow: '0 2px 16px var(--app-bg)' }}
                >
                    Six coordinated agents investigate, plan, and recover — with a human always at the risk
                    boundary, backed by a <span className="text-text-secondary font-medium">real, running orchestration system</span>.
                </p>

                <div className="flex items-center justify-center gap-3 flex-wrap">
                    <motion.button
                        whileHover={{ scale: 1.03 }}
                        whileTap={{ scale: 0.97 }}
                        onClick={handlePrimary}
                        className="relative inline-flex items-center gap-2 text-[15px] px-7 py-3.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white font-semibold shadow-2xl shadow-primary/40 overflow-hidden group"
                    >
                        <span className="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 skew-x-12" />
                        <span className="relative z-10 flex items-center gap-2">
                            {hasToken ? 'Enter Command Center' : 'Sign in to enter'}
                            <ArrowRight className="w-4 h-4" />
                        </span>
                    </motion.button>
                </div>
            </motion.div>

            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1, duration: 1 }}
                className="absolute bottom-8 left-1/2 -translate-x-1/2 text-text-muted text-[11px] flex flex-col items-center gap-1.5"
            >
                <span>Scroll to see how it works</span>
                <motion.div
                    animate={{ y: [0, 6, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                    className="w-1 h-1 rounded-full bg-text-muted"
                />
            </motion.div>
        </section>
    );
}

function Footer() {
    return (
        <footer className="border-t border-white/[0.06] py-8 px-6">
            <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-primary" />
                    <span className="text-[12px] font-medium text-text-secondary">NemoGuard Command Center</span>
                </div>
            </div>
        </footer>
    );
}

export function LandingPage() {
    return (
        <div className="bg-app-bg min-h-screen w-full">
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
