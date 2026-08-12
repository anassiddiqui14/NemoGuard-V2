import { useEffect, useMemo, useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { Activity, BellRing, BrainCircuit, LayoutDashboard, ShieldCheck } from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'investigation' | 'activity' | 'recovery'>('overview');

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

  useEffect(() => {
    setActiveTab('overview');
  }, [activeIncidentId]);

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
    <div className="flex flex-col xl:flex-row h-full min-h-0 w-full bg-app-bg text-text-primary overflow-y-auto xl:overflow-hidden selection:bg-primary/30">
      <Toaster position="top-right" />

      <IncidentQueue
        openIncidents={sortedIncidents}
        activeIncidentId={activeIncidentId}
        setActiveIncidentId={setActiveIncidentId}
        refreshQueue={refreshQueue}
      />

      <main className="flex-1 min-w-0 w-full p-3 sm:p-5 xl:overflow-y-auto flex flex-col gap-3 sm:gap-4 order-2 xl:order-none">
        <IncidentTabs activeTab={activeTab} setActiveTab={setActiveTab} alertCount={alerts.length} />

        {activeTab === 'overview' && (
          <SituationHeader
            selectedIncident={selectedIncident}
            alerts={alerts}
            impact={impact}
            hypothesis={hypothesis}
            triageStarting={triageStarting}
            handleStartTriage={handleStartTriage}
          />
        )}

        {activeTab === 'alerts' && <AlertsPanel alerts={alerts} expandedAlert={expandedAlert} setExpandedAlert={setExpandedAlert} />}

        {activeTab === 'investigation' && (
          <div className="flex-1 min-h-[520px]">
            <AgentAndHypothesisRow
              activeIncidentId={activeIncidentId}
              incidentStatus={selectedIncident?.status ?? 'UNKNOWN'}
              liveEvents={liveEvents}
              hypothesis={hypothesis}
              evidence={evidence}
              dataLoading={dataLoading}
              onViewEvidence={() => setIsEvidenceModalOpen(true)}
            />
          </div>
        )}

        {activeTab === 'activity' && (
          <div className="flex-1 min-h-[520px]">
            <ActivityAndImpactRow
              activeIncidentId={activeIncidentId}
              liveEvents={liveEvents}
              sseStatus={sseStatus}
              selectedSeverity={selectedIncident?.severity}
              impact={impact}
            />
          </div>
        )}

        {activeTab === 'recovery' && (
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
            onViewPlan={() => setIsModalOpen(true)}
            onExecute={handleExecute}
          />
        )}
      </main>

      {isEvidenceModalOpen && activeIncidentId && hypothesis && (
        <EvidenceModal hypothesis={hypothesis} evidence={evidence} onClose={() => setIsEvidenceModalOpen(false)} />
      )}

      {isModalOpen && activeIncidentId && plan && (
        <PlanApprovalModal incidentId={activeIncidentId} plan={plan} onClose={() => setIsModalOpen(false)} onRefreshPlan={() => refreshQueue()} />
      )}
    </div>
  );
}

function IncidentTabs({ activeTab, setActiveTab, alertCount }: {
  activeTab: 'overview' | 'alerts' | 'investigation' | 'activity' | 'recovery';
  setActiveTab: (tab: 'overview' | 'alerts' | 'investigation' | 'activity' | 'recovery') => void;
  alertCount: number;
}) {
  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
    { id: 'alerts' as const, label: 'Alerts', icon: <BellRing className="w-3.5 h-3.5" />, count: alertCount },
    { id: 'investigation' as const, label: 'Investigation', icon: <BrainCircuit className="w-3.5 h-3.5" /> },
    { id: 'activity' as const, label: 'Activity & impact', icon: <Activity className="w-3.5 h-3.5" /> },
    { id: 'recovery' as const, label: 'Recovery plan', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  ];
  return (
    <div className="w-full overflow-x-auto rounded-xl bg-white/[0.02] p-1 ring-1 ring-white/[0.06] flex-shrink-0" role="tablist" aria-label="Incident workspace sections">
      <div className="grid min-w-[700px] grid-cols-5 gap-1">
      {tabs.map((tab) => <button key={tab.id} onClick={() => setActiveTab(tab.id)} role="tab" aria-selected={activeTab === tab.id} className={`inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-2.5 text-[12px] font-medium transition-all ${activeTab === tab.id ? 'bg-primary/14 text-primary shadow-sm ring-1 ring-primary/25' : 'text-text-muted hover:bg-white/[0.04] hover:text-text-primary'}`}>
        {tab.icon}{tab.label}{typeof tab.count === 'number' && tab.count > 0 && <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[9px] font-bold">{tab.count}</span>}
      </button>)}</div>
    </div>
  );
}
