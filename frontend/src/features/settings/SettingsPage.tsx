import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useAuth } from '@/providers/AuthProvider';
import { useTheme } from '@/providers/ThemeProvider';
import {
  getAutoPlayAudio,
  getNativeLang,
  getSoundEffects,
  getTargetLang,
  setAutoPlayAudio,
  setNativeLang,
  setSoundEffects,
  setTargetLang,
} from '@/lib/api';
import {
  fetchUserSettings,
  fetchUserStats,
  resetUserProgress,
  saveUserSettings,
} from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';
import { useNavigate } from 'react-router-dom';

export function SettingsPage() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();

  const [native, setNative] = useState(getNativeLang());
  const [target, setTarget] = useState(getTargetLang());
  const [autoPlay, setAutoPlay] = useState(getAutoPlayAudio());
  const [soundFx, setSoundFx] = useState(getSoundEffects());
  const [saved, setSaved] = useState(false);

  const { data: settingsData } = useQuery({
    queryKey: ['user-settings'],
    queryFn: fetchUserSettings,
  });

  const { data: statsData, refetch: refetchStats } = useQuery({
    queryKey: ['user-stats'],
    queryFn: fetchUserStats,
  });

  useEffect(() => {
    const s = settingsData?.settings;
    if (!s) return;
    if (typeof s.native_language === 'string') {
      setNative(s.native_language);
      setNativeLang(s.native_language);
    }
    if (typeof s.target_language === 'string') {
      setTarget(s.target_language);
      setTargetLang(s.target_language);
    }
    if (typeof s.theme === 'string') setTheme(s.theme as 'light' | 'dark' | 'auto');
    if (typeof s.auto_play_audio === 'boolean') {
      setAutoPlay(s.auto_play_audio);
      setAutoPlayAudio(s.auto_play_audio);
    }
    if (typeof s.sound_enabled === 'boolean') {
      setSoundFx(s.sound_enabled);
      setSoundEffects(s.sound_enabled);
    }
  }, [settingsData, setTheme]);

  const persist = async () => {
    setNativeLang(native);
    setTargetLang(target);
    setAutoPlayAudio(autoPlay);
    setSoundEffects(soundFx);
    try {
      await saveUserSettings({
        native_language: native,
        target_language: target,
        theme,
        auto_play_audio: autoPlay,
        sound_enabled: soundFx,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      /* local prefs still applied */
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleReset = async () => {
    if (!window.confirm(t('settings.reset_confirm', 'Fortschritt wirklich zurücksetzen?'))) return;
    try {
      await resetUserProgress();
      void refetchStats();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Nicht verfügbar');
    }
  };

  const stats = statsData?.stats;

  return (
    <div className="space-y-6 pb-8 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.title', 'Einstellungen')}</h1>
        <p className="text-sm text-[var(--muted)]">{user?.username}</p>
      </div>

      <Card className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-2xl font-bold">{stats?.levels_completed ?? 0}</p>
          <p className="text-xs text-[var(--muted)]">{t('settings.levels', 'Level')}</p>
        </div>
        <div>
          <p className="text-2xl font-bold">{stats?.words_learned ?? 0}</p>
          <p className="text-xs text-[var(--muted)]">{t('settings.words', 'Wörter')}</p>
        </div>
        <div>
          <p className="text-2xl font-bold">{stats?.streak_days ?? stats?.current_streak ?? 0}</p>
          <p className="text-xs text-[var(--muted)]">{t('settings.streak', 'Streak')}</p>
        </div>
      </Card>

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
            value={native}
            onChange={(e) => setNative(e.target.value)}
          >
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label className="text-sm font-medium">{t('settings.target_lang', 'Zielsprache')}</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="en">English</option>
            <option value="fr">Français</option>
            <option value="es">Español</option>
            <option value="de">Deutsch</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoPlay} onChange={(e) => setAutoPlay(e.target.checked)} />
          {t('settings.auto_play', 'Audio automatisch abspielen')}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={soundFx} onChange={(e) => setSoundFx(e.target.checked)} />
          {t('settings.sound_effects', 'Soundeffekte')}
        </label>
        {saved && <p className="text-sm text-[var(--accent)]">{t('settings.saved', 'Gespeichert')}</p>}
        <Button fullWidth onClick={() => void persist()}>
          {t('buttons.save', 'Speichern')}
        </Button>
      </Card>

      <Button variant="secondary" fullWidth onClick={() => void handleReset()}>
        {t('settings.reset_progress', 'Fortschritt zurücksetzen')}
      </Button>

      <Button variant="danger" fullWidth onClick={() => void handleLogout()}>
        {t('auth.logout', 'Abmelden')}
      </Button>
    </div>
  );
}
