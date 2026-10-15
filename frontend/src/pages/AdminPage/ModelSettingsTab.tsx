import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, AlertTriangle, CheckCircle2, Save, Cpu } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';
import { Button } from '../../design-system/components/Button';
import { Chip } from '../../design-system/components/Chip';
import { Input } from '../../design-system/components/Input';
import { SkeletonCard } from '../../design-system/components/Skeleton';

interface KnownModel {
    model: string;
    label: string;
    extra_body: Record<string, unknown>;
}

interface ModelTierValue {
    model: string;
    extra_body: Record<string, unknown>;
}

interface SettingsResponse {
    settings: Record<string, unknown>;
    known_models: KnownModel[];
}

const TIER_KEYS = [
    { key: 'model.ultra_tier', label: 'Ultra tier', hint: 'Used by RCA Agent, Grounding Critic, and Commander Live ASK -- the highest-reasoning, slowest calls.' },
    { key: 'model.super_tier', label: 'Super tier', hint: 'Used by Watcher Agent and Commander guidance-reaction calls -- fast classification/acknowledgment.' },
    { key: 'model.fallback_tier', label: 'Fallback tier', hint: 'Automatically used if the ultra tier model times out or errors.' },
];

/**
 * Genuinely admin-editable AI model selection -- user request: "i should
 * be able to change settings whenever needed from admin console."
 * Backed by system_setting (migrations/018) + settings_service.py.
 * Every agent (BaseAgent/CommanderAgent/CommanderLiveAgent/WatcherAgent)
 * reads its model from this exact table at call time, so a change here
 * takes effect on the very next incident/LLM call -- zero code change,
 * zero restart.
 */
export function ModelSettingsTab({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void } = {}) {
    const [data, setData] = useState<SettingsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [savedKey, setSavedKey] = useState<string | null>(null);
    const [savingKey, setSavingKey] = useState<string | null>(null);
    const [timeoutDraft, setTimeoutDraft] = useState<string>('');
    // UI MODERNIZATION (spec Section 54): the timeout input is the only
    // field on this tab that holds an edit the user could lose by
    // switching tabs mid-type (the model-tier chips save instantly on
    // click, with no "draft" state to lose). Tracks whether the draft
    // currently differs from the last-saved server value.
    const savedTimeoutRef = useRef('');

    const load = () => {
        setLoading(true);
        setError(null);
        authFetch('/api/v2/admin/settings')
            .then(async (res) => {
                if (!res.ok) {
                    const body = await res.json().catch(() => ({}));
                    throw new Error(body?.detail || `HTTP ${res.status}`);
                }
                return res.json();
            })
            .then((d: SettingsResponse) => {
                setData(d);
                const serverValue = String(d.settings['model.fallback_timeout_seconds'] ?? 45);
                setTimeoutDraft(serverValue);
                savedTimeoutRef.current = serverValue;
                onDirtyChange?.(false);
            })
            .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
    }, []);

    const saveTier = async (settingKey: string, model: KnownModel) => {
        setSavingKey(settingKey);
        setError(null);
        try {
            const value: ModelTierValue = { model: model.model, extra_body: model.extra_body };
            const res = await authFetch(`/api/v2/admin/settings/${settingKey}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            setSavedKey(settingKey);
            setTimeout(() => setSavedKey(null), 2000);
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save');
        } finally {
            setSavingKey(null);
        }
    };

    const saveTimeout = async () => {
        const parsed = parseFloat(timeoutDraft);
        if (isNaN(parsed) || parsed <= 0) {
            setError('Timeout must be a positive number of seconds.');
            return;
        }
        setSavingKey('model.fallback_timeout_seconds');
        setError(null);
        try {
            const res = await authFetch('/api/v2/admin/settings/model.fallback_timeout_seconds', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: parsed }),
            });
            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.detail || `HTTP ${res.status}`);
            }
            setSavedKey('model.fallback_timeout_seconds');
            setTimeout(() => setSavedKey(null), 2000);
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save');
        } finally {
            setSavingKey(null);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Change which AI model each agent tier uses. Takes effect on the very next LLM call -- no restart required.
                </p>
                <Button size="sm" variant="secondary" onClick={load} loading={loading} leadingIcon={<RefreshCw className="w-3.5 h-3.5" />} className="flex-shrink-0">
                    Refresh
                </Button>
            </div>

            {loading && (
                <div className="space-y-4">
                    {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} className="h-[120px]" />)}
                </div>
            )}

            {error && (
                <div className="flex items-center gap-2 text-[12px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
                </div>
            )}

            {!loading && data && TIER_KEYS.map(({ key, label, hint }) => {
                const current = data.settings[key] as ModelTierValue | undefined;
                return (
                    <motion.div key={key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="console-surface rounded-2xl p-4 space-y-3">
                        <div className="flex items-center gap-2">
                            <Cpu className="w-3.5 h-3.5 text-primary" />
                            <div className="text-[13px] font-semibold text-text-primary">{label}</div>
                            {savedKey === key && (
                                <span className="text-[10.5px] font-semibold text-healthy flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Saved</span>
                            )}
                        </div>
                        <p className="text-[11px] text-text-muted">{hint}</p>
                        <div className="text-[11px] font-mono text-text-secondary bg-white/[0.03] ring-1 ring-white/[0.06] rounded-lg px-3 py-2">
                            Currently: {current?.model || '(unset)'}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {data.known_models.map((m) => {
                                const isActive = current?.model === m.model;
                                return (
                                    <Chip
                                        key={m.model}
                                        selected={isActive}
                                        mono
                                        onClick={() => saveTier(key, m)}
                                        disabled={savingKey === key || isActive}
                                        title={m.label}
                                    >
                                        {m.model}
                                    </Chip>
                                );
                            })}
                        </div>
                    </motion.div>
                );
            })}

            {!loading && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="console-surface rounded-2xl p-4 space-y-3">
                    <div className="flex items-center gap-2">
                        <Cpu className="w-3.5 h-3.5 text-primary" />
                        <div className="text-[13px] font-semibold text-text-primary">Fallback timeout</div>
                        {savedKey === 'model.fallback_timeout_seconds' && (
                            <span className="text-[10.5px] font-semibold text-healthy flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Saved</span>
                        )}
                    </div>
                    <p className="text-[11px] text-text-muted">Seconds to wait for the ultra-tier model before automatically retrying with the fallback tier.</p>
                    <div className="flex items-center gap-2">
                        <Input
                            type="number"
                            min="1"
                            value={timeoutDraft}
                            onChange={(e) => {
                                setTimeoutDraft(e.target.value);
                                onDirtyChange?.(e.target.value !== savedTimeoutRef.current);
                            }}
                            className="!w-28"
                        />
                        <span className="text-[11px] text-text-muted">seconds</span>
                        <Button
                            size="sm"
                            onClick={saveTimeout}
                            loading={savingKey === 'model.fallback_timeout_seconds'}
                            leadingIcon={<Save className="w-3.5 h-3.5" />}
                        >
                            Save
                        </Button>
                    </div>
                </motion.div>
            )}
        </div>
    );
}
