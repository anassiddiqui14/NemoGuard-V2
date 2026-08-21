import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Cpu, ChevronRight, Radio, Brain, ShieldCheck as ShieldCheckIcon } from 'lucide-react';
import { AgentConstellation } from '../../components/AgentConstellation';
import { LiveOperationsConsole } from '../../components/LiveOperationsConsole';
import { severityPill, EmptyState, needsAttention } from '../../components/dashboard/shared';
import type { IncidentSummary } from '../../components/dashboard/shared';
import type { AgentEvent } from '../../hooks/useIncidentEvents';
import { authFetch } from '../../contexts/AuthGateContext';

// Operational readiness row — inspired by a UI exploration on the
// `darshan-dev` branch (an "Operations" page summarizing service
// readiness at a glance). Reimplemented here as a header strip on the
// existing Agent Operations page rather than a separate page, since this
// page is already the natural home for "is the agentic system itself
// healthy" questions (as opposed to per-incident status).
function ReadinessRow({ incidents }: { incidents: IncidentSummary[] }) {
    const reviewCount = incidents.filter((i) => needsAttention(i.status)).length;
    const activeCount = incidents.filter((i) => i.status?.toUpperCase() !== 'RESOLVED').length;

    const items = [
        {
            icon: <Radio className="w-4 h-4" />,
            label: 'Incident event stream',
            status: activeCount > 0 ? 'Monitoring' : 'Idle',
            tone: 'healthy' as const,
        },
        {
            icon: <Brain className="w-4 h-4" />,
            label: 'NemoClaw investigation agents',
            status: activeCount > 0 ? 'Working' : 'Standing by',
            tone: activeCount > 0 ? ('active' as const) : ('healthy' as const),
        },
        {
            icon: <ShieldCheckIcon className="w-4 h-4" />,
            label: 'Safety & approval controls',
            status: reviewCount > 0 ? `${reviewCount} need review` : 'All clear',
            tone: reviewCount > 0 ? ('warning' as const) : ('healthy' as const),
        },
    ];

    const toneStyles: Record<string, string> = {
        healthy: 'bg-healthy/10 text-healthy ring-healthy/25',
        active: 'bg-agent-active/10 text-agent-active ring-agent-active/25',
        warning: 'bg-warning/10 text-warning ring-warning/25',
    };

    return (
        <div className="glass-panel rounded-2xl ring-1 ring-white/[0.06] p-4 mb-4">
            <div className="text-[12px] font-semibold text-text-secondary mb-3">Operational readiness</div>
            <div className="space-y-2">
                {items.map((item, idx) => (
                    <motion.div
                        key={item.label}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.2, delay: idx * 0.05 }}
                        className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl bg-white/[0.02] ring-1 ring-white/[0.04]"
                    >
                        <div className="flex items-center gap-3">
                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ring-1 ${toneStyles[item.tone]}`}>{item.icon}</div>
                            <span className="text-[12.5px] text-text-primary font-medium">{item.label}</span>
                        </div>
                        <span className={`text-[11px] font-semibold ${item.tone === 'warning' ? 'text-warning' : item.tone === 'active' ? 'text-agent-active' : 'text-healthy'}`}>
                            {item.status}
                        </span>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}

export function AgentOperationsPage() {
    const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [loadingEvents, setLoadingEvents] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const load = () => {
            authFetch('/api/v2/incidents?state=all')
                .then((r) => r.json())
                .then((data) => {
                    if (!cancelled && Array.isArray(data)) {
                        setIncidents(data);
                        setSelectedId((prev) => prev ?? (data.length > 0 ? data[0].incident_id : null));
                    }
                })
                .catch(() => { });
        };
        load();
        const interval = setInterval(load, 5000);
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, []);

    useEffect(() => {
        if (!selectedId) {
            setEvents([]);
            return;
        }
        let cancelled = false;
        setLoadingEvents(true);
        authFetch(`/api/v2/incidents/${selectedId}/events`)
            .then((r) => r.json())
            .then((data) => {
                if (!cancelled && Array.isArray(data)) {
                    setEvents(
                        data.map((e: any, idx: number) => ({
                            id: e.id || e.event_id || `evt-${idx}`,
                            timestamp: e.created_at || e.timestamp,
                            source: e.actor_name || e.source || 'System',
                            event_type: e.event_type || 'EVENT',
                            message: e.message || '',
                        })),
                    );
                }
            })
            .catch(() => { })
            .finally(() => {
                if (!cancelled) setLoadingEvents(false);
            });
        return () => {
            cancelled = true;
        };
    }, [selectedId]);

    const selectedIncident = incidents.find((i) => i.incident_id === selectedId) ?? null;

    return (
        <div className="h-full flex overflow-hidden">
            <aside className="w-[280px] flex-shrink-0 border-r border-white/[0.06] overflow-y-auto p-3">
                <div className="px-2 py-2 mb-1">
                    <h2 className="text-[13px] font-semibold text-text-primary">Agent Operations</h2>
                    <p className="text-[11px] text-text-muted mt-0.5">Historical agent runs by incident</p>
                </div>
                {incidents.length === 0 ? (
                    <div className="px-2 py-8 text-center text-[12px] text-text-muted">No incidents yet.</div>
                ) : (
                    incidents.map((inc) => (
                        <button
                            key={inc.incident_id}
                            onClick={() => setSelectedId(inc.incident_id)}
                            className={`w-full text-left rounded-xl p-3 mb-1.5 transition-colors flex items-start gap-2 ${selectedId === inc.incident_id
                                ? 'bg-primary/[0.1] ring-1 ring-primary/25'
                                : 'hover:bg-white/[0.03] ring-1 ring-transparent'
                                }`}
                        >
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    {severityPill(inc.severity)}
                                    <span className="text-[10px] font-mono text-text-muted truncate">{inc.incident_id}</span>
                                </div>
                                <div className="text-[12px] text-text-secondary line-clamp-2">{inc.title}</div>
                            </div>
                            {selectedId === inc.incident_id && <ChevronRight className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-1" />}
                        </button>
                    ))
                )}
            </aside>

            <main className="flex-1 overflow-y-auto p-6">
                <ReadinessRow incidents={incidents} />
                {!selectedIncident ? (
                    <EmptyState icon={<Cpu className="w-5 h-5" />} title="No incident selected" subtitle="Choose an incident from the list to review its agent activity." />
                ) : (
                    <div className="space-y-4 max-w-4xl">
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]">
                            <div className="flex items-center gap-2 mb-2">
                                {severityPill(selectedIncident.severity)}
                                <span className="text-[11px] font-mono text-text-muted">{selectedIncident.incident_id}</span>
                            </div>
                            <h1 className="text-[17px] font-semibold text-text-primary">{selectedIncident.title}</h1>
                        </motion.div>

                        <div className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]">
                            <div className="text-[12px] font-semibold text-text-secondary mb-4">Agent Constellation</div>
                            <AgentConstellation status={selectedIncident.status} events={events} />
                        </div>

                        <div className="glass-panel rounded-2xl ring-1 ring-white/[0.06] h-[420px] overflow-hidden">
                            <div className="px-5 py-3.5 border-b border-white/[0.05] text-[12px] font-semibold text-text-secondary">
                                Full Event History
                            </div>
                            {loadingEvents ? (
                                <div className="p-6 text-[12.5px] text-text-muted">Loading events…</div>
                            ) : (
                                <LiveOperationsConsole events={events} status="connected" />
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
