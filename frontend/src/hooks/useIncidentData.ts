import { useState, useEffect } from 'react';

export function useIncidentData(incidentId: string | null) {
  const [evidence, setEvidence] = useState<any[]>([]);
  const [hypothesis, setHypothesis] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [impact, setImpact] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!incidentId) {
      setEvidence([]);
      setHypothesis(null);
      setPlan(null);
      setImpact([]);
      setAlerts([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const load = async () => {
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
        if (Array.isArray(hypData) && hypData.length > 0) {
          const rawHyp = hypData[0];
          setHypothesis({
            ...rawHyp,
            title: rawHyp.title || rawHyp.statement || 'Identified Root Cause',
            confidence_score: rawHyp.confidence_score ?? rawHyp.confidence ?? 0,
          });
        }
        if (Array.isArray(planData) && planData.length > 0) {
          setPlan(planData[0]);
          if (planData[0].status === 'APPROVED' || planData[0].status === 'EXECUTED') {
            setLoading(false);
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    setLoading(true);
    void load();
    const interval = window.setInterval(() => void load(), 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [incidentId]);

  return { evidence, hypothesis, plan, impact, alerts, loading };
}
