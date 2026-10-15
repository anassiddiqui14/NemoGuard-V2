import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
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
  // UI MODERNIZATION (Phase 6, spec Section 31/62): a failed poll
  // previously wiped BOTH incident arrays to empty in the catch block --
  // identical in appearance to the legitimate "zero active incidents"
  // empty state. An operator whose network blipped mid-incident would see
  // the entire queue vanish and have no way to tell "the system is
  // actually healthy and quiet" apart from "the dashboard just lost its
  // connection to the API". Now a failed refresh keeps the last-known-good
  // data on screen and surfaces a dedicated, dismissable connection-error
  // banner instead of silently discarding state.
  const [queueError, setQueueError] = useState<string | null>(null);

  const refreshQueue = async () => {
    try {
      const [openRes, allRes] = await Promise.all([
        authFetch('/api/v2/incidents?state=open'),
        authFetch('/api/v2/incidents?state=all'),
      ]);
      if (!openRes.ok || !allRes.ok) throw new Error(`HTTP ${openRes.status}/${allRes.status}`);
      const openData = (await openRes.json()) as IncidentSummary[];
      const allData = (await allRes.json()) as IncidentSummary[];
      setOpenIncidents(Array.isArray(openData) ? openData : []);
      setResolvedIncidents(
        Array.isArray(allData) ? allData.filter((i) => i.status?.toUpperCase() === 'RESOLVED') : [],
      );
      setQueueError(null);
    } catch {
      // Deliberately do NOT clear openIncidents/resolvedIncidents here --
      // stale-but-real data is far more useful to an operator than an
      // empty queue that looks like "all clear".
      setQueueError('Lost connection to the incident feed. Showing last known data.');
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
      {/*
       * UI MODERNIZATION (spec Section 30 -- Dashboard responsive
       * behavior): IncidentQueue has a fixed w-[300px], and this
       * container had no responsive handling at all -- at a 375px
       * mobile viewport that left only ~75px for the entire main
       * content area, which the spec explicitly calls unacceptable
       * ("Do not squeeze 3 columns... use sequential visual states:
       * Incident Queue -> Incident Detail"). Below md, the queue and
       * detail pane now behave like the IncidentsPage's existing
       * list/detail pattern: show the queue OR the detail, never a
       * squeezed version of both, with the queue reappearing once no
       * incident is selected.
       */}
      <div className={`${activeIncidentId ? 'hidden md:flex' : 'flex'} md:flex-shrink-0`}>
        <IncidentQueue
          openIncidents={sortedIncidents}
          activeIncidentId={activeIncidentId}
          setActiveIncidentId={setActiveIncidentId}
          refreshQueue={refreshQueue}
          connectionError={queueError}
        />
      </div>

      <motion.main
        key={activeIncidentId ?? 'no-incident'}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={`flex-1 overflow-y-auto flex-col gap-4 min-w-0 ${activeIncidentId ? 'flex' : 'hidden md:flex'}`}
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
            // Mobile-only "back to queue" -- on desktop (md+) the queue
            // is always visible alongside the detail pane, so a visible
            // back button there would be redundant.
            onBack={() => setActiveIncidentId(null)}
            backButtonMobileOnly
          />
        </div>
      </motion.main>
    </div>
  );
}
