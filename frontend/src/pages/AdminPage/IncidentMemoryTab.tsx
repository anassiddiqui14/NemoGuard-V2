import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, Loader2, AlertTriangle, CheckCircle2, XCircle, Trash2, Edit3, ChevronDown } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Input, Textarea, Select, FormField } from '../../design-system/components/Input';
import { Button } from '../../design-system/components/Button';

interface MemoryRecord {
    memory_id: string;
    tenant_id: string;
    memory_status: string;
    root_cause: string | null;
    cause_type: string | null;
    successful_recovery: string | null;
    human_feedback: string | null;
    verification_result: string | null;
    data_integrity_result: string | null;
    created_at: string;
}

const STATUSES = ['DRAFT', 'REVIEWED', 'APPROVED', 'REJECTED', 'REDACTED', 'EXPIRED'];

const STATUS_COLORS: Record<string, string> = {
    DRAFT: 'bg-white/[0.05] text-text-muted ring-white/[0.08]',
    REVIEWED: 'bg-primary/10 text-primary ring-primary/25',
    APPROVED: 'bg-healthy/10 text-healthy ring-healthy/25',
    REJECTED: 'bg-critical/10 text-critical ring-critical/25',
    REDACTED: 'bg-warning/10 text-warning ring-warning/25',
    EXPIRED: 'bg-white/[0.05] text-text-muted ring-white/[0.08]',
};

/**
 * Governance surface over what NemoGuard "learns" from past incidents --
 * the real memory_engine.py backing (src/domain/memory/memory_engine.py).
 * Every learned pattern (root cause, recovery approach, human feedback)
 * lives here, and an admin can approve it (so future investigations use
 * it as context), reject/redact it (so they don't), or edit it directly.
 */
function MemoryRow({ record, onChanged }: { record: MemoryRecord; onChanged: () => void }) {
    const [expanded, setExpanded] = useState(false);
    const [editing, setEditing] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [draft, setDraft] = useState({
        root_cause: record.root_cause || '',
        cause_type: record.cause_type || '',
        successful_recovery: record.successful_recovery || '',
        human_feedback: record.human_feedback || '',
    });

    const setStatus = async (newStatus: string) => {
        setBusy(true);
        setError(null);
        try {
            const res = await authFetch(`/api/v2/admin/memory/${record.memory_id}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_status: newStatus }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            onChanged();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to update status');
        } finally {
            setBusy(false);
        }
    };

    const saveEdit = async () => {
        setBusy(true);
        setError(null);
        try {
            const res = await authFetch(`/api/v2/admin/memory/${record.memory_id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(draft),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            setEditing(false);
            onChanged();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save edit');
        } finally {
            setBusy(false);
        }
    };

    const deleteRecord = async () => {
        if (!window.confirm('Permanently delete this learned memory record? This cannot be undone.')) return;
        setBusy(true);
        setError(null);
        try {
            const res = await authFetch(`/api/v2/admin/memory/${record.memory_id}`, { method: 'DELETE' });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            onChanged();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to delete');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="border-b border-white/[0.04] last:border-b-0">
            <button onClick={() => setExpanded((e) => !e)} className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-white/[0.02] transition-colors">
                <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-medium text-text-primary truncate">{record.root_cause || 'No root cause recorded'}</div>
                    <div className="text-[10.5px] text-text-muted mt-0.5">{record.cause_type || 'Unclassified'} · {new Date(record.created_at).toLocaleString()}</div>
                </div>
                <span className={`text-[10.5px] font-semibold px-2 py-1 rounded-full ring-1 flex-shrink-0 ${STATUS_COLORS[record.memory_status] || STATUS_COLORS.DRAFT}`}>
                    {record.memory_status}
                </span>
                <ChevronDown className={`w-4 h-4 text-text-muted flex-shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
                {expanded && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                        <div className="px-4 pb-4 space-y-3">
                            {error && <div className="text-[11.5px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">{error}</div>}

                            {editing ? (
                                <div className="space-y-2.5">
                                    <FormField label="Root cause">
                                        <Textarea value={draft.root_cause} onChange={(e) => setDraft((d) => ({ ...d, root_cause: e.target.value }))} rows={2} />
                                    </FormField>
                                    <FormField label="Cause type">
                                        <Input value={draft.cause_type} onChange={(e) => setDraft((d) => ({ ...d, cause_type: e.target.value }))} />
                                    </FormField>
                                    <FormField label="Successful recovery">
                                        <Textarea value={draft.successful_recovery} onChange={(e) => setDraft((d) => ({ ...d, successful_recovery: e.target.value }))} rows={2} />
                                    </FormField>
                                    <FormField label="Human feedback">
                                        <Textarea value={draft.human_feedback} onChange={(e) => setDraft((d) => ({ ...d, human_feedback: e.target.value }))} rows={2} />
                                    </FormField>
                                    <div className="flex gap-2">
                                        <Button size="sm" onClick={saveEdit} loading={busy}>Save</Button>
                                        <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    {record.successful_recovery && (
                                        <div className="text-[12px] text-text-secondary"><span className="text-text-muted">Recovery: </span>{record.successful_recovery}</div>
                                    )}
                                    {record.human_feedback && (
                                        <div className="text-[12px] text-text-secondary"><span className="text-text-muted">Feedback: </span>{record.human_feedback}</div>
                                    )}
                                    {record.verification_result && (
                                        <div className="text-[12px] text-text-secondary"><span className="text-text-muted">Verification: </span>{record.verification_result}</div>
                                    )}

                                    <div className="flex items-center gap-2 flex-wrap">
                                        {STATUSES.filter((s) => s !== record.memory_status).map((s) => (
                                            <button
                                                key={s}
                                                onClick={() => setStatus(s)}
                                                disabled={busy}
                                                className="press-scale text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg ring-1 ring-white/[0.08] text-text-secondary hover:bg-white/[0.05] disabled:opacity-50"
                                            >
                                                {s === 'APPROVED' && <CheckCircle2 className="w-3 h-3 inline mr-1 text-healthy" />}
                                                {s === 'REJECTED' && <XCircle className="w-3 h-3 inline mr-1 text-critical" />}
                                                Mark {s}
                                            </button>
                                        ))}
                                        <button onClick={() => setEditing(true)} disabled={busy} className="press-scale text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg ring-1 ring-white/[0.08] text-text-secondary hover:bg-white/[0.05] disabled:opacity-50">
                                            <Edit3 className="w-3 h-3 inline mr-1" /> Edit
                                        </button>
                                        <button onClick={deleteRecord} disabled={busy} className="press-scale text-[10.5px] font-semibold px-2.5 py-1.5 rounded-lg ring-1 ring-critical/25 text-critical hover:bg-critical/10 disabled:opacity-50">
                                            <Trash2 className="w-3 h-3 inline mr-1" /> Delete
                                        </button>
                                    </div>
                                </>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

export function IncidentMemoryTab() {
    const [records, setRecords] = useState<MemoryRecord[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<string>('');

    const load = () => {
        setLoading(true);
        setError(null);
        const qs = statusFilter ? `?status=${statusFilter}` : '';
        authFetch(`/api/v2/admin/memory${qs}`)
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(setRecords)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [statusFilter]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Learned patterns from past incidents. Approve a record so future investigations use it as context, or reject/redact it so they don't.
                </p>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <Select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="!text-[12px] !py-1.5"
                    >
                        <option value="">All statuses</option>
                        {STATUSES.map((s) => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </Select>
                    <button onClick={load} disabled={loading} className="press-scale inline-flex items-center gap-2 text-[12px] font-medium px-3 py-1.5 rounded-lg ring-1 ring-white/[0.08] hover:bg-white/[0.05] transition disabled:opacity-50">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {error && (
                <div className="flex items-center gap-2 text-[12px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
                </div>
            )}

            <div className="console-surface rounded-2xl overflow-hidden">
                {loading ? (
                    <div className="px-4 py-8 text-center text-[12px] text-text-muted">
                        <Loader2 className="w-4 h-4 animate-spin inline mr-2" /> Loading incident memory...
                    </div>
                ) : records && records.length > 0 ? (
                    records.map((r) => <MemoryRow key={r.memory_id} record={r} onChanged={load} />)
                ) : (
                    <div className="px-4 py-8 text-center text-[12px] text-text-muted">
                        No learned incident memory records{statusFilter ? ` with status ${statusFilter}` : ''} yet.
                    </div>
                )}
            </div>
        </div>
    );
}
