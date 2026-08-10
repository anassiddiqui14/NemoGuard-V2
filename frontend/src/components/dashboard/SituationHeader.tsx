import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { PlayCircle, ShieldAlert, Clock, Users, Briefcase, Layers, AlarmClock } from 'lucide-react';
import { LifecycleStepper, formatElapsedSeconds, severityPill, statusBadge } from './shared';
import type { IncidentSummary } from './shared';

interface Props {
    selectedIncident: IncidentSummary | null;
    alerts: any[];
    impact: any[];
    hypothesis: any;
    triageStarting: boolean;
    handleStartTriage: () => void;
}

function Metric({ icon, label, value, sub, accent }: { icon: React.ReactNode; label: string; value: React.ReactNode; sub: string; accent?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative rounded-xl p-3.5 bg-white/[0.02] ring-1 ring-white/[0.05] overflow-hidden group hover:ring-white/[0.09] hover:-translate-y-0.5 transition-all duration-200"
        >
            <div className="flex items-center gap-1.5 mb-2">
                <span className={`${accent || 'text-text-muted'}`}>{icon}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{label}</span>
            </div>
            <div className="text-xl font-semibold text-text-primary leading-none tabular-nums">{value}</div>
            <div className="text-[10.5px] text-text-muted mt-1">{sub}</div>
        </motion.div>
    );
}

/** Real-time countdown to `next_sla_breach_at`, ticking every second. */
function useLiveCountdown(target?: string | null) {
    const [remainingMs, setRemainingMs] = useState<number | null>(null);

    useEffect(() => {
        if (!target) {
            setRemainingMs(null);
            return;
        }
        const targetMs = new Date(target).getTime();
        const tick = () => setRemainingMs(targetMs - Date.now());
        tick();
        const t = window.setInterval(tick, 1000);
        return () => window.clearInterval(t);
    }, [target]);

    return remainingMs;
}

function SlaBreachCard({ incident, impact }: { incident: IncidentSummary; impact: any[] }) {
    const remainingMs = useLiveCountdown(incident.next_sla_breach_at);
    if (remainingMs === null) return null;

    const breached = remainingMs <= 0;
    const totalSeconds = Math.max(0, Math.floor(Math.abs(remainingMs) / 1000));
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;

    const urgent = !breached && remainingMs < 5 * 60 * 1000;
    const tone = breached ? 'critical' : urgent ? 'critical' : 'warning';
    const toneClasses = tone === 'critical'
        ? 'from-critical/15 ring-critical/30 text-critical'
        : 'from-warning/10 ring-warning/25 text-warning';

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`rounded-xl p-4 min-w-[170px] flex-shrink-0 text-right bg-gradient-to-br ${toneClasses} to-transparent ring-1`}
        >
            <div className="flex items-center justify-end gap-1.5 mb-1">
                <AlarmClock className={`w-3 h-3 ${urgent || breached ? 'animate-pulse' : ''}`} />
                <div className="text-[10px] font-semibold uppercase tracking-wider">
                    {breached ? 'SLA Breached' : 'Next SLA Breach'}
                </div>
            </div>
            <div className="text-3xl font-bold leading-none tabular-nums">
                {breached ? '+' : ''}{mins}
                <span className="text-sm font-medium">m</span> {secs.toString().padStart(2, '0')}
                <span className="text-sm font-medium">s</span>
            </div>
            {impact.length > 0 && (
                <div className="text-[11px] opacity-70 mt-1.5 truncate">{impact[0].asset_name || impact[0].asset_id}</div>
            )}
        </motion.div>
    );
}

export function SituationHeader({ selectedIncident, alerts, impact, hypothesis, triageStarting, handleStartTriage }: Props) {
    const status = selectedIncident?.status?.toUpperCase() || '';
    const canTriage = selectedIncident && (status === 'DETECTED' || status === '');

    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="glass-panel rounded-2xl p-5 lg:p-6 relative"
        >
            <div className="flex flex-col lg:flex-row items-start justify-between gap-4 mb-5">
                <div className="min-w-0 w-full lg:flex-1">
                    <div className="flex items-center gap-2.5 mb-3 flex-wrap">
                        {severityPill(selectedIncident?.severity)}
                        {statusBadge(selectedIncident?.status)}
                        <span className="text-[11px] font-mono text-text-muted truncate max-w-[160px]">{selectedIncident?.incident_id ?? '—'}</span>
                    </div>

                    <h1 className="text-[22px] font-semibold mb-2.5 tracking-tight leading-snug">
                        {selectedIncident?.title ?? 'No active incident selected'}
                    </h1>

                    <div className="text-[13px] text-text-muted flex flex-wrap items-center gap-x-4 gap-y-1 mb-4">
                        {selectedIncident && (
                            <>
                                <span className="flex items-center gap-1.5"><Layers className="w-3.5 h-3.5" /> {alerts.length > 0 ? alerts.length : 1} alerts → 1 incident</span>
                                <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {formatElapsedSeconds(selectedIncident.detected_at)} ago</span>
                                <span className="flex items-center gap-1.5"><Users className="w-3.5 h-3.5" /> {selectedIncident.owner_team || 'Data Operations'}</span>
                                <span className="flex items-center gap-1.5"><Briefcase className="w-3.5 h-3.5" /> <span className="font-mono text-[11px]">{selectedIncident.primary_job_id || 'UNKNOWN'}</span></span>
                            </>
                        )}
                    </div>

                    {selectedIncident?.summary && (
                        <div className="rounded-xl p-4 mb-4 bg-white/[0.02] ring-1 ring-white/[0.05]">
                            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">Executive Summary</h4>
                            <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-wrap">{selectedIncident.summary}</p>
                        </div>
                    )}

                    {canTriage && (
                        <button
                            onClick={handleStartTriage}
                            disabled={triageStarting}
                            className="press-scale inline-flex items-center gap-2 text-[13px] px-4 py-2 rounded-xl bg-gradient-to-r from-primary to-agent-active text-white hover:brightness-110 transition font-semibold disabled:opacity-60 shadow-lg shadow-primary/20"
                        >
                            <PlayCircle className="w-4 h-4" />
                            {triageStarting ? 'Starting investigation…' : 'Start Triage Now'}
                        </button>
                    )}
                </div>

                {selectedIncident && <SlaBreachCard incident={selectedIncident} impact={impact} />}
            </div>

            <div className="relative mb-5">
                <LifecycleStepper status={selectedIncident?.status ?? ''} />
            </div>

            <div className="relative grid grid-cols-2 md:grid-cols-5 gap-3">
                <Metric icon={<Layers className="w-3.5 h-3.5" />} label="Alerts" value={alerts.length > 0 ? `${alerts.length}→1` : '—'} sub="consolidated" />
                <Metric icon={<Briefcase className="w-3.5 h-3.5" />} label="Jobs" value={impact.filter((i) => i.impact_type?.includes('Job')).length || (impact.length > 0 ? 0 : '—')} sub="blocked jobs" accent="text-critical" />
                <Metric icon={<Layers className="w-3.5 h-3.5" />} label="Products" value={impact.filter((i) => !i.impact_type?.includes('Job')).length || (impact.length > 0 ? 0 : '—')} sub="at risk" accent="text-warning" />
                <Metric icon={<ShieldAlert className="w-3.5 h-3.5" />} label="Confidence" value={hypothesis ? `${Math.round(hypothesis.confidence_score * 100)}%` : '—'} sub="root cause" accent="text-agent-active" />
                <Metric icon={<Clock className="w-3.5 h-3.5" />} label="Elapsed" value={selectedIncident ? formatElapsedSeconds(selectedIncident.detected_at) : '—'} sub="since detection" />
            </div>
        </motion.div>
    );
}

export function SafetyReviewBanner({ feedback }: { feedback?: string }) {
    return (
        <div className="rounded-xl p-4 flex items-start gap-3 bg-gradient-to-br from-critical/10 to-transparent ring-1 ring-critical/25">
            <div className="w-8 h-8 rounded-lg bg-critical/15 flex items-center justify-center flex-shrink-0">
                <ShieldAlert className="w-4 h-4 text-critical" />
            </div>
            <div>
                <div className="text-[13px] font-semibold text-critical mb-1">Safety Agent flagged this plan</div>
                <div className="text-[12px] text-text-secondary leading-relaxed">
                    {feedback || 'The Grounding Critic could not fully verify evidence-to-conclusion grounding for this plan. Review carefully before approving.'}
                </div>
            </div>
        </div>
    );
}
