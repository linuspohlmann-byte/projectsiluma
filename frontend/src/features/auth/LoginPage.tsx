import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/providers/AuthProvider';
import { useTranslation } from '@/lib/i18n';

export function LoginPage() {
  const { user, loading, login, register } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) return <Navigate to="/library" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(username, password);
        navigate('/library');
      } else {
        await register(username, email, password);
        localStorage.removeItem('siluma_onboarding_done');
        navigate('/onboarding');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-dvh items-center justify-center bg-[var(--bg)] p-4">
      <Card className="w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold">Polo</h1>
          <p className="text-sm text-[var(--muted)]">{t('library.subtitle', 'Sprachlern-App')}</p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Input
            label={mode === 'login' ? t('auth.username_or_email', 'Benutzername oder E-Mail') : t('auth.username', 'Benutzername')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          {mode === 'register' && (
            <Input
              label={t('auth.email', 'E-Mail')}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          )}
          <Input
            label={t('auth.password', 'Passwort')}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
          />
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <Button type="submit" fullWidth disabled={submitting}>
            {mode === 'login' ? t('auth.login_submit', 'Anmelden') : t('auth.register_submit', 'Registrieren')}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-[var(--muted)]">
          {mode === 'login' ? (
            <>
              No account?{' '}
              <button type="button" className="text-[var(--accent)]" onClick={() => setMode('register')}>
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button type="button" className="text-[var(--accent)]" onClick={() => setMode('login')}>
                Login
              </button>
            </>
          )}
        </p>
        <p className="mt-2 text-center">
          <Link to="/legacy" className="text-xs text-[var(--muted)] underline">
            Legacy UI
          </Link>
        </p>
      </Card>
    </div>
  );
}
