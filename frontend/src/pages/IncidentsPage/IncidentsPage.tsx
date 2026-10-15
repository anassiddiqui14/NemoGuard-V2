import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ListChecks, AlertTriangle, RefreshCw } from 'lucide-react';
import { severityPill, statusBadge, formatElapsedSeconds, EmptyState } from '../../components/dashboard/shared';
import { SkeletonTableRows } from '../../design-system/components/Skeleton';
import { IncidentWorkspace } from '../../components/dashboard/IncidentWorkspace';
import type { IncidentSummary } from '../../components/dashboard/shared';
import { authFetch } from '../../contexts/AuthGateContext';

type SortKey = 'detected_at' | 'severity' | 'status';

export function IncidentsPage() {
    const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
    const [loading, setLoading] = useState(true);
    // UI MODERNIZATION (Phase 7, spec Section 62): previously there was no
    // error state at all here -- a failed fetch silently left `incidents`
    // empty, which then rendered the exact same "No incidents found" empty
    // state as a genuinely empty, healthy result. An operator would have
    // no way to tell "there really are zero incidents" apart from "the API
    // call failed and this list may be wrong/incomplete".
    const [error, setError] = useState<string | null>(null);
    const [query, setQuery] = useState('');
    const [sortKey, setSortKey] = useState<SortKey>('detected_at');
    // Selecting an incident now shows its full workspace INLINE, right here
    // on the Incidents page (with a "Back to incidents" control), instead of
    // navigating away to the Command Center dashboard -- staying on this
    // page keeps the user's search/sort/filter context intact and matches
    // the expectation that "view incident" from a list means "show detail
    // in place", not "jump somewhere else".
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const fetchAll = async () => {
        try {
            const res = await authFetch('/api/v2/incidents?state=all');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setIncidents(data);
                setError(null);
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load incidents');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void fetchAll();
        const t = window.setInterval(fetchAll, 5000);
        return () => window.clearInterval(t);
    }, []);

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        let list = incidents;
        if (q) {
            list = list.filter(
                (i) =>
                    i.title?.toLowerCase().includes(q) ||
                    i.incident_id?.toLowerCase().includes(q) ||
                    i.owner_team?.toLowerCase().includes(q),
            );
        }
        return [...list].sort((a, b) => {
            if (sortKey === 'detected_at') return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
            if (sortKey === 'severity') return (a.severity || '').localeCompare(b.severity || '');
            return (a.status || '').localeCompare(b.status || '');
        });
    }, [incidents, query, sortKey]);

    const selectedIncident = incidents.find((i) => i.incident_id === selectedId) ?? null;

    if (selectedId) {
        return (
            <div className="h-full overflow-y-auto p-6">
                <AnimatePresence mode="wait">
                    <motion.div
                        key={selectedId}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.18 }}
                    >
                        <IncidentWorkspace
                            incidentId={selectedId}
                            selectedIncident={selectedIncident}
                            onRefreshParent={fetchAll}
                            onBack={() => setSelectedId(null)}
                        />
                    </motion.div>
                </AnimatePresence>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <div>
                    <h1 className="text-xl font-semibold text-text-primary tracking-tight">Incidents</h1>
                    <p className="text-[13px] text-text-muted mt-1">Full incident history across all severities and states.</p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Search incidents…"
                            className="pl-8 pr-3 py-2 bg-white/[0.03] border border-white/[0.06] rounded-lg text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/40 w-56 transition-all"
                        />
                    </div>
                    <select
                        value={sortKey}
                        onChange={(e) => setSortKey(e.target.value as SortKey)}
                        className="px-3 py-2 bg-white/[0.03] border border-white/[0.06] rounded-lg text-[12.5px] text-text-secondary focus:outline-none"
                    >
                        <option value="detected_at">Sort: Newest</option>
                        <option value="severity">Sort: Severity</option>
                        <option value="status">Sort: Status</option>
                    </select>
                </div>
            </div>

            {/*
             * Consistent with the Dashboard's queue fix (Phase 6): a
             * polling failure after we already have real data should NOT
             * hide that data behind a full error screen -- it should keep
             * showing it (possibly stale) with a small inline warning. The
             * full-screen error treatment only applies to the FIRST load
             * failing, where there's no prior data to fall back to.
             */}
            {error && incidents.length > 0 && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-warning/10 ring-1 ring-warning/25 flex items-center gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-warning flex-shrink-0" />
                    <p className="text-[11.5px] text-warning flex-1">Lost connection on the last refresh -- showing last known data.</p>
                    <button onClick={() => void fetchAll()} className="text-[11px] font-medium text-warning hover:underline flex-shrink-0">Retry</button>
                </div>
            )}
            {/*
             * UI MODERNIZATION (Phase 12, spec Section 38/63): replaced
             * a plain "Loading incidents…" text row with a structural
             * skeleton that approximates the real table shape (5 columns
             * matching the actual header below), per spec guidance to
             * use skeletons for predictable structures like tables.
             */}
            {loading ? (
                <div className="glass-panel rounded-2xl overflow-hidden ring-1 ring-white/[0.06]">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="border-b border-white/[0.06] text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                                <th className="px-4 py-3">Severity</th>
                                <th className="px-4 py-3">Incident</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Owner</th>
                                <th className="px-4 py-3">Elapsed</th>
                            </tr>
                        </thead>
                        <tbody>
                            <SkeletonTableRows columns={5} rows={6} />
                        </tbody>
                    </table>
                </div>
            ) : error && incidents.length === 0 ? (
                <div className="mt-10">
                    <EmptyState
                        icon={<AlertTriangle className="w-5 h-5 text-critical" />}
                        title="Couldn't load incidents"
                        subtitle={error}
                        action={
                            <button
                                onClick={() => {
                                    setLoading(true);
                                    void fetchAll();
                                }}
                                className="inline-flex items-center gap-1.5 text-[11.5px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.07] ring-1 ring-white/[0.08] text-text-secondary hover:text-text-primary transition-colors"
                            >
                                <RefreshCw className="w-3.5 h-3.5" /> Retry
                            </button>
                        }
                    />
                </div>
            ) : filtered.length === 0 ? (
                <div className="mt-10">
                    <EmptyState icon={<ListChecks className="w-5 h-5" />} title="No incidents found" subtitle="Try a different search or wait for new alerts to arrive." />
                </div>
            ) : (
                <div className="glass-panel rounded-2xl overflow-hidden ring-1 ring-white/[0.06]">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="border-b border-white/[0.06] text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                                <th className="px-4 py-3">Severity</th>
                                <th className="px-4 py-3">Incident</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Owner</th>
                                <th className="px-4 py-3">Elapsed</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((inc, idx) => (
                                <motion.tr
                                    key={inc.incident_id}
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: idx * 0.02 }}
                                    onClick={() => setSelectedId(inc.incident_id)}
                                    className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] cursor-pointer transition-colors"
                                >
                                    <td className="px-4 py-3">{severityPill(inc.severity)}</td>
                                    <td className="px-4 py-3 min-w-0">
                                        <div className="text-[13px] font-medium text-text-primary truncate max-w-[360px]">{inc.title}</div>
                                        <div className="text-[10.5px] font-mono text-text-muted mt-0.5">{inc.incident_id}</div>
                                    </td>
                                    <td className="px-4 py-3">{statusBadge(inc.status)}</td>
                                    <td className="px-4 py-3 text-[12.5px] text-text-secondary">{inc.owner_team || '—'}</td>
                                    <td className="px-4 py-3 text-[12.5px] font-mono text-text-secondary">
                                        {formatElapsedSeconds(inc.detected_at, inc.resolved_at)}
                                    </td>
                                </motion.tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
