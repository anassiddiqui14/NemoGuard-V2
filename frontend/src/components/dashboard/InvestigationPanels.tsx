import { AnimatePresence, motion } from 'framer-motion';
import { ResponsiveContainer, Radar, RadarChart, PolarGrid, PolarAngleAxis, Tooltip } from 'recharts';
import { AgentConstellation, InvestigationChecklist } from '../AgentConstellation';
import { LiveOperationsConsole } from '../LiveOperationsConsole';
import { EmptyState, severityPill } from './shared';
import { InvestigationGlyphIcon } from '../../pages/LandingPage/NemoIcons';
import { Search, Activity, TrendingUp, ChevronDown, Lightbulb } from 'lucide-react';
import type { AgentEvent } from '../../hooks/useIncidentEvents';

function Card({ title, subtitle, right, children, className = '', titleIcon }: { title: string; subtitle?: string; right?: React.ReactNode; children: React.ReactNode; className?: string; titleIcon?: React.ReactNode }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className={`console-surface rounded-2xl overflow-hidden flex flex-col ${className}`}
        >
            <div className="px-4 py-3.5 flex items-center justify-between border-b border-white/[0.05]">
                <div>
                    <div className="font-semibold text-[13px] text-text-primary flex items-center gap-1.5">
                        {titleIcon}
                        {title}
                    </div>
                    {subtitle && <div className="text-[11px] text-text-muted mt-0.5">{subtitle}</div>}
                </div>
                {right}
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
        </motion.div>
    );
}

export function AlertsPanel({ alerts, expandedAlert, setExpandedAlert }: { alerts: any[]; expandedAlert: string | null; setExpandedAlert: (id: string | null) => void }) {
    if (!alerts || alerts.length === 0) return null;
    return (
        <Card title="Consolidated Alerts" subtitle="Downstream alerts dynamically grouped into this incident" right={
            <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-primary/15 text-primary ring-1 ring-primary/30">{alerts.length} alerts</span>
        }>
            <div className="p-4 space-y-2.5">
                {alerts.map((alt: any) => {
                    const isExpanded = expandedAlert === alt.alert_id;
                    return (
                        <div
                            key={alt.alert_id}
                            className={`interactive-surface rounded-xl border ${isExpanded
                                ? 'border-primary/25 bg-primary/[0.04] shadow-lg shadow-primary/5'
                                : 'border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.04]'
                                }`}
                        >
                            <button
                                type="button"
                                aria-expanded={isExpanded}
                                onClick={() => setExpandedAlert(isExpanded ? null : alt.alert_id)}
                                className="focus-ring w-full px-3.5 py-3 flex items-center justify-between gap-3 text-left rounded-xl"
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <span
                                        className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase flex-shrink-0 ${alt.severity === 'critical' ? 'bg-critical/15 text-critical' : alt.severity === 'high' ? 'bg-warning/15 text-warning' : 'bg-healthy/15 text-healthy'}`}
                                    >
                                        {alt.severity}
                                    </span>
                                    <div className="min-w-0">
                                        <div className="font-medium text-[12.5px] leading-5 text-text-primary truncate">{alt.source_system} · {alt.alert_type}</div>
                                        <div className="text-[11px] leading-4 text-text-muted truncate">{alt.message}</div>
                                    </div>
                                </div>
                                <ChevronDown
                                    className={`w-4 h-4 text-text-muted flex-shrink-0 transition-transform duration-150 ${isExpanded ? 'rotate-180 text-primary' : ''}`}
                                />
                            </button>

                            {isExpanded && (
                                <div className="border-t border-white/[0.07] px-3.5 py-3 bg-black/[0.12]">
                                    <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">Alert details</div>
                                    <p className="text-[12px] font-mono text-text-secondary leading-5 whitespace-pre-wrap break-words">
                                        {alt.message}
                                    </p>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </Card>
    );
}

function describeInvestigationProgress(events: AgentEvent[]): { title: string; subtitle: string } {
    const hasEvent = (types: string[]) => events.some((e) => types.includes(e.event_type));
    const rcaDone = hasEvent(['HYPOTHESIS_CREATED']);
    const impactDone = hasEvent(['IMPACT_CALCULATED']);
    const runbookDone = hasEvent(['RUNBOOK_RETRIEVED']);
    const safetyDone = hasEvent(['SAFETY_VALIDATION_PASSED', 'SAFETY_VALIDATION_FAILED']);

    if (!rcaDone) {
        return { title: 'RCA Agent is investigating logs…', subtitle: 'Synthesizing evidence from execution logs and topology.' };
    }
    if (!impactDone || !runbookDone) {
        return { title: 'Impact & Runbook Agents are assessing blast radius…', subtitle: 'Root cause identified — calculating downstream impact and matching recovery procedures.' };
    }
    if (!safetyDone) {
        return { title: 'Safety Agent is validating the recovery plan…', subtitle: 'Independently verifying plan grounding before the hypothesis is finalized.' };
    }
    return { title: 'Finalizing root-cause hypothesis…', subtitle: 'Persisting findings from the completed investigation.' };
}

export function AgentAndHypothesisRow({
    activeIncidentId, incidentStatus, liveEvents, hypothesis, evidence, dataLoading, onViewEvidence,
}: {
    activeIncidentId: string | null;
    incidentStatus: string;
    liveEvents: AgentEvent[];
    hypothesis: any;
    evidence: any[];
    dataLoading: boolean;
    onViewEvidence: () => void;
}) {
    const progress = dataLoading ? describeInvestigationProgress(liveEvents) : null;
    return (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-4 items-start">
            <Card title="Agent Constellation" subtitle="Coordinated multi-agent investigation" className="h-[400px]">
                <div className="p-4 h-full overflow-y-auto">
                    {activeIncidentId ? (
                        <AgentConstellation status={incidentStatus} events={liveEvents} />
                    ) : (
                        <EmptyState icon={<Activity className="w-5 h-5" />} title="No incident selected" subtitle="Select an incident from the queue to see live agent activity." />
                    )}
                </div>
            </Card>

            <Card
                title="Root-Cause Hypothesis"
                subtitle="Ranked and evidence-grounded"
                titleIcon={<InvestigationGlyphIcon className="w-3.5 h-3.5 text-agent-active" />}
                right={
                    <button onClick={onViewEvidence} className="focus-ring press-scale text-[11px] font-medium px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] ring-1 ring-white/[0.06] transition flex items-center gap-1.5 text-text-secondary">
                        <Search className="w-3 h-3" /> Evidence
                    </button>
                }
                className="h-[400px]"
            >
                <div className="p-4 h-full overflow-y-auto">
                    {!hypothesis ? (
                        activeIncidentId && liveEvents.length > 0 ? (
                            // UI MODERNIZATION (spec Section 43 -- "NemoGuard
                            // Investigation" branded checklist loader): while
                            // waiting on a hypothesis, show real per-agent
                            // progress (reusing AgentConstellation's exact
                            // state computation, so this can never say
                            // something different than the grid view does)
                            // instead of a generic "no hypothesis yet" empty
                            // state with zero indication of what's actually
                            // happening.
                            <InvestigationChecklist status={incidentStatus} events={liveEvents} />
                        ) : (
                            <EmptyState
                                icon={<TrendingUp className="w-5 h-5" />}
                                title={progress ? progress.title : 'No hypothesis formulated yet'}
                                subtitle={progress ? progress.subtitle : 'Start triage to begin root-cause analysis.'}
                            />
                        )
                    ) : (
                        <div className="space-y-4">
                            <div className="relative rounded-xl p-4 bg-gradient-to-br from-agent-active/10 to-transparent ring-1 ring-agent-active/20">
                                <div className="flex items-start gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-agent-active/15 flex items-center justify-center flex-shrink-0">
                                        <Lightbulb className="w-4 h-4 text-agent-active" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium text-[13px] leading-relaxed text-text-primary break-words">{hypothesis.title}</div>
                                        <div className="mt-2.5 flex gap-1.5 flex-wrap">
                                            {evidence.slice(0, 3).map((ev: any) => (
                                                <span key={ev.evidence_id} className="text-[10px] px-2 py-0.5 bg-white/[0.04] ring-1 ring-white/[0.06] rounded-md font-mono text-text-muted">
                                                    {ev.source || ev.evidence_id?.substring(0, 8)}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="flex-shrink-0 text-right">
                                        <div className="text-agent-active font-bold text-2xl leading-none tabular-nums">{Math.round((hypothesis.confidence_score || 0) * 100)}%</div>
                                        <div className="text-[9.5px] text-text-muted mt-0.5 uppercase tracking-wide">confidence</div>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <div className="text-[10.5px] font-semibold uppercase tracking-wider text-text-muted mb-2.5">Causal Chain</div>
                                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] font-medium whitespace-nowrap">
                                    {evidence.length > 0 ? (
                                        evidence.slice(0, 4).map((ev, idx) => (
                                            <div key={ev.evidence_id || idx} className="flex items-center gap-1.5">
                                                {idx > 0 && <span className="text-text-muted">→</span>}
                                                <span className="px-2.5 py-1 bg-critical/10 text-critical ring-1 ring-critical/20 rounded-lg truncate max-w-[140px]" title={ev.description || ev.title}>
                                                    {ev.description || ev.title}
                                                </span>
                                            </div>
                                        ))
                                    ) : (
                                        <span className="text-text-muted">No evidence linked yet.</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </Card>
        </div>
    );
}

export function ActivityAndImpactRow({ activeIncidentId, liveEvents, sseStatus, selectedSeverity, impact }: {
    activeIncidentId: string | null;
    liveEvents: AgentEvent[];
    sseStatus: 'connecting' | 'connected' | 'disconnected';
    selectedSeverity: string | undefined;
    impact: any[];
}) {
    return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Card
                title="Agent Activity"
                subtitle="Live thought and execution stream"
                right={
                    <span className="flex items-center gap-1.5 text-[10px] font-bold px-2 py-1 rounded-full bg-healthy/10 text-healthy">
                        <span className={`w-1.5 h-1.5 rounded-full ${sseStatus === 'connected' ? 'bg-healthy animate-pulse' : 'bg-text-muted'}`} />
                        {sseStatus === 'connected' ? 'LIVE' : sseStatus.toUpperCase()}
                    </span>
                }
                className="h-[360px]"
            >
                {activeIncidentId ? (
                    <LiveOperationsConsole events={liveEvents} status={sseStatus} />
                ) : (
                    <EmptyState icon={<Activity className="w-5 h-5" />} title="No active incident" />
                )}
            </Card>

            <Card title="Business Impact" subtitle="Technical and customer-facing blast radius" right={severityPill(selectedSeverity)} className="h-[360px]">
                <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
                    <div className="h-[190px] w-full">
                        {impact.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={[
                                    { subject: 'Jobs', A: impact.filter((i) => i.impact_type?.includes('Job')).length, fullMark: Math.max(impact.length, 5) },
                                    { subject: 'Products', A: impact.filter((i) => !i.impact_type?.includes('Job')).length, fullMark: Math.max(impact.length, 5) },
                                    {
                                        subject: 'Business risk',
                                        A: Math.round(
                                            (impact.reduce((sum, i) => sum + (typeof i.impact_score === 'number' ? i.impact_score : 0), 0) / impact.length) * 10,
                                        ),
                                        fullMark: 10,
                                    },
                                    {
                                        subject: 'SLA at risk',
                                        A: impact.filter((i) => ['AT_RISK', 'BREACHED'].includes(String(i.sla_status || '').toUpperCase())).length,
                                        fullMark: Math.max(impact.length, 5),
                                    },
                                ]}>
                                    {/* UI MODERNIZATION (spec Section 53): this chart previously had HARDCODED dark-mode-only colors (a literal #14141F hex and rgba(255,255,255,...) white-overlay values that never adapted to light mode). Now uses the dedicated chart token set in index.css instead of hand-rolled raw color values. */}
                                    <PolarGrid stroke="var(--chart-grid)" />
                                    <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--chart-axis-text)', fontSize: 9.5 }} />
                                    <Tooltip contentStyle={{ backgroundColor: 'var(--chart-tooltip-bg)', borderColor: 'var(--chart-tooltip-border)', borderRadius: '10px', fontSize: '12px', color: 'var(--chart-tooltip-text)' }} />
                                    <Radar name="Impact" dataKey="A" stroke="var(--chart-secondary)" fill="var(--chart-secondary)" fillOpacity={0.35} />
                                </RadarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-text-muted text-xs">No impact data yet</div>
                        )}
                    </div>

                    <div className="space-y-2 overflow-y-auto max-h-[190px]">
                        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-text-muted mb-2">Affected Assets</div>
                        {impact.length > 0 ? (
                            <AnimatePresence>
                                {impact.map((imp, idx) => (
                                    <motion.div
                                        key={imp.asset_id || idx}
                                        initial={{ opacity: 0, x: 16 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: 0.08 * idx }}
                                        className="interactive-surface flex items-center justify-between p-2.5 mb-1.5 rounded-lg bg-white/[0.02] ring-1 ring-white/[0.05]"
                                    >
                                        <div className="min-w-0 pr-2">
                                            <div className="font-medium text-[12px] text-text-secondary truncate">{imp.asset_name || imp.asset_id}</div>
                                            <div className="text-[9.5px] text-text-muted mt-0.5">
                                                {imp.business_risk ? `${imp.business_risk} risk · ${Math.round((imp.impact_score || 0) * 100)} score` : (imp.impact_status || imp.status || 'AT RISK')}
                                            </div>
                                        </div>
                                        <span
                                            className={`text-[9px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${String(imp.sla_status || '').toUpperCase() === 'BREACHED'
                                                ? 'bg-critical/15 text-critical'
                                                : String(imp.sla_status || '').toUpperCase() === 'AT_RISK'
                                                    ? 'bg-warning/15 text-warning'
                                                    : 'bg-healthy/15 text-healthy'
                                                }`}
                                        >
                                            {imp.sla_status === 'UNKNOWN' ? 'SLA UNKNOWN' : (imp.sla_status || imp.impact_status || imp.status || 'AT RISK')}
                                        </span>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        ) : (
                            <div className="text-[12px] text-text-muted py-2">No assets currently affected.</div>
                        )}
                    </div>
                </div>
            </Card>
        </div>
    );
}
