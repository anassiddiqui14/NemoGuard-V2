import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Layers, AlertOctagon, FileSearch, Clock3, ShieldCheck, TrendingUp } from 'lucide-react';
import { fadeInUp, severityPill, needsAttention, EmptyState } from '../../components/dashboard/shared';
import type { IncidentSummary } from '../../components/dashboard/shared';
import { authFetch } from '../../contexts/AuthGateContext';
import { SkeletonCard } from '../../design-system/components/Skeleton';

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
    // UI MODERNIZATION (Phase 21, spec Section 62): this page explicitly
    // bills itself as a "decision-ready, at-a-glance risk overview" --
    // but a failed fetch previously silently reset openIncidents to []
    // in the catch block, which then rendered every stat card as a
    // reassuring "0" and the "No active incidents, the queue is clear"
    // empty state. A manager glancing at this page during an actual API
    // outage would see the exact opposite of reality: a false "all
    // clear" at the worst possible moment. Added a real error state,
    // and (consistent with every other polling surface fixed so far)
    // kept whatever last-known-good data existed rather than wiping it.
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const [openRes, allRes] = await Promise.all([
                    authFetch('/api/v2/incidents?state=open'),
                    authFetch('/api/v2/incidents?state=all'),
                ]);
                if (!openRes.ok || !allRes.ok) throw new Error(`HTTP ${openRes.status}/${allRes.status}`);
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
                setError(null);
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load risk data');
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
            {/*
             * UI MODERNIZATION (spec Section 70 -- page header system):
             * previously a decorative gradient hero panel with a 22px
             * bold marketing-style tagline ("Understand risk across your
             * response system.") -- precisely the anti-pattern the spec
             * explicitly names: "Do not repeat giant marketing-style
             * headings inside /app." Replaced with the same restrained
             * page-header pattern already used consistently on
             * AdminPage/IncidentsPage/SettingsPage/ScenarioCockpitPage
             * (title + one-line description, no decorative gradient
             * panel), for a page that otherwise behaves and reads like
             * any other operational dashboard view.
             */}
            <div className="mb-5">
                <h1 className="text-xl font-semibold text-text-primary tracking-tight">Intelligence</h1>
                <p className="text-[13px] text-text-muted mt-1">
                    A decision-ready snapshot of incident pressure, safety controls, and investigation coverage.
                </p>
            </div>

            {error && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-critical/10 ring-1 ring-critical/25 flex items-center gap-2 text-[12px] text-critical">
                    <AlertOctagon className="w-3.5 h-3.5 flex-shrink-0" />
                    Couldn't refresh risk data -- figures below may be stale. {error}
                </div>
            )}

            {loading && openIncidents.length === 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
            ) : (
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
            )}

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
