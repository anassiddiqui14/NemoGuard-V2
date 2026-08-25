import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, CheckCircle2, Circle, Radio } from 'lucide-react';
import { Logomark } from './Brand';

interface Stage {
    id: string;
    status: string;
    tone: 'critical' | 'warning' | 'healthy';
    lines: string[];
}

const STAGES: Stage[] = [
    {
        id: 'detected',
        status: 'Detected',
        tone: 'critical',
        lines: [
            '7 alerts correlated → 1 incident',
            'Watcher agent opened INC-2291',
            'Severity classified: SEV-2',
        ],
    },
    {
        id: 'investigating',
        status: 'Investigating',
        tone: 'warning',
        lines: [
            'RCA ranked 3 hypotheses by evidence',
            'Top cause: DEP-442 schema mismatch (91%)',
            'Recovery plan drafted — awaiting approval',
        ],
    },
    {
        id: 'resolved',
        status: 'Resolved',
        tone: 'healthy',
        lines: [
            'Human approved MEDIUM-risk plan',
            'Verifier confirmed 6/6 checks passed',
            'INC-2291 closed in 3m 42s',
        ],
    },
];

const TONE_MAP: Record<Stage['tone'], { dot: string; text: string; ring: string }> = {
    critical: { dot: 'bg-critical', text: 'text-critical', ring: 'ring-critical/25' },
    warning: { dot: 'bg-warning', text: 'text-warning', ring: 'ring-warning/25' },
    healthy: { dot: 'bg-healthy', text: 'text-healthy', ring: 'ring-healthy/25' },
};

function ConsolePreview({ stageIndex }: { stageIndex: number }) {
    const stage = STAGES[stageIndex];
    const tone = TONE_MAP[stage.tone];

    return (
        <div className="console-surface rounded-2xl p-5 sm:p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-text-muted">INC-2291</span>
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.03] ring-1 ${tone.ring}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${tone.dot} status-breath`} />
                    <span className={`text-[10px] font-semibold uppercase tracking-wide ${tone.text}`}>
                        {stage.status}
                    </span>
                </div>
            </div>

            <div className="space-y-2.5 min-h-[112px]">
                {stage.lines.map((line, i) => (
                    <motion.div
                        key={`${stage.id}-${i}`}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.08, duration: 0.3 }}
                        className="flex items-start gap-2.5"
                    >
                        {i < stage.lines.length - 1 || stageIndex === 2 ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-healthy mt-0.5 flex-shrink-0" />
                        ) : (
                            <Circle className="w-3.5 h-3.5 text-text-muted mt-0.5 flex-shrink-0" />
                        )}
                        <span className="text-[12.5px] text-text-secondary leading-relaxed font-mono">{line}</span>
                    </motion.div>
                ))}
            </div>

            <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between">
                <div className="flex gap-1">
                    {STAGES.map((s, i) => (
                        <span
                            key={s.id}
                            className={`h-1 rounded-full transition-all duration-300 ${i === stageIndex ? 'w-6 bg-primary' : 'w-2 bg-white/[0.1]'
                                }`}
                        />
                    ))}
                </div>
                <span className="text-[10px] text-text-muted font-mono">live demo environment</span>
            </div>
        </div>
    );
}

export function HeroSection() {
    const navigate = useNavigate();
    const sectionRef = useRef<HTMLDivElement>(null);
    const [stageIndex, setStageIndex] = useState(0);
    const hasToken = !!localStorage.getItem('nemoguard_token');

    const { scrollYProgress } = useScroll({
        target: sectionRef,
        offset: ['start start', 'end start'],
    });

    useEffect(() => {
        const unsubscribe = scrollYProgress.on('change', (v) => {
            const idx = Math.min(STAGES.length - 1, Math.floor(v * STAGES.length));
            setStageIndex(idx);
        });
        return unsubscribe;
    }, [scrollYProgress]);

    const contentOpacity = useTransform(scrollYProgress, [0, 0.85, 1], [1, 1, 0]);

    const handlePrimary = () => {
        navigate(hasToken ? '/app' : '/login');
    };

    return (
        <section id="top" ref={sectionRef} className="relative w-full" style={{ height: '170vh' }}>
            <div className="sticky top-0 h-screen w-full overflow-hidden flex items-center">
                <div className="absolute inset-0 signal-grid opacity-60 pointer-events-none" />
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-app-bg pointer-events-none" />

                <motion.div
                    style={{ opacity: contentOpacity }}
                    className="relative z-10 max-w-6xl mx-auto w-full px-6 pt-16 grid lg:grid-cols-[1.1fr_0.9fr] gap-12 items-center"
                >
                    <div>
                        <motion.div
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.1 }}
                            className="inline-flex items-center gap-2 mb-6 px-3 py-1.5 rounded-full bg-white/[0.04] ring-1 ring-white/[0.1]"
                        >
                            <Radio className="w-3 h-3 text-primary" />
                            <span className="text-[11px] font-semibold text-text-secondary tracking-wide uppercase">
                                Live agentic incident response
                            </span>
                        </motion.div>

                        <motion.h1
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.15 }}
                            className="text-[2.5rem] sm:text-5xl md:text-[3.4rem] font-bold tracking-tight leading-[1.08] mb-5 text-text-primary"
                        >
                            Incidents move through
                            <br />
                            a real state machine —
                            <br />
                            <span className="text-primary">not a chat window.</span>
                        </motion.h1>

                        <motion.p
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.22 }}
                            className="text-[15px] text-text-muted leading-relaxed mb-8 max-w-md"
                        >
                            Six coordinated agents investigate, decide, and recover — with a human always at the
                            risk boundary. Scroll to watch one incident move end to end.
                        </motion.p>

                        <motion.div
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            className="flex items-center gap-3 flex-wrap"
                        >
                            <button
                                onClick={handlePrimary}
                                className="press-scale inline-flex items-center gap-2 text-[14.5px] px-6 py-3 rounded-xl bg-primary text-white font-semibold shadow-lg shadow-primary/30 hover:brightness-110 transition"
                            >
                                {hasToken ? 'Enter Command Center' : 'Sign in to enter'}
                                <ArrowRight className="w-4 h-4" />
                            </button>
                            <div className="flex items-center gap-1.5 text-text-muted">
                                <Logomark className="w-4 h-4 opacity-60" />
                                <span className="text-[12px]">Running against a real orchestration backend</span>
                            </div>
                        </motion.div>
                    </div>

                    <div className="hidden lg:flex justify-center">
                        <ConsolePreview stageIndex={stageIndex} />
                    </div>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1, duration: 1 }}
                    className="absolute bottom-8 left-1/2 -translate-x-1/2 text-text-muted text-[11px] flex flex-col items-center gap-1.5"
                >
                    <span>Scroll to follow the incident</span>
                    <motion.div
                        animate={{ y: [0, 6, 0] }}
                        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                        className="w-1 h-1 rounded-full bg-text-muted"
                    />
                </motion.div>
            </div>
        </section>
    );
}
