import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/providers/AuthProvider';
import { useTheme } from '@/providers/ThemeProvider';
import { setNativeLang, setTargetLang } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';
import { useNavigate } from 'react-router-dom';

export function SettingsPage() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.title', 'Einstellungen')}</h1>
        <p className="text-sm text-[var(--muted)]">{user?.username}</p>
      </div>

      <Card className="space-y-4">
        <div>
          <label className="text-sm font-medium">{t('settings.theme', 'Design')}</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            value={theme}
            onChange={(e) => setTheme(e.target.value as 'light' | 'dark' | 'auto')}
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="auto">Auto</option>
          </select>
        </div>
        <div>
          <label className="text-sm font-medium">{t('settings.native_lang', 'Muttersprache')}</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            defaultValue="de"
            onChange={(e) => setNativeLang(e.target.value)}
          >
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label className="text-sm font-medium">{t('settings.target_lang', 'Zielsprache')}</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            defaultValue="en"
            onChange={(e) => setTargetLang(e.target.value)}
          >
            <option value="en">English</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
          </select>
        </div>
      </Card>

      <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
        {t('auth.logout', 'Abmelden')}
      </Button>
    </div>
  );
}
