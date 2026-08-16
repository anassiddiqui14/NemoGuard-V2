import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Sparkles, ShieldCheck } from 'lucide-react';

const HYPOTHESES = [
    { rank: 1, title: 'DEP-442 introduced an incompatible schema mapping', confidence: 91, status: 'Probable cause', tone: 'agent-active' },
    { rank: 2, title: 'Source file omitted an expected field', confidence: 34, status: 'Less likely', tone: 'warning' },
    { rank: 3, title: 'Database connectivity caused the failure', confidence: 8, status: 'Rejected', tone: 'text-muted' },
];

export function EvidenceShowcase() {
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: '-15% 0px' });

    return (
        <section ref={ref} className="py-24 px-6 max-w-5xl mx-auto">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.5 }}
                className="text-center mb-12"
            >
                <h2 className="text-2xl sm:text-3xl font-semibold text-text-primary tracking-tight mb-3">
                    Evidence before conclusions
                </h2>
                <p className="text-[14px] text-text-muted max-w-xl mx-auto">
                    Every root-cause claim is ranked, evidence-linked, and never asserted without support.
                </p>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <motion.div
                    initial={{ opacity: 0, x: -24 }}
                    animate={inView ? { opacity: 1, x: 0 } : {}}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.08]"
                >
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-4">Ranked Hypotheses</div>
                    <div className="space-y-3">
                        {HYPOTHESES.map((h) => (
                            <div key={h.rank} className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] ring-1 ring-white/[0.05]">
                                <div className="text-[11px] font-bold text-text-muted w-4">{h.rank}</div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[12.5px] text-text-primary truncate">{h.title}</div>
                                    <div className={`text-[10px] mt-0.5 ${h.tone === 'agent-active' ? 'text-agent-active' : h.tone === 'warning' ? 'text-warning' : 'text-text-muted'}`}>
                                        {h.status}
                                    </div>
                                </div>
                                <div className="text-[15px] font-bold tabular-nums flex-shrink-0" style={{ color: h.rank === 1 ? '#C026D3' : h.rank === 2 ? '#FBBF24' : undefined }}>
                                    {h.confidence}%
                                </div>
                            </div>
                        ))}
                    </div>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, x: 24 }}
                    animate={inView ? { opacity: 1, x: 0 } : {}}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.08] flex flex-col"
                >
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-4">Recovery Plan</div>
                    <div className="rounded-xl p-4 bg-gradient-to-br from-warning/10 to-transparent ring-1 ring-warning/25 mb-3">
                        <div className="flex items-center gap-2 mb-1.5">
                            <ShieldCheck className="w-3.5 h-3.5 text-warning" />
                            <span className="text-[10px] font-bold uppercase tracking-wide text-warning">Risk: Medium · Approval required</span>
                        </div>
                        <div className="text-[13px] text-text-primary font-medium">Restore previous schema mapping and resume processing</div>
                    </div>
                    <div className="flex-1 space-y-1.5 mb-4">
                        {['Restore mapping version v17', 'Validate required columns', 'Retry reservation ingestion', 'Verify row count and output schema'].map((step, i) => (
                            <div key={i} className="flex items-center gap-2 text-[11.5px] text-text-secondary">
                                <span className="w-4 h-4 rounded-full bg-white/[0.04] ring-1 ring-white/[0.08] flex items-center justify-center text-[8px] text-text-muted flex-shrink-0">{i + 1}</span>
                                {step}
                            </div>
                        ))}
                    </div>
                    <button
                        disabled
                        className="w-full flex items-center justify-center gap-2 text-[12.5px] px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white font-semibold opacity-90 cursor-default"
                    >
                        <Sparkles className="w-3.5 h-3.5" /> Approve MEDIUM-risk plan
                    </button>
                </motion.div>
            </div>
        </section>
    );
}
