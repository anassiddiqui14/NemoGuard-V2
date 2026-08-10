import React from 'react';

export type IncidentSummary = {
    incident_id: string;
    title: string;
    status: string;
    severity: string;
    detected_at: string;
    next_sla_breach_at: string | null;
    owner_team?: string;
    primary_job_id?: string;
    summary?: string;
};

export function formatElapsedSeconds(detectedAt: string) {
    if (!detectedAt) return '—';
    try {
        const detected = new Date(detectedAt).getTime();
        const now = new Date().getTime();
        const diff = Math.floor((now - detected) / 1000);
        if (diff < 0) return 'Just now';
        if (diff < 60) return `${diff}s`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m`;
        return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`;
    } catch {
        return '—';
    }
}

export function severityPill(sev: string | undefined) {
    const s = sev?.replace('_', '-').toUpperCase() || 'SEV-3';
    if (s === 'SEV-1') {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-md bg-critical/15 text-critical ring-1 ring-critical/30">
                <span className="w-1 h-1 rounded-full bg-critical" /> {s}
            </span>
        );
    }
    if (s === 'SEV-2') {
        return (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-md bg-warning/15 text-warning ring-1 ring-warning/30">
                <span className="w-1 h-1 rounded-full bg-warning" /> {s}
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-md bg-white/[0.04] text-text-muted ring-1 ring-white/[0.06]">
            {s}
        </span>
    );
}

export function statusBadge(status: string | undefined) {
    const s = status?.toUpperCase() || 'UNKNOWN';
    let cls = 'bg-white/[0.04] text-text-muted ring-white/[0.06]';
    if (s.includes('INVESTIGATING') || s.includes('TRIAGING') || s.includes('CORRELATING')) cls = 'bg-agent-active/15 text-agent-active ring-agent-active/30';
    else if (s.includes('APPROVAL') || s === 'NEEDS_REVIEW') cls = 'bg-warning/15 text-warning ring-warning/30';
    else if (s.includes('EXECUTING') || s.includes('VERIFYING')) cls = 'bg-info/15 text-info ring-info/30';
    else if (s.includes('RESOLVED')) cls = 'bg-healthy/15 text-healthy ring-healthy/30';
    return <span className={`text-[10px] font-bold px-2 py-1 rounded-md ring-1 ${cls}`}>{s.replace(/_/g, ' ')}</span>;
}

export function needsAttention(status: string | undefined) {
    const up = status?.toUpperCase() || '';
    return up.includes('APPROVAL') || up === 'NEEDS_REVIEW';
}

export function EmptyState({ icon, title, subtitle, action }: { icon: React.ReactNode; title: string; subtitle?: string; action?: React.ReactNode }) {
    return (
        <div className="h-full flex flex-col items-center justify-center text-center px-6 py-8">
            <div className="w-11 h-11 mb-3 rounded-xl bg-white/[0.03] ring-1 ring-white/[0.06] text-text-muted flex items-center justify-center">{icon}</div>
            <div className="text-sm font-medium text-text-secondary mb-1">{title}</div>
            {subtitle && <div className="text-xs text-text-muted max-w-xs leading-relaxed">{subtitle}</div>}
            {action && <div className="mt-3">{action}</div>}
        </div>
    );
}

export function LifecycleStepper({ status }: { status: string }) {
    const current = status?.toUpperCase?.() ?? '';
    const steps = [
        { key: 'DETECTED', label: 'Detected' },
        { key: 'CORRELATING', label: 'Correlating' },
        { key: 'INVESTIGATING', label: 'Investigating' },
        { key: 'PLAN_READY', label: 'Plan ready' },
        { key: 'AWAITING_APPROVAL', label: 'Approval' },
        { key: 'EXECUTING', label: 'Executing' },
        { key: 'VERIFYING', label: 'Verifying' },
        { key: 'RESOLVED', label: 'Resolved' },
    ] as const;
    const currentIdx = (() => {
        const idx = steps.findIndex((s) => s.key === current);
        if (idx >= 0) return idx;
        if (current === 'TRIAGING') return 2;
        if (current === 'NEEDS_REVIEW') return 3;
        return 0;
    })();
    return (
        <div className="w-full">
            <div className="flex items-center justify-between text-[10.5px] text-text-muted">
                {steps.map((s, idx) => {
                    const isDone = idx < currentIdx;
                    const isCurrent = idx === currentIdx;
                    const dotCls = isDone
                        ? 'bg-healthy ring-healthy/40 text-app-bg'
                        : isCurrent
                            ? 'bg-gradient-to-br from-primary to-agent-active ring-primary/40 text-white'
                            : 'bg-white/[0.03] ring-white/[0.06] text-text-muted';
                    const labelCls = isCurrent ? 'text-text-primary font-semibold' : isDone ? 'text-text-secondary' : '';
                    return (
                        <div key={s.key} className="flex-1 flex flex-col items-center relative">
                            <div className="flex items-center w-full relative z-10">
                                <div className={`h-px flex-1 ${idx === 0 ? 'invisible' : isDone || isCurrent ? 'bg-gradient-to-r from-healthy to-primary/60' : 'bg-white/[0.06]'}`} />
                                <div className={`w-5 h-5 rounded-full ring-2 flex items-center justify-center text-[9px] flex-shrink-0 ${dotCls}`}>
                                    {isDone ? '✓' : idx + 1}
                                </div>
                                <div className={`h-px flex-1 ${idx === steps.length - 1 ? 'invisible' : isDone ? 'bg-gradient-to-r from-primary/60 to-healthy' : 'bg-white/[0.06]'}`} />
                            </div>
                            <div className={`mt-2 text-center ${labelCls}`}>{s.label}</div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
