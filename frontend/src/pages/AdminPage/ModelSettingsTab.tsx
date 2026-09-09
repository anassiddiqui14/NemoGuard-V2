import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Loader2, AlertTriangle, CheckCircle2, Save, Cpu } from 'lucide-react';
import { authFetch } from '../../contexts/AuthGateContext';

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
export function ModelSettingsTab() {
    const [data, setData] = useState<SettingsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [savedKey, setSavedKey] = useState<string | null>(null);
    const [savingKey, setSavingKey] = useState<string | null>(null);
    const [timeoutDraft, setTimeoutDraft] = useState<string>('');

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
                setTimeoutDraft(String(d.settings['model.fallback_timeout_seconds'] ?? 45));
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

    if (loading) {
        return (
            <div className="console-surface rounded-2xl px-4 py-8 text-center text-[12px] text-text-muted">
                <Loader2 className="w-4 h-4 animate-spin inline mr-2" /> Loading settings...
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="text-[12.5px] text-text-muted">
                    Change which AI model each agent tier uses. Takes effect on the very next LLM call -- no restart required.
                </p>
                <button onClick={load} className="press-scale inline-flex items-center gap-2 text-[12px] font-medium px-3 py-1.5 rounded-lg ring-1 ring-white/[0.08] hover:bg-white/[0.05] transition flex-shrink-0">
                    <RefreshCw className="w-3.5 h-3.5" /> Refresh
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-2 text-[12px] text-critical bg-critical/10 ring-1 ring-critical/25 rounded-lg px-3 py-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
                </div>
            )}

            {data && TIER_KEYS.map(({ key, label, hint }) => {
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
                                    <button
                                        key={m.model}
                                        onClick={() => saveTier(key, m)}
                                        disabled={savingKey === key || isActive}
                                        title={m.label}
                                        className={`press-scale text-[10.5px] font-mono px-2.5 py-1.5 rounded-lg ring-1 transition-colors disabled:cursor-not-allowed ${isActive ? 'bg-primary/20 text-primary ring-primary/35' : 'bg-white/[0.03] text-text-muted ring-white/[0.06] hover:text-text-secondary hover:bg-white/[0.05]'}`}
                                    >
                                        {savingKey === key ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                                        {m.model}
                                    </button>
                                );
                            })}
                        </div>
                    </motion.div>
                );
            })}

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
                    <input
                        type="number"
                        min="1"
                        value={timeoutDraft}
                        onChange={(e) => setTimeoutDraft(e.target.value)}
                        className="w-28 rounded-lg px-3 py-2 text-[12.5px] bg-white/[0.03] ring-1 ring-white/[0.06] text-text-primary focus:outline-none focus:ring-primary/50"
                    />
                    <span className="text-[11px] text-text-muted">seconds</span>
                    <button
                        onClick={saveTimeout}
                        disabled={savingKey === 'model.fallback_timeout_seconds'}
                        className="press-scale inline-flex items-center gap-1.5 text-[11.5px] font-semibold px-3 py-2 rounded-lg bg-primary text-white disabled:opacity-50"
                    >
                        {savingKey === 'model.fallback_timeout_seconds' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                        Save
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
