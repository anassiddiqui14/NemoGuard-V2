import { AnimatePresence, motion } from 'framer-motion';
import { ShieldAlert, FileCheck, Sparkles } from 'lucide-react';
import { SafetyReviewBanner } from './SituationHeader';
import { fadeInUp } from './shared';

interface Props {
    hypothesis: any;
    evidence: any[];
    plan: any;
    dataLoading: boolean;
    isNeedsReview: boolean;
    safetyAcknowledged: boolean;
    setSafetyAcknowledged: (v: boolean) => void;
    canApprove: boolean;
    isIncidentResolved?: boolean;
    onViewPlan: () => void;
    onExecute: () => void;
    // When true, renders as a full-width tab-content panel (spacious layout,
    // used inside WorkspaceTabs' "Recovery plan" tab) instead of the narrow
    // permanently-visible right-hand rail. This directly addresses feedback
    // that the always-visible narrow column made the main dashboard feel
    // cramped -- the recovery status/action UI is unchanged, just given full
    // width and only shown when the operator is actually looking at it.
    embedded?: boolean;
}

function StatusBadge({ isIncidentResolved, isNeedsReview, plan }: { isIncidentResolved?: boolean; isNeedsReview: boolean; plan: any }) {
    return (
        <AnimatePresence mode="wait">
            {isIncidentResolved ? (
                <motion.span key="resolved" {...fadeInUp} className="text-[10px] font-bold px-2 py-1 rounded-full bg-healthy/15 text-healthy ring-1 ring-healthy/30 inline-block">RESOLVED</motion.span>
            ) : isNeedsReview ? (
                <motion.span key="review" {...fadeInUp} className="text-[10px] font-bold px-2 py-1 rounded-full bg-critical/15 text-critical ring-1 ring-critical/30 inline-block">NEEDS REVIEW</motion.span>
            ) : (
                <motion.span key="pending" {...fadeInUp} className="text-[10px] font-bold px-2 py-1 rounded-full bg-warning/15 text-warning ring-1 ring-warning/30 inline-block">
                    {plan ? 'PENDING APPROVAL' : 'PENDING'}
                </motion.span>
            )}
        </AnimatePresence>
    );
}

function FormulationStatus({ hypothesis, evidence, plan, dataLoading, executed }: { hypothesis: any; evidence: any[]; plan: any; dataLoading: boolean; executed: boolean }) {
    return (
        <motion.div layout className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05]">
            <div className="font-medium text-[12px] text-text-secondary mb-3.5">Recovery formulation status</div>
            <div className="space-y-3">
                <StatusRow done={!!hypothesis} active={dataLoading} label="Root cause hypothesis created" />
                <StatusRow done={evidence.length > 0} active={dataLoading && !!hypothesis} label="Blast radius calculated" />
                <StatusRow done={!!plan} active={!plan && (dataLoading || !!hypothesis)} label="Matching approved runbook" />
                <StatusRow done={!!plan && plan.status !== 'PENDING_APPROVAL' && plan.status !== 'NEEDS_REVIEW'} active={!!plan} label="Evaluating action risk" />
                <StatusRow done={executed} active={!!plan && !executed} label="Preparing verification checks" />
            </div>
        </motion.div>
    );
}

function SafetyBlock({ isIncidentResolved, isNeedsReview, plan, safetyAcknowledged, setSafetyAcknowledged }: {
    isIncidentResolved?: boolean; isNeedsReview: boolean; plan: any; safetyAcknowledged: boolean; setSafetyAcknowledged: (v: boolean) => void;
}) {
    return (
        <AnimatePresence>
            {!isIncidentResolved && isNeedsReview && plan && (
                <motion.div {...fadeInUp} className="space-y-2.5">
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
                </motion.div>
            )}
        </AnimatePresence>
    );
}

function ActionButtons({ plan, canApprove, isIncidentResolved, isNeedsReview, safetyAcknowledged, onViewPlan, onExecute }: {
    plan: any; canApprove: boolean; isIncidentResolved?: boolean; isNeedsReview: boolean; safetyAcknowledged: boolean; onViewPlan: () => void; onExecute: () => void;
}) {
    return (
        <>
            <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={onViewPlan}
                disabled={!plan}
                className="w-full text-[13px] px-4 py-2.5 rounded-xl ring-1 ring-primary/40 text-primary hover:bg-primary/5 transition font-medium disabled:opacity-40 disabled:ring-white/[0.06] disabled:text-text-muted flex items-center justify-center gap-2"
            >
                <FileCheck className="w-3.5 h-3.5" /> View exact plan
            </motion.button>
            <motion.button
                whileTap={{ scale: 0.97 }}
                disabled={!canApprove}
                onClick={onExecute}
                className="w-full text-[13px] px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold disabled:opacity-30 disabled:cursor-not-allowed shadow-lg shadow-primary/20 flex items-center justify-center gap-2"
            >
                {!isIncidentResolved && isNeedsReview && !safetyAcknowledged && <ShieldAlert className="w-3.5 h-3.5" />}
                {isIncidentResolved
                    ? 'Plan Executed'
                    : plan?.status === 'PENDING_APPROVAL' || plan?.status === 'NEEDS_REVIEW'
                        ? 'Approve & Execute'
                        : plan
                            ? 'Execute Plan'
                            : 'Plan not ready'}
            </motion.button>
        </>
    );
}

export function RecoveryRail({
    hypothesis, evidence, plan, dataLoading, isNeedsReview, safetyAcknowledged, setSafetyAcknowledged, canApprove, isIncidentResolved, onViewPlan, onExecute, embedded = false,
}: Props) {
    const executed = plan?.status === 'EXECUTED' || plan?.status === 'APPROVED' || !!isIncidentResolved;

    if (embedded) {
        return (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }} className="glass-panel rounded-2xl ring-1 ring-white/[0.06] overflow-hidden">
                <div className="p-5 pb-4 flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.05]">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center">
                                <Sparkles className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div className="font-semibold text-[14px] text-text-primary">Decision & Recovery</div>
                        </div>
                        <div className="text-[11.5px] text-text-muted ml-9">
                            {isIncidentResolved ? 'Incident resolved — recovery complete' : plan ? 'Recovery plan ready for review' : 'Plan formulation in progress'}
                        </div>
                    </div>
                    <StatusBadge isIncidentResolved={isIncidentResolved} isNeedsReview={isNeedsReview} plan={plan} />
                </div>

                {/* Safety banner + acknowledgment now spans the FULL width above
                    the two-column grid instead of being squeezed into a narrow
                    left column, with the rationale text shown only ONCE (it was
                    previously duplicated -- both inside SafetyReviewBanner AND
                    again as a separate card in the right column below), which
                    was the main source of the cramped/redundant feel. */}
                {!isIncidentResolved && isNeedsReview && plan && (
                    <div className="px-5 pt-4">
                        <SafetyBlock
                            isIncidentResolved={isIncidentResolved}
                            isNeedsReview={isNeedsReview}
                            plan={plan}
                            safetyAcknowledged={safetyAcknowledged}
                            setSafetyAcknowledged={setSafetyAcknowledged}
                        />
                    </div>
                )}

                <div className="p-5 grid gap-4 md:grid-cols-[1.1fr_0.9fr] items-start">
                    <FormulationStatus hypothesis={hypothesis} evidence={evidence} plan={plan} dataLoading={dataLoading} executed={executed} />

                    <div className="flex flex-col gap-2.5">
                        {!isNeedsReview && plan?.rationale && (
                            <div className="rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.05] text-[12.5px] text-text-secondary leading-relaxed">
                                {plan.rationale}
                            </div>
                        )}
                        <ActionButtons
                            plan={plan}
                            canApprove={canApprove}
                            isIncidentResolved={isIncidentResolved}
                            isNeedsReview={isNeedsReview}
                            safetyAcknowledged={safetyAcknowledged}
                            onViewPlan={onViewPlan}
                            onExecute={onExecute}
                        />
                    </div>
                </div>
            </motion.div>
        );
    }

    return (
        <motion.aside
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            className="w-[300px] flex-shrink-0 border-l border-white/[0.06] bg-black/20 flex flex-col z-10"
        >
            <div className="p-5 pb-4">
                <div className="flex items-center gap-2 mb-1">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <div className="font-semibold text-[13px] text-text-primary">Decision & Recovery</div>
                </div>
                <div className="text-[11px] text-text-muted mb-3 ml-9">
                    {isIncidentResolved ? 'Incident resolved — recovery complete' : plan ? 'Recovery plan ready for review' : 'Plan formulation in progress'}
                </div>
                <div className="ml-9">
                    <StatusBadge isIncidentResolved={isIncidentResolved} isNeedsReview={isNeedsReview} plan={plan} />
                </div>
            </div>

            <div className="p-4 flex-1 overflow-y-auto space-y-3">
                <SafetyBlock
                    isIncidentResolved={isIncidentResolved}
                    isNeedsReview={isNeedsReview}
                    plan={plan}
                    safetyAcknowledged={safetyAcknowledged}
                    setSafetyAcknowledged={setSafetyAcknowledged}
                />
                <FormulationStatus hypothesis={hypothesis} evidence={evidence} plan={plan} dataLoading={dataLoading} executed={executed} />
            </div>

            <div className="p-4 flex flex-col gap-2.5 mt-auto">
                <ActionButtons
                    plan={plan}
                    canApprove={canApprove}
                    isIncidentResolved={isIncidentResolved}
                    isNeedsReview={isNeedsReview}
                    safetyAcknowledged={safetyAcknowledged}
                    onViewPlan={onViewPlan}
                    onExecute={onExecute}
                />
            </div>
        </motion.aside>
    );
}

function StatusRow({ done, active, label }: { done: boolean; active: boolean; label: string }) {
    return (
        <div className="flex items-start gap-2.5">
            <motion.div
                layout
                animate={{ scale: done ? [1, 1.15, 1] : 1 }}
                transition={{ duration: 0.35, ease: 'easeOut' }}
                className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[8px] ${done ? 'bg-healthy text-app-bg' : active ? 'bg-agent-active/80 text-white animate-pulse' : 'ring-1 ring-white/[0.08] text-text-muted'
                    }`}
            >
                {done ? '✓' : active ? '●' : ''}
            </motion.div>
            <div className={`text-[12px] transition-colors duration-300 ${done || active ? 'text-text-secondary' : 'text-text-muted'}`}>{label}</div>
        </div>
    );
}
