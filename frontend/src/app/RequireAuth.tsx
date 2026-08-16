import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthGate, acquireDemoToken } from '../contexts/AuthGateContext';

export function RequireAuth({ children }: { children: React.ReactNode }) {
    const { devLoginEnabled, loading: authGateLoading } = useAuthGate();
    const [ready, setReady] = useState(false);
    const [hasToken, setHasToken] = useState<boolean>(() => !!localStorage.getItem('nemoguard_token'));

    useEffect(() => {
        if (authGateLoading) return;

        if (hasToken) {
            setReady(true);
            return;
        }

        if (devLoginEnabled) {
            // Only in a development deployment: silently acquire a token so
            // backend calls still work without forcing the developer through
            // the login screen on every reload. In production this branch is
            // never taken -- devLoginEnabled is only true when the API's ENV
            // is development/dev/local.
            void acquireDemoToken().then((token) => {
                setHasToken(!!token);
                setReady(true);
            });
        } else {
            setReady(true);
        }
    }, [devLoginEnabled, authGateLoading, hasToken]);

    if (!ready || authGateLoading) return null;

    if (!hasToken) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
}
