import { ShieldAlert, FileCheck, Sparkles } from 'lucide-react';
import { SafetyReviewBanner } from './SituationHeader';

interface Props {
    embedded?: boolean;
    hypothesis: any;
    evidence: any[];
    plan: any;
    dataLoading: boolean;
    isNeedsReview: boolean;
    safetyAcknowledged: boolean;
    setSafetyAcknowledged: (v: boolean) => void;
    canApprove: boolean;
    onViewPlan: () => void;
    onExecute: () => void;
}

export function RecoveryRail({
    embedded = false, hypothesis, evidence, plan, dataLoading, isNeedsReview, safetyAcknowledged, setSafetyAcknowledged, canApprove, onViewPlan, onExecute,
}: Props) {
    const executed = plan?.status === 'EXECUTED' || plan?.status === 'APPROVED';

    return (
        <aside className={embedded ? 'w-full min-h-[520px] glass-panel rounded-2xl overflow-hidden flex flex-col' : 'w-full xl:w-[300px] flex-shrink-0 border-t xl:border-t-0 xl:border-l border-white/[0.06] bg-black/20 flex flex-col z-10 order-3 xl:order-none'}>
            <div className="p-4 sm:p-5 pb-3 xl:pb-4">
                <div className="flex items-center gap-2 mb-1">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <div className="font-semibold text-[13px] text-text-primary">Decision & Recovery</div>
                </div>
                <div className="text-[11px] text-text-muted mb-3 ml-9">
                    {plan ? 'Recovery plan ready for review' : 'Plan formulation in progress'}
                </div>
                <div className="ml-9">
                    {isNeedsReview ? (
                        <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-critical/15 text-critical ring-1 ring-critical/30">NEEDS REVIEW</span>
                    ) : (
                        <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-warning/15 text-warning ring-1 ring-warning/30">
                            {plan ? 'PENDING APPROVAL' : 'PENDING'}
                        </span>
                    )}
                </div>
            </div>

            <div className="px-4 pb-3 xl:p-4 xl:flex-1 xl:overflow-y-auto space-y-3">
                {isNeedsReview && plan && (
                    <div className="space-y-2.5">
                        <SafetyReviewBanner feedback={plan.rationale} />
                        <label className="flex items-start gap-2 text-[11px] text-text-secondary cursor-pointer px-1">
                            <input
                                type="checkbox"
                                checked={safetyAcknowledged}
                                onChange={(e) => setSafetyAcknowledged(e.target.checked)}
                                className="mt-0.5 accent-critical"
                            />
                            I have reviewed the safety concern and choose to proceed anyway.
                        </label>
                    </div>
                )}

                <div className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05]">
                    <div className="font-medium text-[12px] text-text-secondary mb-3.5">Recovery formulation status</div>
                    <div className="space-y-3">
                        <StatusRow done={!!hypothesis} active={dataLoading} label="Root cause hypothesis created" />
                        <StatusRow done={evidence.length > 0} active={dataLoading && !!hypothesis} label="Blast radius calculated" />
                        <StatusRow done={!!plan} active={!plan && (dataLoading || !!hypothesis)} label="Matching approved runbook" />
                        <StatusRow done={!!plan && plan.status !== 'PENDING_APPROVAL' && plan.status !== 'NEEDS_REVIEW'} active={!!plan} label="Evaluating action risk" />
                        <StatusRow done={executed} active={!!plan && !executed} label="Preparing verification checks" />
                    </div>
                </div>

                {embedded && plan && (
                    <div className="rounded-xl p-4 sm:p-5 bg-white/[0.02] ring-1 ring-white/[0.05]">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                            <div><div className="font-semibold text-[14px] text-text-primary">Recommended recovery</div><div className="text-[11px] text-text-muted mt-0.5">Human approval remains required before execution.</div></div>
                            <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-warning/15 text-warning ring-1 ring-warning/30">{plan.overall_risk || 'MEDIUM'} RISK</span>
                        </div>
                        <p className="text-[13px] leading-relaxed text-text-secondary mb-4">{plan.rationale}</p>
                        <div className="grid gap-3 md:grid-cols-3">
                            {(plan.steps || []).map((step: any, index: number) => (
                                <div key={step.sequence_no || index} className="relative rounded-xl p-3.5 bg-app-bg/40 ring-1 ring-white/[0.06]">
                                    <div className="w-6 h-6 rounded-full bg-primary/15 text-primary text-[11px] font-bold flex items-center justify-center mb-3">{index + 1}</div>
                                    <div className="text-[12px] font-semibold text-text-primary mb-1">{step.title || `Step ${index + 1}`}</div>
                                    <div className="text-[11px] leading-relaxed text-text-muted">{step.action_type || step.instruction}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div className="p-4 pt-2 xl:pt-4 flex flex-col sm:flex-row xl:flex-col gap-2.5 mt-auto">
                <button
                    onClick={onViewPlan}
                    disabled={!plan}
                    className="w-full text-[13px] px-4 py-2.5 rounded-xl ring-1 ring-primary/40 text-primary hover:bg-primary/5 transition font-medium disabled:opacity-40 disabled:ring-white/[0.06] disabled:text-text-muted flex items-center justify-center gap-2"
                >
                    <FileCheck className="w-3.5 h-3.5" /> View exact plan
                </button>
                <button
                    disabled={!canApprove}
                    onClick={onExecute}
                    className="w-full text-[13px] px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold disabled:opacity-30 disabled:cursor-not-allowed shadow-lg shadow-primary/20 flex items-center justify-center gap-2"
                >
                    {isNeedsReview && !safetyAcknowledged && <ShieldAlert className="w-3.5 h-3.5" />}
                    {plan?.status === 'PENDING_APPROVAL' || plan?.status === 'NEEDS_REVIEW' ? 'Approve & Execute' : plan ? 'Execute Plan' : 'Plan not ready'}
                </button>
            </div>
        </aside>
    );
}

function StatusRow({ done, active, label }: { done: boolean; active: boolean; label: string }) {
    return (
        <div className="flex items-start gap-2.5">
            <div
                className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[8px] ${done ? 'bg-healthy text-app-bg' : active ? 'bg-agent-active/80 text-white animate-pulse' : 'ring-1 ring-white/[0.08] text-text-muted'
                    }`}
            >
                {done ? '✓' : active ? '●' : ''}
            </div>
            <div className={`text-[12px] ${done || active ? 'text-text-secondary' : 'text-text-muted'}`}>{label}</div>
        </div>
    );
}
