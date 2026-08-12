import { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowUpRight, BrainCircuit, CircleAlert, Clock3, Database, FileSearch, Layers3, Radio, ShieldCheck } from 'lucide-react';
import type { IncidentSummary } from './dashboard/shared';
import { formatElapsedSeconds, severityPill, statusBadge } from './dashboard/shared';

type Page = 'incidents' | 'operations' | 'intelligence';

function useIncidents() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch('/api/v2/incidents?state=all');
        const data = await response.json();
        setIncidents(Array.isArray(data) ? data : []);
      } catch {
        setIncidents([]);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  return incidents;
}

const card = 'glass-panel rounded-2xl p-4 sm:p-5';

export function WorkspacePage({ page, onOpenIncident }: { page: Page; onOpenIncident: (id: string) => void }) {
  const incidents = useIncidents();
  const critical = incidents.filter((item) => item.severity?.toUpperCase() === 'SEV-1').length;
  const attention = incidents.filter((item) => ['NEEDS_REVIEW', 'AWAITING_APPROVAL'].includes(item.status?.toUpperCase())).length;

  const copy = {
    incidents: { eyebrow: 'Incident management', title: 'Every active incident, prioritized for action.', subtitle: 'Review ownership, severity, state, and elapsed time — then open an incident in the Command Center.' },
    operations: { eyebrow: 'Operations', title: 'Keep autonomous response moving.', subtitle: 'A focused operational view of service readiness, agent activity, and approval work.' },
    intelligence: { eyebrow: 'Intelligence', title: 'Understand risk across your response system.', subtitle: 'A decision-ready snapshot of incident pressure, safety controls, and investigation coverage.' },
  }[page];

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
      <div className="max-w-6xl mx-auto space-y-5 sm:space-y-6">
        <section className="relative overflow-hidden rounded-3xl p-5 sm:p-7 glass-panel">
          <div className="absolute -top-20 -right-16 w-56 h-56 rounded-full bg-primary/15 blur-3xl pointer-events-none" />
          <div className="relative">
            <div className="text-[11px] uppercase tracking-[0.16em] font-bold text-primary mb-2">{copy.eyebrow}</div>
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">{copy.title}</h2>
            <p className="mt-2 max-w-2xl text-sm sm:text-[15px] leading-relaxed text-text-secondary">{copy.subtitle}</p>
          </div>
        </section>

        {page === 'incidents' && <><IncidentPage incidents={incidents.filter((incident) => incident.status?.toUpperCase() !== 'RESOLVED')} onOpenIncident={onOpenIncident} /><ResolvedIncidents incidents={incidents.filter((incident) => incident.status?.toUpperCase() === 'RESOLVED')} onOpenIncident={onOpenIncident} /></>}
        {page === 'operations' && <OperationsPage incidents={incidents} attention={attention} />}
        {page === 'intelligence' && <IntelligencePage incidents={incidents} critical={critical} attention={attention} />}
      </div>
    </div>
  );
}

function IncidentPage({ incidents, onOpenIncident }: { incidents: IncidentSummary[]; onOpenIncident: (id: string) => void }) {
  return (
    <section className={card}>
      <div className="flex flex-wrap gap-3 items-end justify-between mb-4">
        <div><h3 className="font-semibold">Active incident queue</h3><p className="text-xs text-text-muted mt-1">Live updates every five seconds</p></div>
        <span className="rounded-full bg-primary/10 text-primary ring-1 ring-primary/25 px-2.5 py-1 text-[11px] font-bold">{incidents.length} active</span>
      </div>
      <div className="grid gap-3">
        {incidents.length === 0 ? <Empty /> : incidents.map((incident) => (
          <button key={incident.incident_id} onClick={() => onOpenIncident(incident.incident_id)} className="group w-full text-left rounded-xl p-4 bg-white/[0.02] ring-1 ring-white/[0.06] hover:ring-primary/35 hover:bg-primary/[0.04] transition-all">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-5">
              <div className="flex items-center gap-2 min-w-[170px]">{severityPill(incident.severity)} {statusBadge(incident.status)}</div>
              <div className="flex-1 min-w-0"><div className="font-medium text-sm truncate">{incident.title}</div><div className="text-[11px] text-text-muted mt-1 font-mono">{incident.incident_id} · detected {formatElapsedSeconds(incident.detected_at)} ago</div></div>
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary group-hover:translate-x-0.5 transition-transform">Open workspace <ArrowUpRight className="w-3.5 h-3.5" /></span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

function ResolvedIncidents({ incidents, onOpenIncident }: { incidents: IncidentSummary[]; onOpenIncident: (id: string) => void }) {
  return <section className={card}>
    <div className="flex flex-wrap gap-3 items-end justify-between mb-4">
      <div><h3 className="font-semibold">Resolved incidents</h3><p className="text-xs text-text-muted mt-1">Completed incidents retained for review and audit</p></div>
      <span className="rounded-full bg-healthy/10 text-healthy ring-1 ring-healthy/25 px-2.5 py-1 text-[11px] font-bold">{incidents.length} resolved</span>
    </div>
    <div className="grid gap-3">
      {incidents.length === 0 ? <div className="py-10 text-center text-sm text-text-muted">No resolved incidents yet.</div> : incidents.map((incident) => (
        <button key={incident.incident_id} onClick={() => onOpenIncident(incident.incident_id)} className="group w-full text-left rounded-xl p-4 bg-healthy/[0.025] ring-1 ring-healthy/15 hover:ring-healthy/35 hover:bg-healthy/[0.05] transition-all">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-5">
            <div className="flex items-center gap-2 min-w-[170px]">{severityPill(incident.severity)} {statusBadge(incident.status)}</div>
            <div className="flex-1 min-w-0"><div className="font-medium text-sm truncate">{incident.title}</div><div className="text-[11px] text-text-muted mt-1 font-mono">{incident.incident_id} · detected {formatElapsedSeconds(incident.detected_at)} ago</div></div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-healthy group-hover:translate-x-0.5 transition-transform">Open workspace <ArrowUpRight className="w-3.5 h-3.5" /></span>
          </div>
        </button>
      ))}
    </div>
  </section>;
}

function OperationsPage({ incidents, attention }: { incidents: IncidentSummary[]; attention: number }) {
  const rows = [
    { icon: <Radio />, name: 'Incident event stream', state: 'Monitoring', tone: 'text-healthy bg-healthy/10' },
    { icon: <BrainCircuit />, name: 'NemoClaw investigation agents', state: incidents.length ? 'Working' : 'Standing by', tone: incidents.length ? 'text-agent-active bg-agent-active/10' : 'text-text-muted bg-white/[0.04]' },
    { icon: <ShieldCheck />, name: 'Safety & approval controls', state: attention ? `${attention} need review` : 'Clear', tone: attention ? 'text-warning bg-warning/10' : 'text-healthy bg-healthy/10' },
    { icon: <Database />, name: 'Evidence collection', state: 'Available', tone: 'text-info bg-info/10' },
  ];
  return <section className="grid lg:grid-cols-2 gap-5"><div className={card}><h3 className="font-semibold">Operational readiness</h3><div className="mt-4 space-y-2">{rows.map((row) => <div key={row.name} className="flex items-center gap-3 rounded-xl p-3 bg-white/[0.02] ring-1 ring-white/[0.05]"><span className={`w-9 h-9 rounded-lg flex items-center justify-center ${row.tone}`}>{row.icon}</span><span className="flex-1 text-sm font-medium">{row.name}</span><span className="text-xs text-text-secondary">{row.state}</span></div>)}</div></div><div className={card}><h3 className="font-semibold">Operator checklist</h3><p className="text-xs text-text-muted mt-1">The essentials grouped into one operational handoff.</p><div className="mt-5 space-y-4">{['Review incidents awaiting approval', 'Confirm root-cause evidence is grounded', 'Monitor live agent activity during triage', 'Validate recovery after execution'].map((item, index) => <div key={item} className="flex gap-3 text-sm text-text-secondary"><span className="w-6 h-6 rounded-full bg-primary/12 text-primary font-bold text-xs flex items-center justify-center flex-shrink-0">{index + 1}</span>{item}</div>)}</div></div></section>;
}

function IntelligencePage({ incidents, critical, attention }: { incidents: IncidentSummary[]; critical: number; attention: number }) {
  const metrics = useMemo(() => [{ icon: <Layers3 />, label: 'Active incidents', value: incidents.length, detail: 'in the response queue', color: 'text-primary' }, { icon: <CircleAlert />, label: 'Critical risk', value: critical, detail: 'SEV-1 incidents', color: 'text-critical' }, { icon: <FileSearch />, label: 'Review required', value: attention, detail: 'plans needing a decision', color: 'text-warning' }, { icon: <Clock3 />, label: 'Response coverage', value: incidents.length ? 'Live' : 'Ready', detail: 'continuous monitoring', color: 'text-healthy' }], [incidents.length, critical, attention]);
  return <><section className="grid grid-cols-2 lg:grid-cols-4 gap-3">{metrics.map((metric) => <div key={metric.label} className={card}><div className={metric.color}>{metric.icon}</div><div className="text-2xl font-semibold mt-4">{metric.value}</div><div className="text-sm font-medium mt-1">{metric.label}</div><div className="text-[11px] text-text-muted mt-1">{metric.detail}</div></div>)}</section><section className={card}><div className="flex items-center gap-2"><Activity className="w-4 h-4 text-agent-active" /><h3 className="font-semibold">Response posture</h3></div><p className="mt-3 text-sm leading-relaxed text-text-secondary">NemoGuard is coordinating the incident queue with human approval gates for recovery. Use the Command Center to inspect evidence and execute a reviewed plan.</p></section></>;
}

function Empty() { return <div className="py-12 text-center text-sm text-text-muted">No active incidents. The queue is clear.</div>; }
