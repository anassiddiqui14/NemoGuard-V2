import { useEffect, useState } from 'react';
import { authFetch } from '../contexts/AuthGateContext';

export interface NotificationItem {
    id: string;
    incident_id: string;
    title: string;
    kind: 'sla_risk' | 'needs_review' | 'plan_ready';
    detail: string;
    severity: string;
}

export function useNotifications() {
    const [notifications, setNotifications] = useState<NotificationItem[]>([]);

    useEffect(() => {
        let cancelled = false;

        const poll = async () => {
            try {
                const res = await authFetch('/api/v2/incidents?state=open');
                const incidents = await res.json();
                if (!Array.isArray(incidents) || cancelled) return;

                const next: NotificationItem[] = [];
                const now = Date.now();

                for (const inc of incidents) {
                    const status = (inc.status || '').toUpperCase();

                    if (inc.next_sla_breach_at) {
                        const breachMs = new Date(inc.next_sla_breach_at).getTime();
                        const minsLeft = Math.round((breachMs - now) / 60000);
                        if (minsLeft <= 10 && minsLeft > -60) {
                            next.push({
                                id: `${inc.incident_id}-sla`,
                                incident_id: inc.incident_id,
                                title: inc.title,
                                kind: 'sla_risk',
                                detail: minsLeft > 0 ? `SLA breach in ${minsLeft}m` : `SLA breached ${Math.abs(minsLeft)}m ago`,
                                severity: inc.severity,
                            });
                        }
                    }

                    if (status === 'PLAN_READY') {
                        next.push({
                            id: `${inc.incident_id}-plan`,
                            incident_id: inc.incident_id,
                            title: inc.title,
                            kind: 'plan_ready',
                            detail: 'Recovery plan awaiting your review',
                            severity: inc.severity,
                        });
                    }
                }

                setNotifications(next);
            } catch {
                // ignore transient network errors
            }
        };

        void poll();
        const t = window.setInterval(poll, 5000);
        return () => {
            cancelled = true;
            window.clearInterval(t);
        };
    }, []);

    return notifications;
}
