import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { IncidentQueue } from './dashboard/IncidentQueue';
import { IncidentWorkspace } from './dashboard/IncidentWorkspace';
import { GreetingBar } from './shell/GreetingBar';
import type { IncidentSummary } from './dashboard/shared';
import { needsAttention } from './dashboard/shared';
import { authFetch } from '../contexts/AuthGateContext';

export function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const focusIncidentId = searchParams.get('incident');
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);
  const [openIncidents, setOpenIncidents] = useState<IncidentSummary[]>([]);
  const [resolvedIncidents, setResolvedIncidents] = useState<IncidentSummary[]>([]);
  // Tracks whether the incident queue has completed its FIRST fetch. Without
  // this, navigating here with a specific incident already selected (e.g.
  // from the Incidents page or a notification) raced against the initial
  // refreshQueue() call: openIncidents/resolvedIncidents both start as `[]`,
  // so the "does the active incident still exist" check below would run
  // against two empty arrays on mount and immediately null out the
  // just-selected incident before the real data ever arrived.
  const [queueLoaded, setQueueLoaded] = useState(false);

  const refreshQueue = async () => {
    try {
      const [openRes, allRes] = await Promise.all([
        authFetch('/api/v2/incidents?state=open'),
        authFetch('/api/v2/incidents?state=all'),
      ]);
      const openData = (await openRes.json()) as IncidentSummary[];
      const allData = (await allRes.json()) as IncidentSummary[];
      setOpenIncidents(Array.isArray(openData) ? openData : []);
      setResolvedIncidents(
        Array.isArray(allData) ? allData.filter((i) => i.status?.toUpperCase() === 'RESOLVED') : [],
      );
    } catch {
      setOpenIncidents([]);
      setResolvedIncidents([]);
    } finally {
      setQueueLoaded(true);
    }
  };

  // An incident selected from the queue can now come from either the active
  // (open) list or the resolved list — previously this only looked at
  // openIncidents, so clicking a resolved incident would render nothing.
  const selectedIncident = useMemo(
    () =>
      openIncidents.find((i) => i.incident_id === activeIncidentId) ??
      resolvedIncidents.find((i) => i.incident_id === activeIncidentId) ??
      null,
    [openIncidents, resolvedIncidents, activeIncidentId],
  );

  useEffect(() => {
    void refreshQueue();
    const t = window.setInterval(() => void refreshQueue(), 2000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    if (focusIncidentId) {
      setActiveIncidentId(focusIncidentId);
      // Clear the query param once handled so subsequent queue navigation
      // isn't overridden by a stale ?incident= value on every re-render.
      searchParams.delete('incident');
      setSearchParams(searchParams, { replace: true });
    }
  }, [focusIncidentId]);

  useEffect(() => {
    // Wait for the FIRST successful queue fetch before doing any
    // auto-correction. Previously this ran immediately on mount against two
    // still-empty arrays, which meant navigating in with a specific incident
    // pre-selected (e.g. clicking a row on the Incidents page, which sets
    // ?incident=... and this component's activeIncidentId) got wiped back to
    // null on the very next render, before the real queue data had a chance
    // to arrive — making it look like clicking an incident "did nothing" and
    // dumped the user back on an empty dashboard.
    if (!queueLoaded) return;

    // Only auto-correct the selection when the active incident no longer exists
    // in EITHER the open or resolved lists — previously this only checked
    // openIncidents, so selecting a resolved incident from the queue would
    // immediately get snapped back to openIncidents[0] on the very next
    // refresh tick, making resolved incidents impossible to actually view.
    const activeExistsSomewhere =
      !!activeIncidentId &&
      (openIncidents.some((i) => i.incident_id === activeIncidentId) ||
        resolvedIncidents.some((i) => i.incident_id === activeIncidentId));

    if (!activeIncidentId && openIncidents.length > 0) {
      setActiveIncidentId(openIncidents[0].incident_id);
    } else if (activeIncidentId && !activeExistsSomewhere) {
      setActiveIncidentId(openIncidents.length > 0 ? openIncidents[0].incident_id : null);
    }
  }, [activeIncidentId, openIncidents, resolvedIncidents, queueLoaded]);

  const sortedIncidents = useMemo(() => {
    return [...openIncidents].sort((a, b) => {
      const aAttn = needsAttention(a.status) ? 0 : 1;
      const bAttn = needsAttention(b.status) ? 0 : 1;
      return aAttn - bAttn;
    });
  }, [openIncidents]);

  return (
    <div className="flex h-full min-h-0 bg-app-bg text-text-primary overflow-hidden selection:bg-primary/30">
      <Toaster position="top-right" />

      <IncidentQueue
        openIncidents={sortedIncidents}
        activeIncidentId={activeIncidentId}
        setActiveIncidentId={setActiveIncidentId}
        refreshQueue={refreshQueue}
      />

      <motion.main
        key={activeIncidentId ?? 'no-incident'}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className="flex-1 overflow-y-auto flex flex-col gap-4 min-w-0"
      >
        <GreetingBar
          activeCount={openIncidents.length}
          approvalCount={openIncidents.filter((i) => needsAttention(i.status)).length}
        />

        <div className="px-5 pb-5 flex flex-col gap-4">
          <IncidentWorkspace
            incidentId={activeIncidentId}
            selectedIncident={selectedIncident}
            onRefreshParent={refreshQueue}
          />
        </div>
      </motion.main>
    </div>
  );
}
