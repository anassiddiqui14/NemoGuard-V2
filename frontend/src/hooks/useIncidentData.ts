import { useState, useEffect } from 'react';

export function useIncidentData(incidentId: string | null) {
  const [evidence, setEvidence] = useState<any[]>([]);
  const [hypothesis, setHypothesis] = useState<any>(null);
  // Full ranked hypothesis ledger (spec §10.1) -- previously the RCA agent's
  // competing hypotheses (each with its own confidence + supporting/
  // contradicting evidence) were silently collapsed down to just
  // hypData[0], discarding every alternative the agent actually considered
  // and ranked. `hypotheses` now exposes the complete ordered list so the
  // UI can show operators the full reasoning, not just the top pick.
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  const [plan, setPlan] = useState<any>(null);
  const [impact, setImpact] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Reset ALL state whenever the selected incident changes (including switching
    // between two non-null incidents) — not just when deselecting entirely.
    // Previously this only reset on `!incidentId`, and worse, setHypothesis/setPlan
    // below were only called when the fetched array was non-empty. That meant
    // switching to an incident with no plan/hypothesis yet silently kept showing
    // the PREVIOUS incident's plan/hypothesis in the RecoveryRail — looking like
    // the dashboard was "stuck" on the old incident.
    setEvidence([]);
    setHypothesis(null);
    setHypotheses([]);
    setPlan(null);
    setImpact([]);
    setAlerts([]);

    if (!incidentId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const [evRes, hypRes, planRes, impactRes, alertsRes] = await Promise.all([
          fetch(`/api/v2/incidents/${incidentId}/evidence`),
          fetch(`/api/v2/incidents/${incidentId}/hypotheses`),
          fetch(`/api/v2/incidents/${incidentId}/plans`),
          fetch(`/api/v2/incidents/${incidentId}/impact`),
          fetch(`/api/v2/incidents/${incidentId}/alerts`)
        ]);

        const evData = await evRes.json();
        const hypData = await hypRes.json();
        const planData = await planRes.json();
        const impactData = await impactRes.json();
        const alertsData = await alertsRes.json();

        if (cancelled) return;

        if (Array.isArray(evData)) setEvidence(evData);
        if (Array.isArray(impactData)) setImpact(impactData);
        if (Array.isArray(alertsData)) setAlerts(alertsData);

        // Always reflect the current fetch result, including the empty case —
        // otherwise stale data from a previously selected incident persists.
        if (Array.isArray(hypData) && hypData.length > 0) {
          // API already orders by confidence DESC (see /hypotheses endpoint),
          // so hypData[0] is the primary hypothesis and the rest are the
          // ranked alternatives the RCA agent considered and ruled down.
          const normalized = hypData.map((h: any) => ({
            ...h,
            title: h.title || h.statement || 'Identified Root Cause',
            confidence_score: h.confidence_score ?? h.confidence ?? 0,
          }));
          setHypothesis(normalized[0]);
          setHypotheses(normalized);
        } else {
          setHypothesis(null);
          setHypotheses([]);
        }

        if (Array.isArray(planData) && planData.length > 0) {
          setPlan(planData[0]);
          if (planData[0].status === 'APPROVED' || planData[0].status === 'EXECUTED') {
            setLoading(false);
          }
        } else {
          setPlan(null);
        }
      } catch (e) {
        console.error(e);
      }
    };

    // Fetch immediately on incident switch instead of waiting for the first
    // 2s interval tick, so the panel updates right away rather than briefly
    // showing stale/empty data.
    void fetchOnce();
    const interval = setInterval(fetchOnce, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [incidentId]);

  return { evidence, hypothesis, hypotheses, plan, impact, alerts, loading };
}
