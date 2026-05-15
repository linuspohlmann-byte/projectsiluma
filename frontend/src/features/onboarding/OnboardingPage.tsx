import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { setNativeLang, setTargetLang } from '@/lib/api';
import { saveUserSettings } from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

export function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [native, setNative] = useState('de');
  const [target, setTarget] = useState('en');

  const finish = async () => {
    setNativeLang(native);
    setTargetLang(target);
    localStorage.setItem('siluma_onboarding_done', '1');
    try {
      await saveUserSettings({
        native_language: native,
        target_language: target,
        onboarding_completed: true,
      });
    } catch {
      /* local prefs still applied */
    }
    navigate('/library');
  };

  return (
    <div className="mx-auto min-h-dvh max-w-lg space-y-6 p-4">
      <div>
        <h1 className="text-2xl font-bold">{t('onboarding.title', 'Willkommen bei Polo')}</h1>
        <p className="text-sm text-[var(--muted)]">
          {t('onboarding.step', 'Schritt')} {step + 1} / 2
        </p>
      </div>

      <Card className="space-y-4">
        {step === 0 ? (
          <>
            <label className="text-sm font-medium">{t('settings.native_lang', 'Muttersprache')}</label>
            <select
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
              value={native}
              onChange={(e) => setNative(e.target.value)}
            >
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
          </>
        ) : (
          <>
            <label className="text-sm font-medium">{t('settings.target_lang', 'Zielsprache')}</label>
            <select
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="en">English</option>
              <option value="fr">Français</option>
              <option value="es">Español</option>
            </select>
          </>
        )}
        <div className="flex gap-2">
          {step > 0 && (
            <Button variant="secondary" onClick={() => setStep(0)}>
              {t('buttons.back', 'Zurück')}
            </Button>
          )}
          {step < 1 ? (
            <Button fullWidth onClick={() => setStep(1)}>
              {t('buttons.next', 'Weiter')}
            </Button>
          ) : (
            <Button fullWidth onClick={() => void finish()}>
              {t('onboarding.finish', 'Los geht\'s')}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
