import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Button } from '../../design-system/components/Button';
import { SkeletonTableRows } from '../../design-system/components/Skeleton';

interface Capability {
    capability_id: string;
    version: string;
    kind: string;
    description: string;
    owner: string;
    default_risk_level: string;
    default_autonomy_mode: string;
    effective_risk_level: string;
    effective_autonomy_mode: string;
    overridden: boolean;
    supports_dry_run: boolean;
    required_args: string[];
}

const RISK_COLORS: Record<string, string> = {
    READ_ONLY: 'bg-healthy/10 text-healthy ring-healthy/25',
    LOW: 'bg-healthy/10 text-healthy ring-healthy/25',
    MEDIUM: 'bg-warning/10 text-warning ring-warning/25',
    HIGH: 'bg-critical/10 text-critical ring-critical/25',
    PROHIBITED: 'bg-critical/15 text-critical ring-critical/30',
};

const AUTONOMY_COLORS: Record<string, string> = {
    AUTOMATIC: 'bg-primary/10 text-primary ring-primary/25',
    HUMAN_APPROVAL_REQUIRED: 'bg-agent-active/10 text-agent-active ring-agent-active/25',
};

/**
 * Real capability catalog + policy administration, calling the exact
 * endpoints src/api/main.py already exposes (spec 17.3/17.4):
 *   GET  /api/v2/admin/capabilities          -- what's registered + effective policy
 *   POST /api/v2/admin/capabilities/reload-policy -- hot-reload config/capability_policy.yaml
 *
 * "Effective" values already reflect any override in
 * config/capability_policy.yaml -- the backend runs the SAME resolution
 * logic used at real execution time, so what an admin sees here is
 * guaranteed to match runtime behavior (no separate display logic to
 * drift out of sync).
 */
export function CapabilityPolicyTab() {
    const [caps, setCaps] = useState<Capability[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [reloading, setReloading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [reloadMsg, setReloadMsg] = useState<string | null>(null);

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/capabilities')
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then(setCaps)
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
    }, []);

    const handleReload = async () => {
        setReloading(true);
        setReloadMsg(null);
        try {
            const res = await authFetch('/api/v2/admin/capabilities/reload-policy', { method: 'POST' });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            const data = await res.json();
            setReloadMsg(`Policy reloaded from ${data.config_path}`);
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Reload failed');
        } finally {
            setReloading(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Every capability an agent can invoke, with its effective risk level and autonomy mode after applying <code className="text-[11px] bg-white/[0.05] px-1 py-0.5 rounded">config/capability_policy.yaml</code> overrides.
                </p>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <Button size="sm" variant="secondary" onClick={handleReload} loading={reloading} leadingIcon={<RefreshCw className="w-3.5 h-3.5" />}>
                        Reload policy YAML
                    </Button>
                    <Button size="sm" variant="secondary" onClick={load} loading={loading} leadingIcon={<RefreshCw className="w-3.5 h-3.5" />}>
                        Refresh
                    </Button>
                </div>
            </div>

            {reloadMsg && (
                <div className="flex items-center gap-2 text-[12px] text-healthy bg-healthy/10 ring-1 ring-healthy/25 rounded-lg px-3 py-2">
                    <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" /> {reloadMsg}
                </div>
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
                                <th className="px-4 py-3">Capability</th>
                                <th className="px-4 py-3">Owner</th>
                                <th className="px-4 py-3">Effective Risk</th>
                                <th className="px-4 py-3">Effective Autonomy</th>
                                <th className="px-4 py-3">Overridden</th>
                                <th className="px-4 py-3">Dry-run</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <SkeletonTableRows columns={6} rows={5} />
                            ) : caps && caps.length > 0 ? (
                                caps.map((c) => (
                                    <motion.tr
                                        key={c.capability_id}
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <div className="text-[12.5px] font-medium text-text-primary font-mono">{c.capability_id}</div>
                                            <div className="text-[11px] text-text-muted mt-0.5 max-w-md">{c.description}</div>
                                        </td>
                                        <td className="px-4 py-3 text-[12px] text-text-secondary">{c.owner}</td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10.5px] font-semibold px-2 py-1 rounded-full ring-1 ${RISK_COLORS[c.effective_risk_level] || 'bg-white/[0.05] text-text-muted ring-white/[0.08]'}`}>
                                                {c.effective_risk_level}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`text-[10.5px] font-semibold px-2 py-1 rounded-full ring-1 ${AUTONOMY_COLORS[c.effective_autonomy_mode] || 'bg-white/[0.05] text-text-muted ring-white/[0.08]'}`}>
                                                {c.effective_autonomy_mode.replace(/_/g, ' ')}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            {c.overridden ? (
                                                <span className="text-[10.5px] font-semibold text-warning">
                                                    Yes ({c.default_risk_level} → {c.effective_risk_level})
                                                </span>
                                            ) : (
                                                <span className="text-[10.5px] text-text-muted">No (default)</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-[12px] text-text-secondary">{c.supports_dry_run ? 'Yes' : 'No'}</td>
                                    </motion.tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={6} className="px-4 py-8 text-center text-[12px] text-text-muted">
                                        No capabilities registered.
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
