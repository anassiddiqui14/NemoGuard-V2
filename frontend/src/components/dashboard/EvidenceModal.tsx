import { X, Sparkles } from 'lucide-react';

export function EvidenceModal({ hypothesis, evidence, onClose }: { hypothesis: any; evidence: any[]; onClose: () => void }) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="glass-panel rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden ring-1 ring-white/[0.08]">
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
                    <div className="space-y-3">
                        {evidence.map((ev, idx) => (
                            <div key={idx} className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05]">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-[10px] font-bold text-agent-active uppercase tracking-wider">{ev.evidence_type}</span>
                                    <span className="text-[10px] text-text-muted font-mono">{ev.source_system} | {ev.source_record_id || ev.source}</span>
                                </div>
                                <div className="text-[13px] font-medium text-text-primary mb-2">{ev.title}</div>
                                <pre className="text-[11.5px] text-text-secondary bg-black/30 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono ring-1 ring-white/[0.04]">
                                    {ev.excerpt || ev.description}
                                </pre>
                            </div>
                        ))}
                        {evidence.length === 0 && (
                            <div className="text-center text-text-muted p-8 rounded-xl ring-1 ring-white/[0.06] ring-dashed">
                                No concrete evidence items recorded yet.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
