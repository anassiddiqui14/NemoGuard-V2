import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, RefreshCw, Loader2, AlertTriangle, Play, X, BarChart3 } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Chip } from '../../design-system/components/Chip';
import { SkeletonTableRows } from '../../design-system/components/Skeleton';
import { Input, FormField } from '../../design-system/components/Input';

interface EvalRun {
    run_id: string;
    name: string;
    models: string[];
    historical_incident_ids: string[];
    prompt_version: string;
    status: string;
    created_at: string;
}

interface HistoricalIncident {
    id: string;
    title: string;
    service: string | null;
    environment: string | null;
    severity: string | null;
}

interface ScorecardRow {
    model_name: string;
    total_incidents: number;
    completed_replays: number;
    failed_replays: number;
    rca_top1_accuracy: number | null;
    rca_top3_accuracy: number | null;
    cause_family_accuracy: number | null;
    scored_incident_count: number;
    evidence_citation_presence_rate: number | null;
    avg_latency_seconds: number | null;
    p95_latency_seconds: number | null;
}

function pct(v: number | null): string {
    return v == null ? '—' : `${Math.round(v * 100)}%`;
}

function CreateRunForm({ historicalIncidents, availableModels, onCreated, onCancel }: { historicalIncidents: HistoricalIncident[]; availableModels: string[]; onCreated: () => void; onCancel: () => void }) {
    const [name, setName] = useState('');
    const [selectedModels, setSelectedModels] = useState<string[]>(availableModels.slice(0, 1));
    const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const toggleModel = (m: string) => setSelectedModels((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));
    const toggleIncident = (id: string) => setSelectedIncidents((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

    const handleSubmit = async () => {
        if (!name.trim() || selectedModels.length === 0 || selectedIncidents.length === 0) {
            setError('Name, at least one model, and at least one historical incident are required.');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const res = await authFetch('/api/v2/admin/model-evaluation/runs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name.trim(), models: selectedModels, historical_incident_ids: selectedIncidents }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            onCreated();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create run');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="console-surface rounded-2xl p-4 space-y-3 overflow-hidden">
            <div className="flex items-center justify-between">
                <div className="text-[13px] font-semibold text-text-primary">New model evaluation run</div>
                <button onClick={onCancel} className="focus-ring press-scale w-6 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-white/[0.05]">
                    <X className="w-3.5 h-3.5" />
                </button>
            </div>

            {error && <div className="text-[11.5px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">{error}</div>}

            <FormField label="Run name *">
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ultra vs Super Q3 benchmark" />
            </FormField>

            <div>
                <div className="text-[11px] text-text-muted mb-1.5">Models to compare *</div>
                <div className="flex flex-wrap gap-1.5">
                    {availableModels.map((m) => (
                        <Chip key={m} selected={selectedModels.includes(m)} mono onClick={() => toggleModel(m)}>
                            {m}
                        </Chip>
                    ))}
                </div>
            </div>

            <div>
                <div className="text-[11px] text-text-muted mb-1.5">Historical incidents to replay * ({selectedIncidents.length} selected)</div>
                <div className="max-h-40 overflow-y-auto space-y-1 rounded-lg ring-1 ring-white/[0.06] p-2">
                    {historicalIncidents.length === 0 ? (
                        <div className="text-[11.5px] text-text-muted py-2 text-center">No historical incidents recorded yet. Create one via /api/v2/replay/historical-incidents first.</div>
                    ) : (
                        historicalIncidents.map((h) => (
                            <label key={h.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-white/[0.03] cursor-pointer">
                                <input type="checkbox" checked={selectedIncidents.includes(h.id)} onChange={() => toggleIncident(h.id)} className="accent-primary" />
                                <span className="text-[12px] text-text-secondary truncate">{h.title}</span>
                                {h.severity && <span className="text-[9.5px] text-text-muted flex-shrink-0">{h.severity}</span>}
                            </label>
                        ))
                    )}
                </div>
            </div>

            <button onClick={handleSubmit} disabled={submitting} className="press-scale w-full flex items-center justify-center gap-2 text-[12.5px] font-semibold px-4 py-2.5 rounded-xl bg-primary text-white disabled:opacity-50">
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Create run
            </button>
        </motion.div>
    );
}

function ScorecardView({ runId, onClose }: { runId: string; onClose: () => void }) {
    const [rows, setRows] = useState<ScorecardRow[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        authFetch(`/api/v2/admin/model-evaluation/runs/${runId}/scorecard`)
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then((data) => setRows(data.scorecard || data))
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load scorecard'))
            .finally(() => setLoading(false));
    }, [runId]);

    return (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="console-surface rounded-2xl p-4 space-y-3 overflow-hidden">
            <div className="flex items-center justify-between">
                <div className="text-[13px] font-semibold text-text-primary">Scorecard — {runId}</div>
                <button onClick={onClose} className="focus-ring press-scale w-6 h-6 rounded-md flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-white/[0.05]">
                    <X className="w-3.5 h-3.5" />
                </button>
            </div>
            {loading ? (
                <div className="text-[12px] text-text-muted py-4 text-center"><Loader2 className="w-4 h-4 animate-spin inline mr-2" /> Loading scorecard...</div>
            ) : error ? (
                <div className="text-[11.5px] text-critical">{error}</div>
            ) : rows && rows.length > 0 ? (
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[10px] font-semibold uppercase tracking-wide text-text-muted border-b border-white/[0.06]">
                                <th className="py-2 pr-3">Model</th>
                                <th className="py-2 pr-3">Top-1</th>
                                <th className="py-2 pr-3">Top-3</th>
                                <th className="py-2 pr-3">Cause family</th>
                                <th className="py-2 pr-3">Evidence cited</th>
                                <th className="py-2 pr-3">Avg latency</th>
                                <th className="py-2 pr-3">Completed</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((r) => (
                                <tr key={r.model_name} className="border-b border-white/[0.04] last:border-b-0 text-[12px]">
                                    <td className="py-2 pr-3 font-mono text-text-primary">{r.model_name}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{pct(r.rca_top1_accuracy)}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{pct(r.rca_top3_accuracy)}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{pct(r.cause_family_accuracy)}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{pct(r.evidence_citation_presence_rate)}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{r.avg_latency_seconds != null ? `${r.avg_latency_seconds}s` : '—'}</td>
                                    <td className="py-2 pr-3 text-text-secondary">{r.completed_replays}/{r.total_incidents}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="text-[12px] text-text-muted py-4 text-center">No scorecard data yet — the run may still be in progress.</div>
            )}
        </motion.div>
    );
}

const STATUS_COLORS: Record<string, string> = {
    PENDING: 'bg-white/[0.05] text-text-muted ring-white/[0.08]',
    RUNNING: 'bg-primary/10 text-primary ring-primary/25',
    COMPLETED: 'bg-healthy/10 text-healthy ring-healthy/25',
    FAILED: 'bg-critical/10 text-critical ring-critical/25',
};

export function ModelEvaluationTab() {
    const [runs, setRuns] = useState<EvalRun[] | null>(null);
    const [historicalIncidents, setHistoricalIncidents] = useState<HistoricalIncident[]>([]);
    // Loaded live from the SAME settings endpoint the Model Settings tab
    // uses (/api/v2/admin/settings -> known_models), rather than a
    // hardcoded, independently-maintained duplicate list -- which is
    // exactly why a newly-added model (e.g. moonshotai/kimi-k3) never
    // showed up here even after it was added to settings_service.py.
    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showForm, setShowForm] = useState(false);
    const [scorecardRunId, setScorecardRunId] = useState<string | null>(null);
    const [startingRunId, setStartingRunId] = useState<string | null>(null);

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/model-evaluation/runs')
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(setRuns)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
        authFetch('/api/v2/replay/historical-incidents')
            .then((res) => (res.ok ? res.json() : []))
            .then(setHistoricalIncidents)
            .catch(() => setHistoricalIncidents([]));
        authFetch('/api/v2/admin/settings')
            .then((res) => (res.ok ? res.json() : { known_models: [] }))
            .then((data) => setAvailableModels((data.known_models || []).map((m: { model: string }) => m.model)))
            .catch(() => setAvailableModels([]));
    }, []);

    const handleStart = async (runId: string) => {
        setStartingRunId(runId);
        try {
            const res = await authFetch(`/api/v2/admin/model-evaluation/runs/${runId}/start`, { method: 'POST' });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to start run');
        } finally {
            setStartingRunId(null);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Compare AI model performance (RCA accuracy, evidence citation, latency) across the same real historical incidents replayed through the full investigation graph.
                </p>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <button onClick={() => setShowForm((s) => !s)} className="press-scale inline-flex items-center gap-2 text-[12px] font-medium px-3 py-1.5 rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30 hover:bg-primary/20 transition">
                        <Plus className="w-3.5 h-3.5" /> New run
                    </button>
                    <button onClick={load} disabled={loading} className="press-scale inline-flex items-center gap-2 text-[12px] font-medium px-3 py-1.5 rounded-lg ring-1 ring-white/[0.08] hover:bg-white/[0.05] transition disabled:opacity-50">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            <AnimatePresence>
                {showForm && (
                    <CreateRunForm
                        historicalIncidents={historicalIncidents}
                        availableModels={availableModels}
                        onCancel={() => setShowForm(false)}
                        onCreated={() => {
                            setShowForm(false);
                            load();
                        }}
                    />
                )}
            </AnimatePresence>

            <AnimatePresence>
                {scorecardRunId && <ScorecardView runId={scorecardRunId} onClose={() => setScorecardRunId(null)} />}
            </AnimatePresence>

            {error && (
                <div className="flex items-center gap-2 text-[12px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
                </div>
            )}

            <div className="console-surface rounded-2xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="border-b border-white/[0.06] text-[10.5px] font-semibold uppercase tracking-wide text-text-muted">
                                <th className="px-4 py-3">Run</th>
                                <th className="px-4 py-3">Models</th>
                                <th className="px-4 py-3">Incidents</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <SkeletonTableRows columns={5} rows={4} />
                            ) : runs && runs.length > 0 ? (
                                runs.map((r) => (
                                    <motion.tr key={r.run_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors">
                                        <td className="px-4 py-3">
                                            <div className="text-[12.5px] font-medium text-text-primary">{r.name}</div>
                                            <div className="text-[10.5px] text-text-muted font-mono mt-0.5">{r.run_id}</div>
                                        </td>
                                        <td className="px-4 py-3 text-[11px] text-text-secondary">
                                            {r.models.map((m) => <div key={m} className="font-mono">{m}</div>)}
                                        </td>
                                        <td className="px-4 py-3 text-[12px] text-text-secondary">{r.historical_incident_ids.length}</td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10.5px] font-semibold px-2 py-1 rounded-full ring-1 ${STATUS_COLORS[r.status] || STATUS_COLORS.PENDING}`}>{r.status}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                {r.status === 'PENDING' && (
                                                    <button onClick={() => handleStart(r.run_id)} disabled={startingRunId === r.run_id} className="press-scale inline-flex items-center gap-1 text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30 disabled:opacity-50">
                                                        {startingRunId === r.run_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Start
                                                    </button>
                                                )}
                                                {(r.status === 'COMPLETED' || r.status === 'RUNNING') && (
                                                    <button onClick={() => setScorecardRunId(r.run_id)} className="press-scale inline-flex items-center gap-1 text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg ring-1 ring-white/[0.08] text-text-secondary hover:bg-white/[0.05]">
                                                        <BarChart3 className="w-3 h-3" /> Scorecard
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </motion.tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={5} className="px-4 py-8 text-center text-[12px] text-text-muted">
                                        No model evaluation runs yet.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
