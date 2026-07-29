import { useCallback, useEffect, useState } from 'react'
import AdminSelect from '../../../components/AdminSelect'
import {
  deleteContractTemplate,
  fetchContractTemplates,
  fetchFragmentHealth,
  fetchPayoutSettings,
  saveContractTemplate,
  updatePayoutSettings,
} from '../../../lib/adminClient'

const THRESHOLD_FIELDS = [
  ['cosignKut', 'Kut'],
  ['cosignStars', 'Stars'],
  ['cosignCrypto', 'Крипта'],
  ['cosignCard', 'Карта'],
  ['cosignOther', 'Другое'],
]

export default function PayrollSettingsTab() {
  const [settings, setSettings] = useState(null)
  const [frag, setFrag] = useState(null)
  const [templates, setTemplates] = useState([])
  const [busy, setBusy] = useState(false)
  const [tpl, setTpl] = useState({ name: '', body: '', payoutType: 'crypto' })

  const load = useCallback(async () => {
    try {
      const [s, t, f] = await Promise.all([
        fetchPayoutSettings(),
        fetchContractTemplates(),
        fetchFragmentHealth().catch(() => null),
      ])
      setSettings(s)
      setTemplates(t.items || [])
      setFrag(f || s.fragment || null)
    } catch (err) {
      alert(err?.message || 'Ошибка загрузки')
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (!settings) return <p className="sec-loading">Загрузка…</p>

  const fragDead = frag && (frag.ok === false || (frag.ok === true && frag.ton != null && frag.ton <= 0))

  return (
    <div className="sec-tab-body payroll-tab">
      <div className="payroll-hero">
        <div>
          <h3 className="payroll-hero-title">Настройки выплат</h3>
          <p className="payroll-hero-sub">Пороги cosign, Fragment и шаблоны договоров</p>
        </div>
        <div className="payroll-hero-stats">
          {fragDead && <span className="payroll-stat payroll-stat-danger">Fragment недоступен</span>}
          {!fragDead && frag?.ok && (
            <span className="payroll-stat payroll-stat-ok">
              Fragment {frag.ton != null ? `${Number(frag.ton).toFixed(2)} TON` : 'OK'}
            </span>
          )}
          {(!frag || frag.ok == null) && <span className="payroll-stat">Fragment: нет данных</span>}
        </div>
      </div>

      <section className="payroll-panel">
        <h4 className="payroll-panel-title">Со-подтверждение (второй владелец)</h4>
        <p className="staff-hint">0 = cosign отключён для способа. Иначе — при сумме ≥ порога.</p>
        <div className="payroll-fields">
          {THRESHOLD_FIELDS.map(([key, label]) => (
            <label key={key}>{label}
              <input className="sec-input" type="number" min="0" value={settings[key] ?? 0}
                onChange={(e) => setSettings((s) => ({ ...s, [key]: Number.parseInt(e.target.value, 10) || 0 }))} />
            </label>
          ))}
          <label>Stars по умолчанию
            <AdminSelect
              value={settings.defaultStarsMethod || 'auto'}
              onChange={(v) => setSettings((s) => ({ ...s, defaultStarsMethod: v }))}
              options={[
                { value: 'auto', label: 'Auto (Fragment → userbot)' },
                { value: 'fragment', label: 'Только Fragment' },
                { value: 'userbot', label: 'Только userbot' },
              ]}
            />
          </label>
        </div>
        <button type="button" className="sec-btn sec-btn-sm" style={{ marginTop: '0.75rem' }} disabled={busy}
          onClick={async () => {
            setBusy(true)
            try {
              const r = await updatePayoutSettings({
                cosignKut: settings.cosignKut,
                cosignStars: settings.cosignStars,
                cosignCrypto: settings.cosignCrypto,
                cosignCard: settings.cosignCard,
                cosignOther: settings.cosignOther,
                defaultStarsMethod: settings.defaultStarsMethod,
              })
              setSettings(r)
              alert('Сохранено')
            } catch (e) {
              alert(e?.message || 'Ошибка')
            } finally {
              setBusy(false)
            }
          }}>
          Сохранить пороги
        </button>
      </section>

      <section className="payroll-panel">
        <h4 className="payroll-panel-title">Шаблоны договоров</h4>
        <p className="staff-hint">
          Плейсхолдеры: {'{{amount}}'} {'{{name}}'} {'{{username}}'} {'{{payout_type}}'} {'{{period}}'}{' '}
          {'{{crypto_network}}'} {'{{crypto_address}}'} {'{{card_bank}}'} {'{{card_number}}'}{' '}
          {'{{card_holder}}'} {'{{card_sbp}}'} {'{{stars_username}}'}
        </p>
        <input className="sec-input" placeholder="Название" value={tpl.name}
          onChange={(e) => setTpl((t) => ({ ...t, name: e.target.value }))} />
        <AdminSelect value={tpl.payoutType} onChange={(v) => setTpl((t) => ({ ...t, payoutType: v }))}
          options={[
            { value: 'crypto', label: 'Крипта' },
            { value: 'card', label: 'Карта' },
            { value: 'other', label: 'Общий' },
          ]} />
        <textarea className="sec-input payroll-textarea" rows={7} placeholder="Текст договора…"
          value={tpl.body} onChange={(e) => setTpl((t) => ({ ...t, body: e.target.value }))} />
        <button type="button" className="sec-btn sec-btn-sm" disabled={busy || !tpl.name.trim()}
          onClick={async () => {
            setBusy(true)
            try {
              await saveContractTemplate({
                name: tpl.name.trim(), body: tpl.body, payoutType: tpl.payoutType, enabled: true,
              })
              setTpl({ name: '', body: '', payoutType: 'crypto' })
              await load()
            } catch (e) {
              alert(e?.message || 'Ошибка')
            } finally {
              setBusy(false)
            }
          }}>
          Сохранить шаблон
        </button>

        <div className="payroll-tpl-list">
          {templates.map((t) => (
            <div key={t.id} className="payroll-tpl-row">
              <div>
                <strong>{t.name}</strong>
                <span className="payroll-muted"> · {t.payoutType || 'any'}</span>
                {!t.enabled && <span className="payroll-muted"> · выкл</span>}
              </div>
              <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm"
                onClick={async () => {
                  if (!confirm('Удалить шаблон?')) return
                  try {
                    await deleteContractTemplate(t.id)
                    await load()
                  } catch (e) {
                    alert(e?.message || 'Ошибка')
                  }
                }}>
                Удалить
              </button>
            </div>
          ))}
          {templates.length === 0 && <p className="sec-empty">Шаблонов пока нет</p>}
        </div>
      </section>
    </div>
  )
}
