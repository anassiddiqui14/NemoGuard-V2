import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, RefreshCw, Loader2, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Chip } from '../../design-system/components/Chip';
import { SkeletonTableRows } from '../../design-system/components/Skeleton';
import { Input, Select, FormField } from '../../design-system/components/Input';
import { IconButton } from '../../design-system/components/IconButton';
import { Button } from '../../design-system/components/Button';

interface TeamsRoute {
    route_id: string;
    name: string;
    enabled: number | boolean;
    environment: string | null;
    service_pattern: string | null;
    severity_threshold: string | null;
    team_id: string | null;
    channel_id: string | null;
    delivery_mode: string;
    notify_on: string[];
    webhook_configured: boolean;
    created_at: string;
}

const NOTIFY_OPTIONS = ['INCIDENT_CREATED', 'PLAN_READY', 'AWAITING_APPROVAL', 'EXECUTING', 'RESOLVED', 'FAILED', 'ESCALATED'];

function CreateRouteForm({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
    const [name, setName] = useState('');
    const [environment, setEnvironment] = useState('');
    const [servicePattern, setServicePattern] = useState('');
    const [severityThreshold, setSeverityThreshold] = useState('');
    const [teamId, setTeamId] = useState('');
    const [channelId, setChannelId] = useState('');
    const [notifyOn, setNotifyOn] = useState<string[]>(['ESCALATED', 'FAILED']);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const toggleNotify = (v: string) => {
        setNotifyOn((prev) => (prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]));
    };

    const handleSubmit = async () => {
        if (!name.trim()) {
            setError('Route name is required.');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const res = await authFetch('/api/v2/admin/teams/routes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name.trim(),
                    enabled: true,
                    environment: environment.trim() || null,
                    service_pattern: servicePattern.trim() || null,
                    severity_threshold: severityThreshold || null,
                    team_id: teamId.trim() || null,
                    channel_id: channelId.trim() || null,
                    delivery_mode: 'WORKFLOWS_WEBHOOK',
                    notify_on: notifyOn,
                }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            onCreated();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to create route');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="console-surface rounded-2xl p-4 space-y-3 overflow-hidden">
            <div className="flex items-center justify-between">
                <div className="text-[13px] font-semibold text-text-primary">New Teams route</div>
                {/* UI MODERNIZATION (spec Section 18/73): icon-only close button had no accessible name at all. */}
                <IconButton onClick={onCancel} label="Cancel" size="sm">
                    <X className="w-3.5 h-3.5" />
                </IconButton>
            </div>

            {error && <div className="text-[11.5px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">{error}</div>}

            <div className="grid grid-cols-2 gap-3">
                <FormField label="Route name *">
                    <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Prod Data Eng" />
                </FormField>
                <FormField label="Environment filter">
                    <Input value={environment} onChange={(e) => setEnvironment(e.target.value)} placeholder="production (blank = all)" />
                </FormField>
                <FormField label="Service pattern">
                    <Input value={servicePattern} onChange={(e) => setServicePattern(e.target.value)} placeholder="e.g. data-eng-* (blank = all)" />
                </FormField>
                <FormField label="Minimum severity">
                    <Select value={severityThreshold} onChange={(e) => setSeverityThreshold(e.target.value)}>
                        <option value="">Any severity</option>
                        <option value="low">Low+</option>
                        <option value="medium">Medium+</option>
                        <option value="high">High+</option>
                        <option value="critical">Critical only</option>
                    </Select>
                </FormField>
                <FormField label="MS Teams Team ID">
                    <Input value={teamId} onChange={(e) => setTeamId(e.target.value)} placeholder="optional" />
                </FormField>
                <FormField label="MS Teams Channel ID">
                    <Input value={channelId} onChange={(e) => setChannelId(e.target.value)} placeholder="optional" />
                </FormField>
            </div>

            <div>
                <div className="text-[11px] text-text-muted mb-1.5">Notify on these events</div>
                <div className="flex flex-wrap gap-1.5">
                    {NOTIFY_OPTIONS.map((opt) => (
                        <Chip key={opt} selected={notifyOn.includes(opt)} onClick={() => toggleNotify(opt)}>
                            {opt.replace(/_/g, ' ')}
                        </Chip>
                    ))}
                </div>
            </div>

            <div className="text-[10.5px] text-text-muted">
                Note: the actual webhook URL secret is never set here -- it's configured via an environment variable named{' '}
                <code className="bg-white/[0.05] px-1 py-0.5 rounded">{'TEAMS_WEBHOOK_URL_<ROUTE_ID>'}</code> after this route is created (route ID shown in the list below).
            </div>

            <button
                onClick={handleSubmit}
                disabled={submitting}
                className="press-scale w-full flex items-center justify-center gap-2 text-[12.5px] font-semibold px-4 py-2.5 rounded-xl bg-primary text-white disabled:opacity-50"
            >
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Create route
            </button>
        </motion.div>
    );
}

export function TeamsRoutesTab() {
    const [routes, setRoutes] = useState<TeamsRoute[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showForm, setShowForm] = useState(false);

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/teams/routes')
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(setRoutes)
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
                    Rules for which MS Teams channel gets notified about which incidents, filtered by environment/service/severity.
                </p>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <Button size="sm" variant="secondary" onClick={() => setShowForm((s) => !s)} leadingIcon={<Plus className="w-3.5 h-3.5" />}>
                        New route
                    </Button>
                    {/* UI MODERNIZATION (spec Section 18/73): icon-only refresh button had no accessible name. */}
                    <IconButton onClick={load} label="Refresh Teams routes" size="sm">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </IconButton>
                </div>
            </div>

            {showForm && (
                <CreateRouteForm
                    onCancel={() => setShowForm(false)}
                    onCreated={() => {
                        setShowForm(false);
                        load();
                    }}
                />
            )}

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
                                <th className="px-4 py-3">Name</th>
                                <th className="px-4 py-3">Filters</th>
                                <th className="px-4 py-3">Notify On</th>
                                <th className="px-4 py-3">Webhook</th>
                                <th className="px-4 py-3">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <SkeletonTableRows columns={5} rows={4} />
                            ) : routes && routes.length > 0 ? (
                                routes.map((r) => (
                                    <motion.tr
                                        key={r.route_id}
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <div className="text-[12.5px] font-medium text-text-primary">{r.name}</div>
                                            <div className="text-[10.5px] text-text-muted font-mono mt-0.5">{r.route_id}</div>
                                        </td>
                                        <td className="px-4 py-3 text-[11.5px] text-text-secondary">
                                            {r.environment && <div>env: {r.environment}</div>}
                                            {r.service_pattern && <div>service: {r.service_pattern}</div>}
                                            {r.severity_threshold && <div>severity ≥ {r.severity_threshold}</div>}
                                            {!r.environment && !r.service_pattern && !r.severity_threshold && <span className="text-text-muted">All incidents</span>}
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex flex-wrap gap-1 max-w-[220px]">
                                                {(r.notify_on || []).map((n) => (
                                                    <span key={n} className="text-[9.5px] font-semibold px-1.5 py-0.5 rounded-full bg-white/[0.04] text-text-secondary ring-1 ring-white/[0.06]">
                                                        {n.replace(/_/g, ' ')}
                                                    </span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            {r.webhook_configured ? (
                                                <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-healthy">
                                                    <CheckCircle2 className="w-3 h-3" /> Configured
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-warning">
                                                    <AlertTriangle className="w-3 h-3" /> Needs secret
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10.5px] font-semibold px-2 py-1 rounded-full ring-1 ${r.enabled ? 'bg-healthy/10 text-healthy ring-healthy/25' : 'bg-white/[0.05] text-text-muted ring-white/[0.08]'}`}>
                                                {r.enabled ? 'Enabled' : 'Disabled'}
                                            </span>
                                        </td>
                                    </motion.tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={5} className="px-4 py-8 text-center text-[12px] text-text-muted">
                                        No Teams routes configured yet.
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
