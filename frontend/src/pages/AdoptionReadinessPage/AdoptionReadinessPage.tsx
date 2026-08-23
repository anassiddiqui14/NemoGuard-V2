import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    ShieldCheck, CheckCircle2, XCircle, Loader2, RefreshCw,
    FlaskConical, Cloud, Lock, Brain, Activity,
} from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';

/**
 * Adoption Readiness Dashboard (per docs/NemoGuard_Validation_Demonstration
 * _and_Adoption_Readiness_Plan.md §20). Displays ONLY real, already-run
 * validation results persisted under docs/validation/ (unit tests, the
 * real-AWS scenario suite, the security/governance suite, the AI
 * evaluation benchmark) plus operational metrics computed live from the
 * database -- never a hardcoded or estimated number. A metric shows as
 * "Not yet run" rather than a fabricated placeholder when no artifact
 * exists yet.
 */

interface SuiteSummary {
    available: boolean;
    label: string;
    passed?: number | null;
    total?: number | null;
    metrics?: Record<string, any> | null;
    run_at?: string | null;
    source_file?: string | null;
}

interface ReadinessData {
    generated_at: string;
    unit_tests: SuiteSummary;
    scenario_suite: SuiteSummary;
    security_suite: SuiteSummary;
    ai_evaluation: SuiteSummary;
    operational_metrics: Record<string, any>;
}

function SuiteCard({ icon, suite }: { icon: React.ReactNode; suite: SuiteSummary }) {
    const passRate = suite.passed != null && suite.total ? suite.passed / suite.total : null;
    const allPassed = passRate !== null && passRate >= 1;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]"
        >
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
                        {icon}
                    </div>
                    <div className="font-semibold text-[13px] text-text-primary">{suite.label}</div>
                </div>
                {suite.available ? (
                    allPassed ? (
                        <CheckCircle2 className="w-4 h-4 text-healthy" />
                    ) : (
                        <XCircle className="w-4 h-4 text-warning" />
                    )
                ) : (
                    <span className="text-[10px] text-text-muted uppercase tracking-wide">Not yet run</span>
                )}
            </div>

            {suite.available ? (
                <>
                    {suite.passed != null && suite.total != null && (
                        <div className="text-2xl font-semibold text-text-primary tabular-nums mb-1">
                            {suite.passed}/{suite.total}
                            <span className="text-[12px] text-text-muted ml-2 font-normal">
                                {passRate !== null ? `(${Math.round(passRate * 100)}%)` : ''}
                            </span>
                        </div>
                    )}
                    {suite.metrics && (
                        <div className="grid grid-cols-2 gap-2 mt-2">
                            {Object.entries(suite.metrics).map(([k, v]) => (
                                <div key={k} className="text-[11px] text-text-secondary">
                                    <span className="text-text-muted">{k.replace(/_/g, ' ')}: </span>
                                    <span className="font-medium">
                                        {typeof v === 'number' && v <= 1 && v >= 0 && k.includes('accuracy') ? `${Math.round(v * 100)}%` : String(v)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                    {suite.run_at && (
                        <div className="text-[10.5px] text-text-muted mt-3">
                            Last run: {new Date(suite.run_at).toLocaleString()}
                        </div>
                    )}
                </>
            ) : (
                <div className="text-[12px] text-text-muted">
                    No result artifact found yet for this suite.
                </div>
            )}
        </motion.div>
    );
}

function MetricTile({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
    return (
        <div className="rounded-xl p-3.5 bg-white/[0.02] ring-1 ring-white/[0.05]">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">{label}</div>
            <div className="text-xl font-semibold text-text-primary tabular-nums">
                {value === null || value === undefined ? '—' : value}
            </div>
            {sub && <div className="text-[10.5px] text-text-muted mt-1">{sub}</div>}
        </div>
    );
}

export function AdoptionReadinessPage() {
    const [data, setData] = useState<ReadinessData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/adoption-readiness')
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
        <div className="h-full overflow-y-auto p-6 max-w-5xl mx-auto space-y-5">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-xl font-semibold text-text-primary tracking-tight flex items-center gap-2">
                        <ShieldCheck className="w-5 h-5 text-primary" /> Adoption Readiness
                    </h1>
                    <p className="text-[13px] text-text-muted mt-1">
                        Real, persisted validation results and live operational metrics — nothing on this page is estimated or hardcoded.
                    </p>
                </div>
                <button
                    onClick={load}
                    disabled={loading}
                    className="press-scale inline-flex items-center gap-2 text-[12.5px] font-medium px-3.5 py-2 rounded-xl ring-1 ring-white/[0.08] hover:bg-white/[0.05] transition disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    Refresh
                </button>
            </div>

            {error && (
                <div className="glass-panel rounded-xl p-4 ring-1 ring-critical/30 text-[12.5px] text-critical">
                    {error}
                    {error.toLowerCase().includes('permission') && (
                        <div className="text-text-muted mt-1">This dashboard requires an admin role.</div>
                    )}
                </div>
            )}

            {data && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <SuiteCard icon={<FlaskConical className="w-4 h-4" />} suite={data.unit_tests} />
                        <SuiteCard icon={<Cloud className="w-4 h-4" />} suite={data.scenario_suite} />
                        <SuiteCard icon={<Lock className="w-4 h-4" />} suite={data.security_suite} />
                        <SuiteCard icon={<Brain className="w-4 h-4" />} suite={data.ai_evaluation} />
                    </div>

                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass-panel rounded-2xl p-5 ring-1 ring-white/[0.06]"
                    >
                        <div className="flex items-center gap-2.5 mb-4">
                            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                <Activity className="w-4 h-4" />
                            </div>
                            <div className="font-semibold text-[13px] text-text-primary">Live Operational Metrics</div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <MetricTile label="Total Incidents" value={data.operational_metrics.total_incidents} />
                            <MetricTile label="Active Incidents" value={data.operational_metrics.active_incidents} />
                            <MetricTile label="Correlated Alerts" value={data.operational_metrics.total_correlated_alerts} />
                            <MetricTile
                                label="Alert Compression"
                                value={data.operational_metrics.alert_compression_ratio ? `${data.operational_metrics.alert_compression_ratio}:1` : null}
                                sub="alerts per incident"
                            />
                            <MetricTile
                                label="Median MTTR"
                                value={
                                    data.operational_metrics.median_mttr_seconds != null
                                        ? `${Math.round(data.operational_metrics.median_mttr_seconds / 60)}m`
                                        : null
                                }
                                sub={data.operational_metrics.median_mttr_seconds == null ? 'no resolved incidents yet' : undefined}
                            />
                            <MetricTile
                                label="Resolved w/ Known MTTR"
                                value={data.operational_metrics.resolved_incident_count_with_known_mttr}
                            />
                        </div>
                    </motion.div>

                    <div className="text-[10.5px] text-text-muted text-center">
                        Generated at {new Date(data.generated_at).toLocaleString()}
                    </div>
                </>
            )}
        </div>
    );
}
