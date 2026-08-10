import { useEffect, useMemo, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { useIncidentData } from '../hooks/useIncidentData';
import { useIncidentEvents } from '../hooks/useIncidentEvents';
import { IncidentQueue } from './dashboard/IncidentQueue';
import { SituationHeader } from './dashboard/SituationHeader';
import { AlertsPanel, AgentAndHypothesisRow, ActivityAndImpactRow } from './dashboard/InvestigationPanels';
import { RecoveryRail } from './dashboard/RecoveryRail';
import { EvidenceModal } from './dashboard/EvidenceModal';
import { PlanApprovalModal } from './PlanApprovalModal';
import type { IncidentSummary } from './dashboard/shared';
import { needsAttention } from './dashboard/shared';

interface DashboardProps {
  focusIncidentId?: string | null;
  onFocusHandled?: () => void;
}

export function Dashboard({ focusIncidentId, onFocusHandled }: DashboardProps = {}) {
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);
  const [openIncidents, setOpenIncidents] = useState<IncidentSummary[]>([]);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [triageStarting, setTriageStarting] = useState(false);
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false);

  const { evidence, hypothesis, plan, impact, alerts, loading: dataLoading } = useIncidentData(activeIncidentId);
  const { events: liveEvents, status: sseStatus } = useIncidentEvents(activeIncidentId);

  const refreshQueue = async () => {
    try {
      const res = await fetch('/api/v2/incidents?state=open');
      const data = (await res.json()) as IncidentSummary[];
      setOpenIncidents(Array.isArray(data) ? data : []);
    } catch {
      setOpenIncidents([]);
    }
  };

  const selectedIncident = useMemo(
    () => openIncidents.find((i) => i.incident_id === activeIncidentId) ?? null,
    [openIncidents, activeIncidentId],
  );

  const handleExecute = async () => {
    if (!selectedIncident || !plan) return;
    try {
      const token = localStorage.getItem('nemoguard_token') || '';
      await fetch(`/api/v2/incidents/${selectedIncident.incident_id}/plans/${plan.action_plan_id}/approve`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approve', plan_hash: plan.plan_hash }),
      });
      refreshQueue();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStartTriage = async () => {
    if (!activeIncidentId) return;
    setTriageStarting(true);
    try {
      const token = localStorage.getItem('nemoguard_token') || '';
      await fetch(`/api/v2/incidents/${activeIncidentId}/triage`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      refreshQueue();
    } catch (e) {
      console.error(e);
    } finally {
      setTriageStarting(false);
    }
  };

  useEffect(() => {
    void refreshQueue();
    const t = window.setInterval(() => void refreshQueue(), 2000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (focusIncidentId) {
      setActiveIncidentId(focusIncidentId);
      onFocusHandled?.();
    }
  }, [focusIncidentId, onFocusHandled]);

  useEffect(() => {
    if (openIncidents.length === 0 && activeIncidentId) {
      setActiveIncidentId(null);
    } else if (!activeIncidentId && openIncidents.length > 0) {
      setActiveIncidentId(openIncidents[0].incident_id);
    } else if (activeIncidentId && openIncidents.length > 0 && !openIncidents.some((i) => i.incident_id === activeIncidentId)) {
      setActiveIncidentId(openIncidents[0].incident_id);
    }
  }, [activeIncidentId, openIncidents]);

  useEffect(() => {
    setSafetyAcknowledged(false);
  }, [plan?.action_plan_id]);

  const sortedIncidents = useMemo(() => {
    return [...openIncidents].sort((a, b) => {
      const aAttn = needsAttention(a.status) ? 0 : 1;
      const bAttn = needsAttention(b.status) ? 0 : 1;
      return aAttn - bAttn;
    });
  }, [openIncidents]);

  const isNeedsReview = plan?.status === 'NEEDS_REVIEW';
  const canApprove = !!plan && (!isNeedsReview || safetyAcknowledged);

  return (
    <div className="flex h-full min-h-0 bg-app-bg text-text-primary overflow-hidden selection:bg-primary/30">
      <Toaster position="top-right" />

      <IncidentQueue
        openIncidents={sortedIncidents}
        activeIncidentId={activeIncidentId}
        setActiveIncidentId={setActiveIncidentId}
        refreshQueue={refreshQueue}
      />

      <main className="flex-1 overflow-y-auto p-5 flex flex-col gap-4 min-w-0">
        <SituationHeader
          selectedIncident={selectedIncident}
          alerts={alerts}
          impact={impact}
          hypothesis={hypothesis}
          triageStarting={triageStarting}
          handleStartTriage={handleStartTriage}
        />

        <AlertsPanel alerts={alerts} expandedAlert={expandedAlert} setExpandedAlert={setExpandedAlert} />

        <AgentAndHypothesisRow
          activeIncidentId={activeIncidentId}
          incidentStatus={selectedIncident?.status ?? 'UNKNOWN'}
          liveEvents={liveEvents}
          hypothesis={hypothesis}
          evidence={evidence}
          dataLoading={dataLoading}
          onViewEvidence={() => setIsEvidenceModalOpen(true)}
        />

        <ActivityAndImpactRow
          activeIncidentId={activeIncidentId}
          liveEvents={liveEvents}
          sseStatus={sseStatus}
          selectedSeverity={selectedIncident?.severity}
          impact={impact}
        />
      </main>

      <RecoveryRail
        hypothesis={hypothesis}
        evidence={evidence}
        plan={plan}
        dataLoading={dataLoading}
        isNeedsReview={isNeedsReview}
        safetyAcknowledged={safetyAcknowledged}
        setSafetyAcknowledged={setSafetyAcknowledged}
        canApprove={canApprove}
        onViewPlan={() => setIsModalOpen(true)}
        onExecute={handleExecute}
      />

      {isEvidenceModalOpen && activeIncidentId && hypothesis && (
        <EvidenceModal hypothesis={hypothesis} evidence={evidence} onClose={() => setIsEvidenceModalOpen(false)} />
      )}

      {isModalOpen && activeIncidentId && plan && (
        <PlanApprovalModal incidentId={activeIncidentId} plan={plan} onClose={() => setIsModalOpen(false)} onRefreshPlan={() => refreshQueue()} />
      )}
    </div>
  );
}
