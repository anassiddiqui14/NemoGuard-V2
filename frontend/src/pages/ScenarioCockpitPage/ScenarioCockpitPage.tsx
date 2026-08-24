import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import {
    Rocket, Cloud, Sparkles, RotateCcw, Database, Mail, GitBranch,
    AlertTriangle, CheckCircle2, XCircle, Loader2, PlayCircle, BellRing, Network,
} from 'lucide-react';

/**
 * The Scenario Cockpit is a visual control surface for demoing/testing
 * NemoGuard's agent pipeline: fire scripted webhook scenarios, break real
 * AWS-emulated jobs (Lambda/S3/Step Functions via LocalStack) and watch
 * NemoGuard actually detect and respond, or describe a fully custom
 * incident in plain English for the LLM to synthesize. All requests go
 * through /sim/ (proxied by Nginx to simulator_backend) so the browser
 * never talks directly to the simulator's internal port.
 */

const SIM_BASE = '/sim';

function Section({ icon, title, subtitle, children, right }: {
    icon: React.ReactNode; title: string; subtitle: string; children: React.ReactNode; right?: React.ReactNode;
}) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="glass-panel rounded-2xl ring-1 ring-white/[0.06] overflow-hidden"
        >
            <div className="px-5 py-4 flex items-center justify-between border-b border-white/[0.05]">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/20 to-agent-active/20 flex items-center justify-center text-primary flex-shrink-0">
                        {icon}
                    </div>
                    <div>
                        <div className="font-semibold text-[14px] text-text-primary">{title}</div>
                        <div className="text-[11.5px] text-text-muted mt-0.5">{subtitle}</div>
                    </div>
                </div>
                {right}
            </div>
            <div className="p-5">{children}</div>
        </motion.div>
    );
}

function ScenarioButton({ label, description, tone = 'default', onClick, disabled, loading }: {
    label: string; description?: string; tone?: 'default' | 'critical' | 'warning'; onClick: () => void; disabled?: boolean; loading?: boolean;
}) {
    const toneClasses = tone === 'critical'
        ? 'ring-critical/30 hover:bg-critical/10 text-critical'
        : tone === 'warning'
            ? 'ring-warning/30 hover:bg-warning/10 text-warning'
            : 'ring-white/[0.08] hover:bg-white/[0.05] text-text-secondary hover:text-text-primary';
    return (
        <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={onClick}
            disabled={disabled || loading}
            className={`w-full text-left rounded-xl p-3.5 ring-1 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-between gap-3 ${toneClasses}`}
        >
            <div>
                <div className="text-[12.5px] font-semibold">{label}</div>
                {description && <div className="text-[11px] text-text-muted mt-0.5">{description}</div>}
            </div>
            {loading ? <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" /> : <PlayCircle className="w-4 h-4 flex-shrink-0 opacity-60" />}
        </motion.button>
    );
}

async function postJson(path: string, body?: any) {
    const res = await fetch(`${SIM_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
    });
    let data: any = null;
    try { data = await res.json(); } catch { /* no body */ }
    if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
    }
    return data;
}

type AlarmState = { alarm_name: string; state: string; state_reason: string; state_updated_at: string };

export function ScenarioCockpitPage() {
    const [labStatus, setLabStatus] = useState<{ available: boolean; detail: string } | null>(null);
    const [loadingKey, setLoadingKey] = useState<string | null>(null);
    const [prompt, setPrompt] = useState('');
    const [aiStreamStatus, setAiStreamStatus] = useState<string | null>(null);
    const [aiRunning, setAiRunning] = useState(false);
    const [alarms, setAlarms] = useState<AlarmState[] | null>(null);
    const [correlationLog, setCorrelationLog] = useState<string[] | null>(null);
    const [correlationRunning, setCorrelationRunning] = useState<string | null>(null);

    const refreshLabStatus = () => {
        fetch(`${SIM_BASE}/lab/status`)
            .then((r) => r.json())
            .then((d) => setLabStatus(d))
            .catch(() => setLabStatus({ available: false, detail: 'Simulator unreachable.' }));
    };

    const refreshAlarms = () => {
        fetch(`${SIM_BASE}/lab/alarms`)
            .then((r) => (r.ok ? r.json() : null))
            .then((d) => setAlarms(d?.alarms ?? null))
            .catch(() => setAlarms(null));
    };

    useEffect(() => {
        refreshLabStatus();
        refreshAlarms();
        const t = setInterval(() => { refreshLabStatus(); refreshAlarms(); }, 15000);
        return () => clearInterval(t);
    }, []);

    const run = async (key: string, path: string, body: any, successLabel: string) => {
        setLoadingKey(key);
        try {
            await postJson(path, body);
            toast.success(successLabel);
        } catch (e) {
            toast.error(e instanceof Error ? e.message : 'Request failed');
        } finally {
            setLoadingKey(null);
        }
    };

    const runScripted = (scenarioType: string, label: string) =>
        run(scenarioType, '/trigger', { scenario_type: scenarioType }, `Fired ${label} webhook into NemoGuard.`);

    const runLab = (key: string, endpoint: string, scenario: string, label: string) =>
        run(key, `/lab/trigger/${endpoint}`, { scenario }, `${label} — real AWS lab invocation completed. Alarm forwarding may take up to ~15s.`);

    const runReset = () => run('reset', '/reset', undefined, 'Cleared all incidents and alerts.');

    const runCorrelationCheck = async (check: 'same_alarm' | 'different_alarm') => {
        setCorrelationRunning(check);
        setCorrelationLog([]);
        try {
            const res = await fetch(`${SIM_BASE}/lab/correlation-check`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ check }),
            });
            if (res.ok && res.body) {
                const reader = res.body.getReader();
                const decoder = new TextDecoder('utf-8');
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    for (const line of text.split('\n')) {
                        if (line.startsWith('status: ')) {
                            const msg = line.replace('status: ', '');
                            setCorrelationLog((prev) => [...(prev ?? []), msg]);
                        }
                    }
                }
            } else {
                toast.error('Correlation check failed to start.');
            }
        } catch {
            toast.error('Network error reaching the simulator.');
        } finally {
            setCorrelationRunning(null);
        }
    };

    const runAi = async () => {
        if (!prompt.trim()) return;
        setAiRunning(true);
        setAiStreamStatus('Contacting LLM...');
        try {
            const res = await fetch(`${SIM_BASE}/trigger/ai`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt }),
            });
            if (res.ok && res.body) {
                const reader = res.body.getReader();
                const decoder = new TextDecoder('utf-8');
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    for (const line of text.split('\n')) {
                        if (line.startsWith('status: ')) setAiStreamStatus(line.replace('status: ', ''));
                    }
                }
                setPrompt('');
                toast.success('Custom scenario injected into NemoGuard.');
            } else {
                toast.error('Failed to generate custom scenario.');
            }
        } catch {
            toast.error('Network error reaching the simulator.');
        } finally {
            setAiRunning(false);
            setTimeout(() => setAiStreamStatus(null), 4000);
        }
    };

    return (
        <div className="h-full overflow-y-auto p-6 max-w-5xl mx-auto space-y-5">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-xl font-semibold text-text-primary tracking-tight flex items-center gap-2">
                        <Rocket className="w-5 h-5 text-primary" /> Scenario Cockpit
                    </h1>
                    <p className="text-[13px] text-text-muted mt-1">
                        Control demo scenarios, trigger real AWS/Airflow-style jobs, and introduce error conditions for NemoGuard to detect and respond to.
                    </p>
                </div>
                <motion.button
                    whileTap={{ scale: 0.96 }}
                    onClick={runReset}
                    disabled={loadingKey === 'reset'}
                    className="press-scale inline-flex items-center gap-2 text-[12.5px] font-semibold px-4 py-2.5 rounded-xl ring-1 ring-critical/30 text-critical hover:bg-critical/10 transition disabled:opacity-50 flex-shrink-0"
                >
                    {loadingKey === 'reset' ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                    Reset All Incidents
                </motion.button>
            </div>

            {/* Scripted webhook scenarios — instant, no real infra required */}
            <Section
                icon={<AlertTriangle className="w-4.5 h-4.5" />}
                title="Scripted Failure Scenarios"
                subtitle="Instantly fires pre-built log + webhook payloads directly into NemoGuard's ingestion endpoint."
            >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <ScenarioButton
                        label="Schema Regression"
                        description="customer_profile validation failure cascading to marketing_sync_job"
                        tone="critical"
                        loading={loadingKey === 'SCHEMA_REGRESSION'}
                        onClick={() => runScripted('SCHEMA_REGRESSION', 'Schema Regression')}
                    />
                    <ScenarioButton
                        label="Spark OOM Crash"
                        description="AWS_EXTRACT_RESERVATION job exhausts heap space"
                        tone="warning"
                        loading={loadingKey === 'OOM_CRASH'}
                        onClick={() => runScripted('OOM_CRASH', 'Spark OOM Crash')}
                    />
                    <ScenarioButton
                        label="Cascading Failure"
                        description="auth_db deadlock -> auth_api -> checkout -> payment -> reporting"
                        tone="critical"
                        loading={loadingKey === 'CASCADING_FAILURE'}
                        onClick={() => runScripted('CASCADING_FAILURE', 'Cascading Failure')}
                    />
                </div>
            </Section>

            {/* Real AWS lab (LocalStack): genuine Lambda/S3/CloudWatch/SQS/Step Functions */}
            <Section
                icon={<Cloud className="w-4.5 h-4.5" />}
                title="Real AWS Lab (LocalStack)"
                subtitle="Genuinely breaks real Lambda/S3/Step Functions jobs -- not scripted payloads -- and NemoGuard is notified via a real CloudWatch Alarm -> SNS -> SQS chain."
                right={
                    labStatus ? (
                        <span className={`text-[10.5px] font-bold px-2.5 py-1 rounded-full ring-1 flex items-center gap-1.5 ${labStatus.available ? 'bg-healthy/10 text-healthy ring-healthy/25' : 'bg-warning/10 text-warning ring-warning/25'}`}>
                            {labStatus.available ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                            {labStatus.available ? 'Lab Ready' : 'Lab Unavailable'}
                        </span>
                    ) : undefined
                }
            >
                {labStatus && !labStatus.available && (
                    <div className="mb-4 text-[11.5px] text-warning bg-warning/5 ring-1 ring-warning/20 rounded-lg px-3 py-2">
                        {labStatus.detail}
                    </div>
                )}
                <div className="space-y-4">
                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-2 flex items-center gap-1.5">
                            <Database className="w-3.5 h-3.5" /> Ingest Job (S3 → Lambda → Postgres)
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <ScenarioButton
                                label="Schema Drift"
                                description="Real object missing last_login_ip -> real KeyError"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_ingest_schema_drift'}
                                onClick={() => runLab('lab_ingest_schema_drift', 'ingest', 'schema_drift', 'Schema Drift')}
                            />
                            <ScenarioButton
                                label="OOM Crash"
                                description="Real MemoryError raised inside the Lambda"
                                tone="warning"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_ingest_oom'}
                                onClick={() => runLab('lab_ingest_oom', 'ingest', 'oom_crash', 'OOM Crash')}
                            />
                            <ScenarioButton
                                label="DB Outage"
                                description="Real connection failure to Postgres from the job"
                                tone="warning"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_ingest_db_outage'}
                                onClick={() => runLab('lab_ingest_db_outage', 'ingest', 'db_outage', 'DB Outage')}
                            />
                            <ScenarioButton
                                label="Healthy (sanity check)"
                                description="Confirms the job succeeds normally"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_ingest_healthy'}
                                onClick={() => runLab('lab_ingest_healthy', 'ingest', 'healthy', 'Healthy ingest run')}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-2 flex items-center gap-1.5">
                            <GitBranch className="w-3.5 h-3.5" /> Order Events Job (Glue-style partial write)
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <ScenarioButton
                                label="Partial Write Crash"
                                description="Genuinely commits half a batch, then crashes mid-write"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_order_events_crash'}
                                onClick={() => runLab('lab_order_events_crash', 'order_events', 'partial_write_crash', 'Partial Write Crash')}
                            />
                            <ScenarioButton
                                label="Duplicate Write"
                                description="Real UniqueViolation from a retry re-sending a committed order_id"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_order_events_duplicate'}
                                onClick={() => runLab('lab_order_events_duplicate', 'order_events', 'duplicate_write', 'Duplicate Write')}
                            />
                            <ScenarioButton
                                label="Healthy (sanity check)"
                                description="Confirms the full batch commits successfully"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_order_events_healthy'}
                                onClick={() => runLab('lab_order_events_healthy', 'order_events', 'healthy', 'Healthy order events run')}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-2 flex items-center gap-1.5">
                            <Mail className="w-3.5 h-3.5" /> Notification Job (SQS poison-pill)
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <ScenarioButton
                                label="Poison Pill"
                                description="Malformed SQS message the consumer can't process"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_notification_poison'}
                                onClick={() => runLab('lab_notification_poison', 'notification', 'poison_pill', 'Poison Pill')}
                            />
                            <ScenarioButton
                                label="Healthy (sanity check)"
                                description="Confirms a valid message succeeds"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_notification_healthy'}
                                onClick={() => runLab('lab_notification_healthy', 'notification', 'healthy', 'Healthy notification run')}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted mb-2 flex items-center gap-1.5">
                            <GitBranch className="w-3.5 h-3.5" /> Daily Pipeline (Step Functions, multi-step)
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <ScenarioButton
                                label="Ingest Step Fails"
                                description="First state fails; second state never runs"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_pipeline_ingest_fails'}
                                onClick={() => runLab('lab_pipeline_ingest_fails', 'pipeline', 'ingest_step_fails', 'Ingest Step Fails')}
                            />
                            <ScenarioButton
                                label="Order Events Step Fails"
                                description="Ingest succeeds; second state crashes mid-batch"
                                tone="critical"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_pipeline_order_events_fails'}
                                onClick={() => runLab('lab_pipeline_order_events_fails', 'pipeline', 'order_events_step_fails', 'Order Events Step Fails')}
                            />
                            <ScenarioButton
                                label="Healthy (sanity check)"
                                description="Both steps succeed end-to-end"
                                disabled={!labStatus?.available}
                                loading={loadingKey === 'lab_pipeline_healthy'}
                                onClick={() => runLab('lab_pipeline_healthy', 'pipeline', 'healthy', 'Healthy pipeline execution')}
                            />
                        </div>
                    </div>
                </div>
            </Section>

            {/* Real CloudWatch alarm lifecycle -- live state + acknowledge/reset,
                previously only exercised via scripts/run_scenario_catalog_30.py
                with no cockpit UI/API path at all. */}
            <Section
                icon={<BellRing className="w-4.5 h-4.5" />}
                title="Alarm Lifecycle (real CloudWatch state)"
                subtitle="Live state of every lab CloudWatch alarm -- trips on real errors, stays ALARM on repeat failures (no re-notify), and can be acknowledged/reset here after a verified fix."
                right={
                    <motion.button
                        whileTap={{ scale: 0.96 }}
                        onClick={refreshAlarms}
                        className="text-[11px] font-semibold px-3 py-1.5 rounded-lg ring-1 ring-white/[0.08] text-text-secondary hover:bg-white/[0.05] transition"
                    >
                        Refresh
                    </motion.button>
                }
            >
                {!alarms ? (
                    <div className="text-[12px] text-text-muted">Alarm states unavailable -- provision the lab first.</div>
                ) : (
                    <div className="space-y-2">
                        {alarms.map((a) => {
                            const isAlarm = a.state === 'ALARM';
                            return (
                                <div
                                    key={a.alarm_name}
                                    className="flex items-center justify-between gap-3 rounded-xl p-3.5 ring-1 ring-white/[0.06] bg-white/[0.02]"
                                >
                                    <div className="min-w-0">
                                        <div className="text-[12.5px] font-semibold text-text-primary truncate">{a.alarm_name}</div>
                                        <div className="text-[11px] text-text-muted mt-0.5 truncate">{a.state_reason || 'No state reason yet.'}</div>
                                    </div>
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className={`text-[10.5px] font-bold px-2.5 py-1 rounded-full ring-1 flex items-center gap-1.5 ${isAlarm ? 'bg-critical/10 text-critical ring-critical/25' : 'bg-healthy/10 text-healthy ring-healthy/25'}`}>
                                            {isAlarm ? <XCircle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                                            {a.state}
                                        </span>
                                        <motion.button
                                            whileTap={{ scale: 0.96 }}
                                            disabled={!isAlarm || loadingKey === `alarm_reset_${a.alarm_name}`}
                                            onClick={() => run(`alarm_reset_${a.alarm_name}`, '/lab/alarms/reset', { alarm_name: a.alarm_name }, `${a.alarm_name} acknowledged and reset to OK.`).then(refreshAlarms)}
                                            className="text-[11px] font-semibold px-3 py-1.5 rounded-lg ring-1 ring-healthy/30 text-healthy hover:bg-healthy/10 transition disabled:opacity-30 disabled:cursor-not-allowed"
                                        >
                                            {loadingKey === `alarm_reset_${a.alarm_name}` ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Acknowledge & Reset'}
                                        </motion.button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </Section>

            {/* Real cross-cutting alert-correlation verification -- mirrors
                scripts/run_scenario_catalog_30.py's scenario_28/29 exactly,
                previously exercised only via that CLI script with zero
                cockpit UI/API path. */}
            <Section
                icon={<Network className="w-4.5 h-4.5" />}
                title="Alert Correlation Verification"
                subtitle="Triggers two REAL, sequential Lambda failures and observes NemoGuard's actual correlation decision -- not a scripted assertion. Each check takes up to ~5 minutes (real webhook forwarding + LLM correlation + polling)."
            >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                    <ScenarioButton
                        label="Same Alarm -> Same Incident"
                        description="schema_drift then oom_crash (same alarm) -- expects BOTH to land on ONE incident"
                        tone="default"
                        disabled={!labStatus?.available || !!correlationRunning}
                        loading={correlationRunning === 'same_alarm'}
                        onClick={() => runCorrelationCheck('same_alarm')}
                    />
                    <ScenarioButton
                        label="Different Alarm -> Different Incident"
                        description="schema_drift then order_events partial_write_crash -- expects TWO separate incidents"
                        tone="default"
                        disabled={!labStatus?.available || !!correlationRunning}
                        loading={correlationRunning === 'different_alarm'}
                        onClick={() => runCorrelationCheck('different_alarm')}
                    />
                </div>
                {correlationLog && (
                    <div className="rounded-xl ring-1 ring-white/[0.06] bg-black/20 p-3 max-h-64 overflow-y-auto space-y-1">
                        {correlationLog.map((line, i) => (
                            <div
                                key={i}
                                className={`text-[11.5px] font-mono ${line.startsWith('RESULT: PASS') ? 'text-healthy font-semibold' : line.startsWith('RESULT: FAIL') ? 'text-critical font-semibold' : line.startsWith('ERROR') ? 'text-warning' : 'text-text-secondary'}`}
                            >
                                {line}
                            </div>
                        ))}
                        {correlationRunning && <div className="text-[11.5px] text-text-muted flex items-center gap-2"><Loader2 className="w-3 h-3 animate-spin" /> Running...</div>}
                    </div>
                )}
            </Section>

            {/* Generative AI custom scenario */}
            <Section
                icon={<Sparkles className="w-4.5 h-4.5" />}
                title="Generative AI Simulator"
                subtitle="Describe any incident in plain English -- the LLM synthesizes matching logs, alerts, business-asset impact, and runbooks."
            >
                <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="e.g. A severe network partition in the payments gateway causing timeouts and downstream checkout failures..."
                    className="w-full h-24 px-4 py-3 rounded-xl bg-white/[0.03] ring-1 ring-white/[0.06] text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-primary/50 transition-all resize-vertical mb-3"
                />
                <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={runAi}
                    disabled={!prompt.trim() || aiRunning}
                    className="w-full flex items-center justify-center gap-2 text-[13px] px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold disabled:opacity-40"
                >
                    {aiRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    {aiRunning ? 'Generating…' : 'Generate Custom Incident'}
                </motion.button>
                {aiStreamStatus && (
                    <div className="mt-3 text-[11.5px] text-text-secondary bg-white/[0.02] ring-1 ring-white/[0.06] rounded-lg px-3 py-2">
                        {aiStreamStatus}
                    </div>
                )}
            </Section>
        </div>
    );
}
