import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/providers/AuthProvider';
import { fetchUserSettings } from '@/lib/learningApi';

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    if (!user) {
      setOnboardingChecked(true);
      return;
    }
    if (localStorage.getItem('siluma_onboarding_done') === '1') {
      setNeedsOnboarding(false);
      setOnboardingChecked(true);
      return;
    }
    fetchUserSettings()
      .then((res) => {
        const done = Boolean(res.settings?.onboarding_completed);
        if (done) localStorage.setItem('siluma_onboarding_done', '1');
        setNeedsOnboarding(!done);
      })
      .catch(() => setNeedsOnboarding(false))
      .finally(() => setOnboardingChecked(true));
  }, [user]);

  if (loading || (user && !onboardingChecked)) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (
    needsOnboarding &&
    location.pathname !== '/onboarding' &&
    !location.pathname.startsWith('/lesson') &&
    !location.pathname.startsWith('/evaluation')
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
