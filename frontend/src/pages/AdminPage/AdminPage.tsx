import { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, MessageSquareShare, BrainCircuit, AlertOctagon, FlaskConical, Cpu } from 'lucide-react';
import { CapabilityPolicyTab } from './CapabilityPolicyTab';
import { TeamsRoutesTab } from './TeamsRoutesTab';
import { IncidentMemoryTab } from './IncidentMemoryTab';
import { FalseResolutionsTab } from './FalseResolutionsTab';
import { ModelEvaluationTab } from './ModelEvaluationTab';
import { ModelSettingsTab } from './ModelSettingsTab';

type AdminTab = 'model-settings' | 'capabilities' | 'teams' | 'memory' | 'false-resolutions' | 'model-eval';

const TABS: { key: AdminTab; label: string; icon: React.ReactNode }[] = [
    { key: 'model-settings', label: 'Model Settings', icon: <Cpu className="w-4 h-4" /> },
    { key: 'capabilities', label: 'Capability Policy', icon: <ShieldCheck className="w-4 h-4" /> },
    { key: 'teams', label: 'Teams Routes', icon: <MessageSquareShare className="w-4 h-4" /> },
    { key: 'memory', label: 'Incident Memory', icon: <BrainCircuit className="w-4 h-4" /> },
    { key: 'false-resolutions', label: 'False Resolutions', icon: <AlertOctagon className="w-4 h-4" /> },
    { key: 'model-eval', label: 'Model Evaluation', icon: <FlaskConical className="w-4 h-4" /> },
];

/**
 * Real NemoGuard admin controls -- surfaces backend endpoints that
 * already exist (all gated `require_role("admin")` in src/api/main.py)
 * but previously had zero frontend UI:
 *
 *   - Capability Policy: view every registered agent capability's
 *     effective risk level/autonomy mode and hot-reload the policy YAML
 *     (src/capabilities/policy.py, config/capability_policy.yaml).
 *   - Teams Routes: create/list MS Teams notification routing rules
 *     (teams_notification_route table).
 *   - Incident Memory: review/approve/edit/delete learned incident
 *     patterns (src/domain/memory/memory_engine.py) -- this is the
 *     actual governance surface over what NemoGuard "remembers".
 *   - False Resolutions: the real safety-net audit
 *     (src/domain/evaluation/false_resolution.py) over incidents marked
 *     RESOLVED without satisfied verification checks.
 *   - Model Evaluation: trigger/view AI model benchmark runs
 *     (src/domain/evaluation/evaluation_engine.py).
 *
 * Every control here calls a REAL, already-functioning backend endpoint
 * -- nothing is a placeholder toggle. Nav-gated to users with the
 * `admin` role (see GlobalNavRail.tsx), matching how the backend itself
 * already enforces this via require_role("admin") on every endpoint
 * used here.
 */
export function AdminPage() {
    const [tab, setTab] = useState<AdminTab>('model-settings');

    return (
        <div className="h-full overflow-y-auto p-6 max-w-6xl mx-auto space-y-5">
            <div>
                <h1 className="text-xl font-semibold text-text-primary tracking-tight flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-primary" /> Admin
                </h1>
                <p className="text-[13px] text-text-muted mt-1">
                    Real controls over NemoGuard's behavior -- capability policy, notification routing, learned incident memory, and safety audits.
                </p>
            </div>

            <div className="console-surface w-full rounded-2xl p-1.5">
                <div className="flex flex-wrap gap-1" role="tablist" aria-label="Admin sections">
                    {TABS.map((t) => (
                        <button
                            key={t.key}
                            onClick={() => setTab(t.key)}
                            role="tab"
                            aria-selected={tab === t.key}
                            className={`focus-ring relative flex-1 min-w-[120px] flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl text-[12px] font-semibold transition-colors ${tab === t.key ? 'text-text-primary' : 'text-text-muted hover:text-text-secondary hover:bg-white/[0.03]'
                                }`}
                        >
                            {tab === t.key && (
                                <motion.div
                                    layoutId="admin-tab-pill"
                                    className="absolute inset-0 rounded-xl bg-gradient-to-br from-white/[0.10] to-white/[0.04] ring-1 ring-primary/25 shadow-lg shadow-primary/5"
                                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                                />
                            )}
                            <span className="relative z-10 flex items-center gap-1.5">
                                {t.icon}
                                <span className="truncate">{t.label}</span>
                            </span>
                        </button>
                    ))}
                </div>
            </div>

            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
                {tab === 'model-settings' && <ModelSettingsTab />}
                {tab === 'capabilities' && <CapabilityPolicyTab />}
                {tab === 'teams' && <TeamsRoutesTab />}
                {tab === 'memory' && <IncidentMemoryTab />}
                {tab === 'false-resolutions' && <FalseResolutionsTab />}
                {tab === 'model-eval' && <ModelEvaluationTab />}
            </motion.div>
        </div>
    );
}
