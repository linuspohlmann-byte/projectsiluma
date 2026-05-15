import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/providers/AuthProvider';
import { fetchUserSettings } from '@/lib/learningApi';

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [onboardingResolved, setOnboardingResolved] = useState(false);

  useEffect(() => {
    if (!user) {
      setNeedsOnboarding(false);
      setOnboardingResolved(true);
      return;
    }
    if (localStorage.getItem('siluma_onboarding_done') === '1') {
      setNeedsOnboarding(false);
      setOnboardingResolved(true);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!cancelled) {
        setNeedsOnboarding(true);
        setOnboardingResolved(true);
      }
    }, 8000);

    fetchUserSettings()
      .then((res) => {
        if (cancelled) return;
        const done = Boolean(res.settings?.onboarding_completed);
        if (done) localStorage.setItem('siluma_onboarding_done', '1');
        setNeedsOnboarding(!done);
      })
      .catch(() => {
        if (!cancelled) setNeedsOnboarding(false);
      })
      .finally(() => {
        if (!cancelled) {
          window.clearTimeout(timer);
          setOnboardingResolved(true);
        }
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [user]);

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (
    onboardingResolved &&
    needsOnboarding &&
    location.pathname !== '/onboarding' &&
    !location.pathname.startsWith('/lesson') &&
    !location.pathname.startsWith('/evaluation')
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}
