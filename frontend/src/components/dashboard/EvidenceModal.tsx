import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { X, Sparkles, ShieldCheck, ShieldAlert, ShieldQuestion, Shield } from 'lucide-react';
import { modalBackdrop, modalPanel } from './shared';

// Evidence authority (spec §9.2): AUTHORITATIVE/HIGH/MEDIUM/LOW is now
// computed deterministically in code (src/domain/evidence_authority.py)
// and stored on every evidence row -- this maps that value to a visible
// badge so operators can see at a glance how trustworthy each piece of
// evidence actually is, rather than treating a raw CloudWatch log line
// identically to inferred/derived text.
const AUTHORITY_STYLES: Record<string, { icon: ReactNode; className: string; label: string }> = {
    AUTHORITATIVE: {
        icon: <ShieldCheck className="w-3 h-3" />,
        className: 'bg-healthy/15 text-healthy ring-healthy/30',
        label: 'Authoritative',
    },
    HIGH: {
        icon: <Shield className="w-3 h-3" />,
        className: 'bg-primary/15 text-primary ring-primary/30',
        label: 'High',
    },
    MEDIUM: {
        icon: <ShieldQuestion className="w-3 h-3" />,
        className: 'bg-warning/15 text-warning ring-warning/30',
        label: 'Medium',
    },
    LOW: {
        icon: <ShieldAlert className="w-3 h-3" />,
        className: 'bg-critical/15 text-critical ring-critical/30',
        label: 'Low',
    },
};

function AuthorityBadge({ authority }: { authority?: string }) {
    const style = AUTHORITY_STYLES[authority || 'MEDIUM'] || AUTHORITY_STYLES.MEDIUM;
    return (
        <span className={`inline-flex items-center gap-1 text-[9.5px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full ring-1 ${style.className}`}>
            {style.icon} {style.label}
        </span>
    );
}

// Ranked hypothesis ledger (spec §10.1): shows every competing hypothesis
// the RCA agent considered, not just the top pick, with per-hypothesis
// confidence and supporting/contradicting evidence counts so an operator
// can see the actual reasoning process rather than a single unexplained
// conclusion.
function HypothesisLedger({ hypotheses }: { hypotheses: any[] }) {
    if (!hypotheses || hypotheses.length < 2) return null;
    return (
        <div className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05] space-y-2.5">
            <h4 className="text-[11px] font-bold text-text-muted uppercase tracking-wider mb-1">
                Hypothesis Ledger — {hypotheses.length} competing explanations considered
            </h4>
            {hypotheses.map((h, idx) => {
                const supporting = h.supporting_evidence_ids?.length ?? 0;
                const contradicting = h.contradicting_evidence_ids?.length ?? 0;
                const confidencePct = Math.round((h.confidence_score ?? 0) * 100);
                return (
                    <div key={h.hypothesis_id || idx} className="flex items-start gap-3 py-1.5">
                        <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5 ${idx === 0 ? 'bg-primary/20 text-primary' : 'bg-white/[0.05] text-text-muted'}`}>
                            #{idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-[12.5px] text-text-primary font-medium">{h.statement}</span>
                            </div>
                            <div className="flex items-center gap-3 mt-1 text-[10.5px] text-text-muted">
                                <span>Confidence: <span className="font-mono text-text-secondary">{confidencePct}%</span></span>
                                {supporting > 0 && <span className="text-healthy">+{supporting} supporting</span>}
                                {contradicting > 0 && <span className="text-critical">-{contradicting} contradicting</span>}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export function EvidenceModal({ hypothesis, hypotheses, evidence, onClose }: { hypothesis: any; hypotheses?: any[]; evidence: any[]; onClose: () => void }) {
    return (
        <motion.div {...modalBackdrop} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <motion.div {...modalPanel} className="glass-panel rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden ring-1 ring-white/[0.08]">
                <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center">
                            <Sparkles className="w-4 h-4 text-primary" />
                        </div>
                        <h2 className="text-[15px] font-semibold text-text-primary">Evidence & Grounding</h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/[0.06] rounded-full transition-colors text-text-muted hover:text-text-primary">
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="p-6 overflow-y-auto space-y-4">
                    <div>
                        <h3 className="font-semibold text-text-primary text-[14px]">Hypothesis: {hypothesis?.title}</h3>
                        <p className="text-[13px] text-text-secondary mb-4 mt-1 leading-relaxed">{hypothesis?.statement || 'Root cause identified based on logs and metrics.'}</p>
                    </div>

                    {hypotheses && <HypothesisLedger hypotheses={hypotheses} />}

                    <div className="space-y-3">
                        {evidence.map((ev, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.2, delay: idx * 0.04 }}
                                className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05]"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="text-[10px] font-bold text-agent-active uppercase tracking-wider">{ev.evidence_type}</span>
                                        <AuthorityBadge authority={ev.authority} />
                                    </div>
                                    <span className="text-[10px] text-text-muted font-mono">{ev.source_system} | {ev.source_record_id || ev.source}</span>
                                </div>
                                <div className="text-[13px] font-medium text-text-primary mb-2">{ev.title}</div>
                                <pre className="text-[11.5px] text-text-secondary bg-black/30 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono ring-1 ring-white/[0.04]">
                                    {ev.excerpt || ev.description}
                                </pre>
                            </motion.div>
                        ))}
                        {evidence.length === 0 && (
                            <div className="text-center text-text-muted p-8 rounded-xl ring-1 ring-white/[0.06] ring-dashed">
                                No concrete evidence items recorded yet.
                            </div>
                        )}
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
}
