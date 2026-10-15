import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth } from './RequireAuth';
import { AppShell } from '../components/shell/AppShell';
import { LandingPage } from '../pages/LandingPage/LandingPage';
import { LoginPage } from '../pages/LoginPage/LoginPage';
import { Dashboard } from '../components/Dashboard';
import { IncidentsPage } from '../pages/IncidentsPage/IncidentsPage';
import { AgentOperationsPage } from '../pages/AgentOperationsPage/AgentOperationsPage';
import { SettingsPage } from '../pages/SettingsPage/SettingsPage';

/*
 * UI MODERNIZATION (Phase 16, spec Section 61 -- route-level code
 * splitting): `vite build` was flagging the production bundle as 931KB+
 * (gzip ~268KB), explicitly listing "Using dynamic import()" as its own
 * first suggestion. The spec names Intelligence, Scenario Cockpit, and
 * Admin as good candidates for this specifically because they're
 * secondary/infrequently-visited surfaces (Admin is role-gated and most
 * users never see it at all; Scenario Cockpit is a demo/testing tool, not
 * part of daily incident-response workflow) -- lazy-loading them means a
 * typical operator session (Dashboard/Incidents/Agent Ops/Settings) never
 * pays for that code at all.
 *
 * Dashboard, Incidents, Agent Operations, and Settings stay eager since
 * they're the core, every-session pages where an extra network
 * round-trip on first navigation would be a real regression.
 */
const IntelligencePage = lazy(() => import('../pages/IntelligencePage/IntelligencePage').then((m) => ({ default: m.IntelligencePage })));
const ScenarioCockpitPage = lazy(() => import('../pages/ScenarioCockpitPage/ScenarioCockpitPage').then((m) => ({ default: m.ScenarioCockpitPage })));
const AdoptionReadinessPage = lazy(() => import('../pages/AdoptionReadinessPage/AdoptionReadinessPage').then((m) => ({ default: m.AdoptionReadinessPage })));
const AdminPage = lazy(() => import('../pages/AdminPage/AdminPage').then((m) => ({ default: m.AdminPage })));

function RouteFallback() {
    return (
        <div className="h-full flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
    );
}

export function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
                path="/app"
                element={
                    <RequireAuth>
                        <AppShell />
                    </RequireAuth>
                }
            >
                <Route index element={<Dashboard />} />
                <Route path="incidents" element={<IncidentsPage />} />
                <Route path="agent-operations" element={<AgentOperationsPage />} />
                <Route
                    path="intelligence"
                    element={
                        <Suspense fallback={<RouteFallback />}>
                            <IntelligencePage />
                        </Suspense>
                    }
                />
                <Route
                    path="scenario-cockpit"
                    element={
                        <Suspense fallback={<RouteFallback />}>
                            <ScenarioCockpitPage />
                        </Suspense>
                    }
                />
                <Route
                    path="adoption-readiness"
                    element={
                        <Suspense fallback={<RouteFallback />}>
                            <AdoptionReadinessPage />
                        </Suspense>
                    }
                />
                <Route
                    path="admin"
                    element={
                        <Suspense fallback={<RouteFallback />}>
                            <AdminPage />
                        </Suspense>
                    }
                />
                <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
