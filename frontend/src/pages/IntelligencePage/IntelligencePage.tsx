import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Layers, AlertOctagon, FileSearch, Clock3, ShieldCheck, TrendingUp } from 'lucide-react';
import { fadeInUp, severityPill, needsAttention, EmptyState } from '../../components/dashboard/shared';
import type { IncidentSummary } from '../../components/dashboard/shared';

// The "Intelligence" page — a decision-ready, at-a-glance risk overview
// across the whole incident response system, distinct from the per-
// incident Command Center dashboard. This fills a real gap the original
// single-dashboard UI didn't have anywhere: a manager/on-call-lead level
// summary of "how much risk is currently in flight, and where."
//
// Design origin note: inspired by a UI exploration on the `darshan-dev`
// branch (a stat-card risk-overview page) — reimplemented here using this
// app's existing animation/motion primitives (fadeInUp, glass-panel,
// severityPill) rather than a new design system, so it feels native to
// the rest of the product instead of a bolted-on page.

type Metrics = {
    activeIncidents: number;
    criticalRisk: number;
    reviewRequired: number;
    resolvedToday: number;
};

function StatCard({
    icon,
    value,
    label,
    sublabel,
    tone,
    delay,
}: {
    icon: React.ReactNode;
    value: number;
    label: string;
    sublabel: string;
    tone: 'default' | 'critical' | 'warning' | 'healthy';
    delay: number;
}) {
    const toneStyles: Record<string, string> = {
        default: 'bg-primary/10 text-primary ring-primary/25',
        critical: 'bg-critical/10 text-critical ring-critical/25',
        warning: 'bg-warning/10 text-warning ring-warning/25',
        healthy: 'bg-healthy/10 text-healthy ring-healthy/25',
    };
    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay, ease: [0.16, 1, 0.3, 1] }}
            whileHover={{ y: -2 }}
            className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]"
        >
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ring-1 mb-3 ${toneStyles[tone]}`}>{icon}</div>
            <motion.div
                key={value}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-[28px] font-bold text-text-primary leading-none tracking-tight"
            >
                {value}
            </motion.div>
            <div className="text-[12.5px] font-medium text-text-secondary mt-1.5">{label}</div>
            <div className="text-[11px] text-text-muted mt-0.5">{sublabel}</div>
        </motion.div>
    );
}

function RiskRow({ incident, index }: { incident: IncidentSummary; index: number }) {
    return (
        <motion.div
            {...fadeInUp}
            transition={{ duration: 0.2, delay: index * 0.04 }}
            className="flex items-center gap-3 py-3 border-b border-white/[0.05] last:border-b-0"
        >
            {severityPill(incident.severity)}
            <div className="min-w-0 flex-1">
                <div className="text-[13px] text-text-primary font-medium truncate">{incident.title}</div>
                <div className="text-[10.5px] text-text-muted font-mono mt-0.5">{incident.incident_id}</div>
            </div>
            {needsAttention(incident.status) && (
                <span className="text-[10px] font-bold px-2 py-1 rounded-md bg-warning/15 text-warning ring-1 ring-warning/30 flex-shrink-0">
                    Needs review
                </span>
            )}
        </motion.div>
    );
}

export function IntelligencePage() {
    const [openIncidents, setOpenIncidents] = useState<IncidentSummary[]>([]);
    const [resolvedToday, setResolvedToday] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const [openRes, allRes] = await Promise.all([
                    fetch('/api/v2/incidents?state=open'),
                    fetch('/api/v2/incidents?state=all'),
                ]);
                const openData = (await openRes.json()) as IncidentSummary[];
                const allData = (await allRes.json()) as IncidentSummary[];
                if (cancelled) return;
                setOpenIncidents(Array.isArray(openData) ? openData : []);
                const todayStr = new Date().toDateString();
                const resolvedTodayCount = Array.isArray(allData)
                    ? allData.filter(
                        (i) => i.status?.toUpperCase() === 'RESOLVED' && i.resolved_at && new Date(i.resolved_at).toDateString() === todayStr,
                    ).length
                    : 0;
                setResolvedToday(resolvedTodayCount);
            } catch {
                setOpenIncidents([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        void load();
        const interval = setInterval(load, 5000);
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, []);

    const metrics: Metrics = {
        activeIncidents: openIncidents.length,
        criticalRisk: openIncidents.filter((i) => i.severity?.toUpperCase().replace('_', '-') === 'SEV-1').length,
        reviewRequired: openIncidents.filter((i) => needsAttention(i.status)).length,
        resolvedToday,
    };

    const sortedByRisk = [...openIncidents].sort((a, b) => {
        const rank = (s?: string) => {
            const norm = s?.toUpperCase().replace('_', '-') || 'SEV-3';
            if (norm === 'SEV-1') return 0;
            if (norm === 'SEV-2') return 1;
            return 2;
        };
        return rank(a.severity) - rank(b.severity);
    });

    return (
        <div className="h-full overflow-y-auto p-6">
            <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl p-6 mb-6 bg-gradient-to-br from-primary/[0.08] via-agent-active/[0.05] to-transparent ring-1 ring-white/[0.06]"
            >
                <div className="text-[11px] font-bold text-primary uppercase tracking-wider mb-2">Intelligence</div>
                <h1 className="text-[22px] font-bold text-text-primary leading-tight">Understand risk across your response system.</h1>
                <p className="text-[13px] text-text-secondary mt-1.5 max-w-xl">
                    A decision-ready snapshot of incident pressure, safety controls, and investigation coverage.
                </p>
            </motion.div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <StatCard
                    icon={<Layers className="w-4.5 h-4.5" />}
                    value={metrics.activeIncidents}
                    label="Active incidents"
                    sublabel="in the response queue"
                    tone="default"
                    delay={0}
                />
                <StatCard
                    icon={<AlertOctagon className="w-4.5 h-4.5" />}
                    value={metrics.criticalRisk}
                    label="Critical risk"
                    sublabel="SEV-1 incidents"
                    tone="critical"
                    delay={0.05}
                />
                <StatCard
                    icon={<FileSearch className="w-4.5 h-4.5" />}
                    value={metrics.reviewRequired}
                    label="Review required"
                    sublabel="plans awaiting human sign-off"
                    tone="warning"
                    delay={0.1}
                />
                <StatCard
                    icon={<ShieldCheck className="w-4.5 h-4.5" />}
                    value={metrics.resolvedToday}
                    label="Resolved today"
                    sublabel="verified recoveries"
                    tone="healthy"
                    delay={0.15}
                />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]"
            >
                <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-4 h-4 text-primary" />
                    <h2 className="text-[13px] font-semibold text-text-primary">Ranked by risk</h2>
                </div>
                {loading ? (
                    <div className="py-8 text-center text-[12.5px] text-text-muted">Loading…</div>
                ) : sortedByRisk.length === 0 ? (
                    <EmptyState
                        icon={<Clock3 className="w-5 h-5" />}
                        title="No active incidents"
                        subtitle="The response queue is clear. New risk will appear here as soon as it's detected."
                    />
                ) : (
                    <div>
                        {sortedByRisk.map((inc, idx) => (
                            <RiskRow key={inc.incident_id} incident={inc} index={idx} />
                        ))}
                    </div>
                )}
            </motion.div>
        </div>
    );
}
