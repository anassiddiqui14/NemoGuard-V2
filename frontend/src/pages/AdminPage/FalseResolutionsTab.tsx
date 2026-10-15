import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, AlertTriangle, ShieldCheck, ShieldAlert } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Button } from '../../design-system/components/Button';
import { SkeletonCard } from '../../design-system/components/Skeleton';

interface VerificationCheck {
    check_name: string;
    status: string;
}

interface Violation {
    incident_id: string;
    title: string;
    resolved_at: string | null;
    reason: string;
    verification_checks: VerificationCheck[];
}

interface FalseResolutionData {
    total_resolved_incidents: number;
    false_resolution_count: number;
    false_resolution_rate: number | null;
    target: number;
    meets_target: boolean;
    violations: Violation[];
}

/**
 * The real safety-net audit (src/domain/evaluation/false_resolution.py):
 * scans every RESOLVED incident and flags any where the required
 * verification checks were NOT actually all PASSED -- i.e. an incident
 * that was marked resolved without its recovery being genuinely verified.
 * Target is 0; a non-empty violation list in a real deployment is a
 * serious bug, not a benchmark statistic. Nothing here is estimated --
 * every number is computed live from the incident/action_plan/
 * verification_result tables.
 */
export function FalseResolutionsTab() {
    const [data, setData] = useState<FalseResolutionData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/false-resolutions')
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(setData)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
    }, []);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Audits every RESOLVED incident to confirm its recovery was genuinely verified. Target is 0 -- any violation here is a real safety bug, not a benchmark statistic.
                </p>
                <Button size="sm" variant="secondary" onClick={load} loading={loading} leadingIcon={<RefreshCw className="w-3.5 h-3.5" />} className="flex-shrink-0">
                    Refresh
                </Button>
            </div>

            {error && (
                <div className="flex items-center gap-2 text-[12px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
                </div>
            )}

            {loading ? (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
            ) : data ? (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="console-surface rounded-2xl p-4">
                            <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">Resolved incidents</div>
                            <div className="text-2xl font-semibold text-text-primary tabular-nums">{data.total_resolved_incidents}</div>
                        </motion.div>
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.03 }} className="console-surface rounded-2xl p-4">
                            <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">False resolutions</div>
                            <div className={`text-2xl font-semibold tabular-nums ${data.false_resolution_count > 0 ? 'text-critical' : 'text-healthy'}`}>{data.false_resolution_count}</div>
                        </motion.div>
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} className="console-surface rounded-2xl p-4 flex items-center gap-3">
                            {data.meets_target ? <ShieldCheck className="w-8 h-8 text-healthy flex-shrink-0" /> : <ShieldAlert className="w-8 h-8 text-critical flex-shrink-0" />}
                            <div>
                                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-0.5">Target status</div>
                                <div className={`text-[13px] font-semibold ${data.meets_target ? 'text-healthy' : 'text-critical'}`}>
                                    {data.meets_target ? 'Meets target (0)' : `${data.false_resolution_count} violation(s) found`}
                                </div>
                            </div>
                        </motion.div>
                    </div>

                    {data.violations.length > 0 && (
                        <div className="console-surface rounded-2xl overflow-hidden">
                            <div className="px-4 py-3 border-b border-white/[0.05] text-[12.5px] font-semibold text-critical">Violations requiring review</div>
                            {data.violations.map((v) => (
                                <div key={v.incident_id} className="px-4 py-3 border-b border-white/[0.04] last:border-b-0">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="text-[12.5px] font-medium text-text-primary">{v.title}</div>
                                        <span className="text-[10.5px] font-mono text-text-muted flex-shrink-0">{v.incident_id}</span>
                                    </div>
                                    <div className="text-[12px] text-critical mt-1">{v.reason}</div>
                                    {v.verification_checks.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 mt-2">
                                            {v.verification_checks.map((c, i) => (
                                                <span key={i} className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ring-1 ${c.status === 'PASSED' ? 'bg-healthy/10 text-healthy ring-healthy/25' : 'bg-critical/10 text-critical ring-critical/25'}`}>
                                                    {c.check_name}: {c.status}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </>
            ) : null}
        </div>
    );
}
