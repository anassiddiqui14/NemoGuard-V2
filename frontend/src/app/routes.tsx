import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth } from './RequireAuth';
import { AppShell } from '../components/shell/AppShell';
import { LandingPage } from '../pages/LandingPage/LandingPage';
import { LoginPage } from '../pages/LoginPage/LoginPage';
import { Dashboard } from '../components/Dashboard';
import { IncidentsPage } from '../pages/IncidentsPage/IncidentsPage';
import { AgentOperationsPage } from '../pages/AgentOperationsPage/AgentOperationsPage';
import { IntelligencePage } from '../pages/IntelligencePage/IntelligencePage';
import { WhatsNewPage } from '../pages/WhatsNewPage/WhatsNewPage';
import { SettingsPage } from '../pages/SettingsPage/SettingsPage';

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
                <Route path="intelligence" element={<IntelligencePage />} />
                <Route path="whats-new" element={<WhatsNewPage />} />
                <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
