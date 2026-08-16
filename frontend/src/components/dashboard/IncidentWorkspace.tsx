import { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { ArrowLeft, AlertTriangle } from 'lucide-react';
import { useIncidentData } from '../../hooks/useIncidentData';
import { useIncidentEvents } from '../../hooks/useIncidentEvents';
import { authFetch } from '../../contexts/AuthGateContext';
import { SituationHeader } from './SituationHeader';
import { AlertsPanel, AgentAndHypothesisRow, ActivityAndImpactRow } from './InvestigationPanels';
import { RecoveryRail } from './RecoveryRail';
import { EvidenceModal } from './EvidenceModal';
import { PlanApprovalModal } from '../PlanApprovalModal';
import { WorkspaceTabs } from './WorkspaceTabs';
import { EmptyState } from './shared';
import type { IncidentSummary } from './shared';

interface Props {
    incidentId: string | null;
    selectedIncident: IncidentSummary | null;
    // Called after any action that changes incident/plan state (triage
    // started, plan approved) so the parent's incident list/queue reflects
    // the change without the workspace needing to know how the parent
    // fetches its data.
    onRefreshParent: () => void;
    // When provided, renders a "Back to incidents" control above the
    // workspace and the whole thing is meant to be shown INLINE within the
    // page that provided it (e.g. the Incidents page), rather than
    // navigating the user elsewhere to view incident details.
    onBack?: () => void;
}

/**
 * The full single-incident workspace (situation header, alerts,
 * investigation, activity/impact, recovery plan) factored out of
 * `Dashboard.tsx` so it can be reused by any page that wants to show a
 * specific incident's detail INLINE, with its own back-navigation, instead
 * of forcing every "view incident" action to jump to the Command Center
 * dashboard.
 */
export function IncidentWorkspace({ incidentId, selectedIncident, onRefreshParent, onBack }: Props) {
    const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);
    const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [triageStarting, setTriageStarting] = useState(false);
    const [safetyAcknowledged, setSafetyAcknowledged] = useState(false);

    const { evidence, hypothesis, hypotheses, plan, impact, alerts, loading: dataLoading } = useIncidentData(incidentId);
    const { events: liveEvents, status: sseStatus } = useIncidentEvents(incidentId);

    useEffect(() => {
        setSafetyAcknowledged(false);
    }, [plan?.action_plan_id]);

    const handleExecute = async () => {
        if (!selectedIncident || !plan) return;
        try {
            const res = await authFetch(`/api/v2/incidents/${selectedIncident.incident_id}/plans/${plan.action_plan_id}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ decision: 'approve', plan_hash: plan.plan_hash }),
            });
            if (!res.ok) {
                let detail = `HTTP ${res.status}`;
                try {
                    const body = await res.json();
                    detail = body?.detail || detail;
                } catch {
                    // response wasn't JSON; fall back to the status code above
                }
                toast.error(`Failed to execute plan: ${detail}`);
                return;
            }

            toast.success('Plan approved — executing recovery actions.');
            onRefreshParent();

            // Approval is asynchronous when Temporal owns the workflow. Poll
            // the authoritative incident record briefly so the operator gets a
            // definitive result rather than an approval toast followed by a
            // stale-looking workspace.
            for (let attempt = 0; attempt < 12; attempt += 1) {
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
                const statusRes = await authFetch(`/api/v2/incidents/${selectedIncident.incident_id}`);
                if (!statusRes.ok) continue;
                const updatedIncident = await statusRes.json();
                const status = String(updatedIncident.status || '').toUpperCase();

                if (status === 'RESOLVED') {
                    toast.success('Recovery verified — incident resolved.');
                    onRefreshParent();
                    return;
                }

                if (status === 'FAILED') {
                    toast.error('Recovery completed but verification failed — incident escalated for follow-up.', { duration: 7000 });
                    onRefreshParent();
                    return;
                }
            }

            // The plan is still running or the workflow is taking longer than
            // the short UI polling window. Its latest state continues to be
            // refreshed by useIncidentData.
            toast('Recovery execution is still in progress. Live status will update automatically.', { icon: '⏳' });
        } catch (e) {
            toast.error(`Failed to execute plan: ${e instanceof Error ? e.message : 'network error'}`);
        }
    };

    const handleStartTriage = async () => {
        if (!incidentId) return;
        setTriageStarting(true);
        try {
            const res = await authFetch(`/api/v2/incidents/${incidentId}/triage`, {
                method: 'POST',
            });
            if (!res.ok) {
                let detail = `HTTP ${res.status}`;
                try {
                    const body = await res.json();
                    detail = body?.detail || detail;
                } catch {
                    // response wasn't JSON; fall back to the status code above
                }
                toast.error(`Failed to start triage: ${detail}`);
                return;
            }
            onRefreshParent();
        } catch (e) {
            toast.error(`Failed to start triage: ${e instanceof Error ? e.message : 'network error'}`);
        } finally {
            setTriageStarting(false);
        }
    };

    const isNeedsReview = plan?.status === 'NEEDS_REVIEW';
    const isIncidentResolved = selectedIncident?.status?.toUpperCase() === 'RESOLVED';
    const isPlanExecuted = plan?.status === 'EXECUTED' || plan?.status === 'APPROVED';
    const canApprove = !!plan && !isPlanExecuted && !isIncidentResolved && (!isNeedsReview || safetyAcknowledged);

    if (!incidentId) {
        return (
            <div className="flex flex-col gap-4">
                {onBack && (
                    <button
                        onClick={onBack}
                        className="press-scale self-start flex items-center gap-1.5 text-[12.5px] font-medium text-text-secondary hover:text-text-primary px-3 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors"
                    >
                        <ArrowLeft className="w-3.5 h-3.5" /> Back to incidents
                    </button>
                )}
                <div className="glass-panel rounded-2xl ring-1 ring-white/[0.06] min-h-[300px] flex items-center justify-center">
                    <EmptyState icon={<AlertTriangle className="w-5 h-5" />} title="No incident selected" subtitle="Choose an incident to view its full detail." />
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4">
            {onBack && (
                <button
                    onClick={onBack}
                    className="press-scale self-start flex items-center gap-1.5 text-[12.5px] font-medium text-text-secondary hover:text-text-primary px-3 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors"
                >
                    <ArrowLeft className="w-3.5 h-3.5" /> Back to incidents
                </button>
            )}

            <WorkspaceTabs
                alertCount={alerts.length}
                overview={
                    <SituationHeader
                        selectedIncident={selectedIncident}
                        alerts={alerts}
                        impact={impact}
                        hypothesis={hypothesis}
                        triageStarting={triageStarting}
                        handleStartTriage={handleStartTriage}
                    />
                }
                investigation={
                    <AgentAndHypothesisRow
                        activeIncidentId={incidentId}
                        incidentStatus={selectedIncident?.status ?? 'UNKNOWN'}
                        liveEvents={liveEvents}
                        hypothesis={hypothesis}
                        evidence={evidence}
                        dataLoading={dataLoading}
                        onViewEvidence={() => setIsEvidenceModalOpen(true)}
                    />
                }
                evidence={
                    <AlertsPanel alerts={alerts} expandedAlert={expandedAlert} setExpandedAlert={setExpandedAlert} />
                }
                activity={
                    <ActivityAndImpactRow
                        activeIncidentId={incidentId}
                        liveEvents={liveEvents}
                        sseStatus={sseStatus}
                        selectedSeverity={selectedIncident?.severity}
                        impact={impact}
                    />
                }
                recovery={
                    <RecoveryRail
                        embedded
                        hypothesis={hypothesis}
                        evidence={evidence}
                        plan={plan}
                        dataLoading={dataLoading}
                        isNeedsReview={isNeedsReview}
                        safetyAcknowledged={safetyAcknowledged}
                        setSafetyAcknowledged={setSafetyAcknowledged}
                        canApprove={canApprove}
                        isIncidentResolved={isIncidentResolved}
                        onViewPlan={() => setIsModalOpen(true)}
                        onExecute={handleExecute}
                    />
                }
            />

            <AnimatePresence>
                {isEvidenceModalOpen && hypothesis && (
                    <EvidenceModal hypothesis={hypothesis} hypotheses={hypotheses} evidence={evidence} onClose={() => setIsEvidenceModalOpen(false)} />
                )}
            </AnimatePresence>

            <AnimatePresence>
                {isModalOpen && plan && (
                    <PlanApprovalModal incidentId={incidentId} plan={plan} onClose={() => setIsModalOpen(false)} onRefreshPlan={onRefreshParent} />
                )}
            </AnimatePresence>
        </div>
    );
}
