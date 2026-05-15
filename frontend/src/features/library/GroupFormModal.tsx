import { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { getNativeLang, getTargetLang } from '@/lib/api';
import {
  createCustomGroup,
  fetchCustomGroup,
  updateCustomGroup,
} from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

const CEFR = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

export function CreateGroupModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (groupId: number, publishAfter?: boolean) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [context, setContext] = useState('');
  const [cefr, setCefr] = useState('A1');
  const [publishAfter, setPublishAfter] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim() || !context.trim()) {
      setError(t('groups.required', 'Bitte alle Pflichtfelder ausfüllen.'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      const res = await createCustomGroup({
        group_name: name.trim(),
        context_description: context.trim(),
        language: getTargetLang(),
        native_language: getNativeLang(),
        cefr_level: cefr,
      });
      if (!res.success || !res.group_id) throw new Error(res.error || 'Create failed');
      onCreated(res.group_id, publishAfter);
      setName('');
      setContext('');
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t('groups.create', 'Level-Gruppe erstellen')}>
      <div className="space-y-4">
        <Input label={t('groups.name', 'Titel')} value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <label className="text-sm font-medium">{t('groups.context', 'Kontext / Story')}</label>
          <textarea
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
            rows={4}
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium">CEFR</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            value={cefr}
            onChange={(e) => setCefr(e.target.value)}
          >
            {CEFR.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={publishAfter}
            onChange={(e) => setPublishAfter(e.target.checked)}
          />
          {t('groups.publish_after', 'Nach Erstellung im Marktplatz veröffentlichen')}
        </label>
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        <Button fullWidth disabled={saving} onClick={() => void submit()}>
          {saving ? '…' : t('buttons.create', 'Erstellen')}
        </Button>
      </div>
    </Modal>
  );
}

export function EditGroupModal({
  groupId,
  open,
  onClose,
  onUpdated,
}: {
  groupId: number;
  open: boolean;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [context, setContext] = useState('');
  const [cefr, setCefr] = useState('A1');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !groupId) return;
    fetchCustomGroup(groupId)
      .then((res) => {
        const g = res.group;
        if (!g) return;
        setName(g.group_name || '');
        setContext(g.context_description || '');
        setCefr(g.cefr_level || 'A1');
      })
      .catch(() => {});
  }, [open, groupId]);

  const submit = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await updateCustomGroup(groupId, {
        group_name: name.trim(),
        context_description: context.trim(),
        cefr_level: cefr,
      });
      if (!res.success) throw new Error(res.error || 'Update failed');
      onUpdated();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t('groups.edit', 'Gruppe bearbeiten')}>
      <div className="space-y-4">
        <Input label={t('groups.name', 'Titel')} value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <label className="text-sm font-medium">{t('groups.context', 'Kontext')}</label>
          <textarea
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
            rows={4}
            value={context}
            onChange={(e) => setContext(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium">CEFR</label>
          <select
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            value={cefr}
            onChange={(e) => setCefr(e.target.value)}
          >
            {CEFR.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
        <Button fullWidth disabled={saving} onClick={() => void submit()}>
          {saving ? '…' : t('buttons.save', 'Speichern')}
        </Button>
      </div>
    </Modal>
  );
}
