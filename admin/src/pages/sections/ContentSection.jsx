import { useCallback, useEffect, useMemo, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import AdminSelect from '../../components/AdminSelect'
import CraftRecipeWizard from '../../components/CraftRecipeWizard'
import DexItemSearchPicker from '../../components/DexItemSearchPicker'
import {
  createContentCraft,
  createContentCrop,
  createContentDexItem,
  createContentQuest,
  deleteContentCraft,
  deleteContentCrop,
  deleteContentDexItem,
  deleteContentQuest,
  fetchContentDex,
  fetchContentOverview,
  fetchDexItemFull,
  patchContentCraft,
  patchContentCrop,
  patchContentDexItem,
  patchContentQuest,
  updateDexItemFull,
} from '../../lib/adminClient'
import { parseRequiredIntFields } from '../../lib/formNumbers'
import { notifyAdmin } from '../../lib/notify'

// ---- Dex Item Preview ----
function DexItemPreview({ item }) {
  if (!item || !item.name) return null
  return (
    <div className="dex-preview">
      <div className="dex-preview-badge">Предпросмотр</div>
      <div className="dex-preview-card">
        <div className="dex-preview-emoji">{item.emoji || '📦'}</div>
        <div className="dex-preview-info">
          <div className="dex-preview-name">{item.name}</div>
          {item.name1 && <div className="dex-preview-name1">{item.name1}</div>}
          {item.bio && <div className="dex-preview-bio">{item.bio}</div>}
          <div className="dex-preview-meta-row">
            <span className="dex-preview-price">💰 {Number(item.price || 0).toLocaleString('ru-RU')} КУТ</span>
            {item.sorting && <span className="dex-preview-sorting">🏷 {item.sorting}</span>}
          </div>
          {item.use && <div className="dex-preview-field"><b>Использование:</b> {item.use}</div>}
          {item.bonus && <div className="dex-preview-field"><b>Бонус:</b> {item.bonus}</div>}
          {item.craft && <div className="dex-preview-field"><b>Крафт:</b> {item.craft}</div>}
        </div>
      </div>
    </div>
  )
}

const TABS = [
  { id: 'items', label: 'Предметы' },
  { id: 'crops', label: 'Культуры' },
  { id: 'craft', label: 'Крафт' },
  { id: 'quests', label: 'Задания' },
]

const EMPTY_DROP = { itemId: '', minAmount: '1', maxAmount: '1', chancePercent: '100' }
const EMPTY_QUEST_REWARD = { kind: 'kut', amount: '10', itemId: '' }

function formatSec(sec) {
  const m = Math.floor(Number(sec) / 60)
  const s = Number(sec) % 60
  return s ? `${m}м ${s}с` : `${m}м`
}

function ItemOption({ item }) {
  if (!item) return '-'
  return `${item.emoji || '📦'} ${item.name} (#${item.id})`
}

export default function ContentSection() {
  const [tab, setTab] = useState('crops')
  const [overview, setOverview] = useState(null)
  const [dexItems, setDexItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [dexQuery, setDexQuery] = useState('')
  const EMPTY_DEX_ITEM = { name: '', emoji: '📦', name1: '', price: '0', dis: '0', remains: '0', sorting: '', bio: '', use: '', bonus: '', craft: '' }
  const [newItem, setNewItem] = useState(EMPTY_DEX_ITEM)
  const [creatingItem, setCreatingItem] = useState(false)
  const [editingDexItem, setEditingDexItem] = useState(null)
  const [savingDexItem, setSavingDexItem] = useState(false)
  const [deleteDexTarget, setDeleteDexTarget] = useState(null)
  const [showDexPreview, setShowDexPreview] = useState(false)

  const [cropForm, setCropForm] = useState(null)
  const [savingCrop, setSavingCrop] = useState(false)
  const [deleteCropTarget, setDeleteCropTarget] = useState(null)

  const [craftForm, setCraftForm] = useState(null)
  const [craftStep, setCraftStep] = useState(1)
  const [savingCraft, setSavingCraft] = useState(false)
  const [deleteCraftTarget, setDeleteCraftTarget] = useState(null)

  const [questForm, setQuestForm] = useState(null)
  const [savingQuest, setSavingQuest] = useState(false)
  const [deleteQuestTarget, setDeleteQuestTarget] = useState(null)

  const loadDex = useCallback(async (q = '') => {
    const data = await fetchContentDex({ q, limit: 100 })
    setDexItems(data.items || [])
    return data.items || []
  }, [])

  const loadAll = useCallback(async () => {
    setError('')
    try {
      const [data] = await Promise.all([fetchContentOverview(), loadDex('')])
      setOverview(data)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить контент')
    } finally {
      setLoading(false)
    }
  }, [loadDex])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const handleDexSearch = async () => {
    try {
      await loadDex(dexQuery.trim())
    } catch (err) {
      notifyAdmin(err.message || 'Ошибка поиска', { error: true })
    }
  }

  const handleCreateItem = async () => {
    setCreatingItem(true)
    setError('')
    try {
      const payload = parseRequiredIntFields(
        { price: newItem.price, remains: newItem.remains },
        { price: 'Цена', remains: 'Остаток' },
      )
      if (!newItem.name.trim()) throw new Error('Укажите название предмета')
      const created = await createContentDexItem({
        name: newItem.name.trim(),
        emoji: newItem.emoji.trim() || '📦',
        name1: newItem.name1.trim(),
        price: payload.price,
        dis: parseInt(newItem.dis || '0', 10) || 0,
        remains: payload.remains,
        sorting: newItem.sorting.trim() || null,
        bio: newItem.bio.trim(),
        use: newItem.use.trim(),
        bonus: newItem.bonus.trim(),
        craft: newItem.craft.trim(),
      })
      notifyAdmin(`Предмет «${created.name}» создан (#${created.id})`)
      setNewItem(EMPTY_DEX_ITEM)
      await loadAll()
    } catch (err) {
      const message = err.message || 'Ошибка создания'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setCreatingItem(false)
    }
  }

  const openEditDexItem = async (itemId) => {
    try {
      const full = await fetchDexItemFull(itemId)
      setEditingDexItem({
        ...full,
        price: String(full.price),
        dis: String(full.dis),
        remains: String(full.remains),
      })
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка загрузки', { error: true })
    }
  }

  const handleSaveDexItem = async () => {
    if (!editingDexItem) return
    setSavingDexItem(true)
    try {
      const updated = await updateDexItemFull(editingDexItem.id, {
        name: editingDexItem.name.trim(),
        emoji: editingDexItem.emoji.trim() || '📦',
        name1: (editingDexItem.name1 || '').trim(),
        price: parseInt(editingDexItem.price || '0', 10) || 0,
        dis: parseInt(editingDexItem.dis || '0', 10) || 0,
        remains: parseInt(editingDexItem.remains || '0', 10) || 0,
        sorting: (editingDexItem.sorting || '').trim() || null,
        bio: (editingDexItem.bio || '').trim(),
        use: (editingDexItem.use || '').trim(),
        bonus: (editingDexItem.bonus || '').trim(),
        craft: (editingDexItem.craft || '').trim(),
      })
      notifyAdmin(`Предмет «${updated.name}» обновлён`)
      setEditingDexItem(null)
      await loadDex(dexQuery)
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка сохранения', { error: true })
    } finally {
      setSavingDexItem(false)
    }
  }

  const handleDeleteDexItem = async () => {
    if (!deleteDexTarget) return
    try {
      const result = await deleteContentDexItem(deleteDexTarget.id)
      notifyAdmin(`Предмет «${result.name}» удалён`)
      setDeleteDexTarget(null)
      await loadAll()
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка удаления', { error: true })
    }
  }

  const openNewCrop = () => {
    setCropForm({
      mode: 'create',
      id: null,
      key: '',
      displayName: '',
      seedItemId: '',
      growSeconds: '600',
      harvestToolItemId: '',
      harvestToolCost: '1',
      waterItemId: '',
      waterCostPerUse: '',
      spriteKey: 'generic',
      enabled: true,
      harvestDrops: [{ ...EMPTY_DROP }],
    })
  }

  const openEditCrop = (crop) => {
    setCropForm({
      mode: 'edit',
      id: crop.id,
      key: crop.key,
      displayName: crop.displayName || '',
      seedItemId: crop.seedItemId || '',
      growSeconds: String(crop.growSeconds ?? ''),
      harvestToolItemId: crop.harvestToolItemId || '',
      harvestToolCost: String(crop.harvestToolCost ?? 1),
      waterItemId: crop.waterItemId || '',
      waterCostPerUse: crop.waterCostPerUse != null ? String(crop.waterCostPerUse) : '',
      spriteKey: crop.spriteKey || 'generic',
      enabled: crop.enabled !== false,
      harvestDrops: (crop.harvestDrops?.length ? crop.harvestDrops : [{ itemId: '' }]).map((d) => ({
        itemId: d.itemId || '',
        minAmount: String(d.minAmount ?? 1),
        maxAmount: String(d.maxAmount ?? 1),
        chancePercent: String(d.chancePercent ?? 100),
      })),
    })
  }

  const saveCrop = async () => {
    if (!cropForm) return
    setSavingCrop(true)
    setError('')
    try {
      const growParsed = parseRequiredIntFields(
        { growSeconds: cropForm.growSeconds, harvestToolCost: cropForm.harvestToolCost || '1' },
        { growSeconds: 'Время роста', harvestToolCost: 'Расход инструмента' },
      )
      const drops = cropForm.harvestDrops.map((drop, idx) => {
        if (!drop.itemId) throw new Error(`Дроп #${idx + 1}: выберите предмет`)
        const parsed = parseRequiredIntFields(
          {
            minAmount: drop.minAmount,
            maxAmount: drop.maxAmount,
            chancePercent: drop.chancePercent,
          },
          {
            minAmount: `Дроп #${idx + 1} мин.`,
            maxAmount: `Дроп #${idx + 1} макс.`,
            chancePercent: `Дроп #${idx + 1} шанс %`,
          },
        )
        return {
          itemId: drop.itemId,
          minAmount: parsed.minAmount,
          maxAmount: parsed.maxAmount,
          chancePercent: parsed.chancePercent,
        }
      })

      const basePayload = {
        displayName: cropForm.displayName.trim() || cropForm.key,
        seedItemId: cropForm.seedItemId,
        growSeconds: growParsed.growSeconds,
        harvestToolItemId: cropForm.harvestToolItemId || null,
        harvestToolCost: growParsed.harvestToolCost,
        waterItemId: cropForm.waterItemId || null,
        waterCostPerUse: cropForm.waterCostPerUse ? Number(cropForm.waterCostPerUse) : null,
        spriteKey: cropForm.spriteKey,
        enabled: cropForm.enabled,
        harvestDrops: drops,
      }

      if (!basePayload.seedItemId) {
        throw new Error('Выберите саженец (seed)')
      }
      if (basePayload.waterItemId && !basePayload.waterCostPerUse) {
        throw new Error('Укажите расход предмета для полива')
      }

      if (cropForm.mode === 'create') {
        if (!/^[a-z][a-z0-9_]{1,48}$/.test(cropForm.key.trim())) {
          throw new Error('Ключ: латиница, цифры, _, от 2 символов')
        }
        await createContentCrop({ ...basePayload, key: cropForm.key.trim() })
        notifyAdmin('Культура создана')
      } else {
        await patchContentCrop(cropForm.id, {
          ...basePayload,
          clearHarvestTool: !cropForm.harvestToolItemId,
          clearWaterItem: !cropForm.waterItemId,
        })
        notifyAdmin('Культура сохранена')
      }
      setCropForm(null)
      await loadAll()
    } catch (err) {
      const message = err.message || 'Ошибка сохранения культуры'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setSavingCrop(false)
    }
  }

  const confirmDeleteCrop = async () => {
    if (!deleteCropTarget) return
    try {
      await deleteContentCrop(deleteCropTarget.id)
      notifyAdmin(`Культура «${deleteCropTarget.key}» удалена`)
      setDeleteCropTarget(null)
      await loadAll()
    } catch (err) {
      notifyAdmin(err.message || 'Ошибка удаления', { error: true })
    }
  }

  const openNewCraft = () => {
    setCraftStep(1)
    setCraftForm({
      mode: 'create',
      id: null,
      key: '',
      displayName: '',
      resultItemId: '',
      ingredientAId: '',
      ingredientBId: '',
      successPercent: '100',
      enabled: true,
      remains: 0,
      resultQty: 1,
    })
  }

  const openEditCraft = (recipe) => {
    setCraftStep(1)
    setCraftForm({
      mode: 'edit',
      id: recipe.id,
      key: recipe.key,
      displayName: recipe.displayName || '',
      resultItemId: recipe.resultItemId,
      ingredientAId: recipe.ingredientAId,
      ingredientBId: recipe.ingredientBId,
      successPercent: String(recipe.successPercent ?? 100),
      enabled: recipe.enabled !== false,
      remains: recipe.remains ?? 0,
      resultQty: recipe.resultQty ?? 1,
    })
  }

  const createDexItemForCraft = async ({ name, emoji }) => {
    const created = await createContentDexItem({
      name,
      emoji,
      price: 0,
      remains: 0,
    })
    notifyAdmin(`Предмет «${created.name}» создан (#${created.id})`)
    await loadDex('')
    return created
  }

  const saveCraft = async () => {
    if (!craftForm) return
    setSavingCraft(true)
    try {
      const parsed = parseRequiredIntFields(
        { successPercent: craftForm.successPercent },
        { successPercent: 'Шанс успеха' },
      )
      const payload = {
        displayName: craftForm.displayName.trim() || craftForm.key,
        resultItemId: craftForm.resultItemId,
        ingredientAId: craftForm.ingredientAId,
        ingredientBId: craftForm.ingredientBId,
        successPercent: parsed.successPercent,
        enabled: craftForm.enabled,
        remains: Math.max(0, parseInt(craftForm.remains ?? 0, 10) || 0),
        resultQty: Math.max(1, parseInt(craftForm.resultQty ?? 1, 10) || 1),
      }
      if (!craftForm.resultItemId || !craftForm.ingredientAId || !craftForm.ingredientBId) {
        throw new Error('Выберите все три предмета')
      }
      if (craftForm.ingredientAId === craftForm.ingredientBId) {
        throw new Error('Ингредиенты A и B должны быть разными')
      }
      if (craftForm.mode === 'create') {
        if (!/^[a-z][a-z0-9_]{1,48}$/.test(craftForm.key.trim())) {
          throw new Error('Ключ рецепта: латиница, цифры, _')
        }
        await createContentCraft({ ...payload, key: craftForm.key.trim() })
        notifyAdmin('Крафт создан')
      } else {
        await patchContentCraft(craftForm.id, payload)
        notifyAdmin('Крафт сохранён')
      }
      setCraftForm(null)
      setCraftStep(1)
      await loadAll()
    } catch (err) {
      notifyAdmin(err.message || 'Ошибка крафта', { error: true })
    } finally {
      setSavingCraft(false)
    }
  }

  const confirmDeleteCraft = async () => {
    if (!deleteCraftTarget) return
    try {
      await deleteContentCraft(deleteCraftTarget.id)
      notifyAdmin('Рецепт удалён')
      setDeleteCraftTarget(null)
      await loadAll()
    } catch (err) {
      notifyAdmin(err.message || 'Ошибка', { error: true })
    }
  }

  const openNewQuest = () => {
    setQuestForm({
      mode: 'create',
      id: null,
      key: '',
      period: 'daily',
      action: 'harvest',
      target: '1',
      title: '',
      description: '',
      emoji: '📋',
      enabled: true,
      targetScope: 'any',
      targetCropKey: '',
      targetItemId: '',
      rewards: [{ ...EMPTY_QUEST_REWARD }],
    })
  }

  const openEditQuest = (quest) => {
    setQuestForm({
      mode: 'edit',
      id: quest.id,
      key: quest.key,
      period: quest.period,
      action: quest.action,
      target: String(quest.target ?? 1),
      title: quest.title || '',
      description: quest.description || '',
      emoji: quest.emoji || '📋',
      enabled: quest.enabled !== false,
      targetScope: quest.targetScope || 'any',
      targetCropKey: quest.targetCropKey || '',
      targetItemId: quest.targetItemId || '',
      rewards: (quest.rewards?.length ? quest.rewards : [{ kind: 'kut', amount: 1 }]).map((reward) => ({
        kind: reward.kind || 'kut',
        amount: String(reward.amount ?? 1),
        itemId: reward.itemId || '',
      })),
    })
  }

  const saveQuest = async () => {
    if (!questForm) return
    setSavingQuest(true)
    setError('')
    try {
      const parsed = parseRequiredIntFields(
        { target: questForm.target },
        { target: 'Цель (сколько раз)' },
      )
      if (!questForm.title.trim()) throw new Error('Укажите название задания')
      if (questForm.targetScope === 'crop' && !questForm.targetCropKey) {
        throw new Error('Выберите культуру для задания')
      }
      if (questForm.targetScope === 'item' && !questForm.targetItemId) {
        throw new Error('Выберите предмет dex для задания')
      }

      const rewards = questForm.rewards.map((reward, idx) => {
        const amountParsed = parseRequiredIntFields(
          { amount: reward.amount },
          { amount: `Награда #${idx + 1}` },
        )
        const kind = reward.kind || 'kut'
        if (kind === 'item' && !reward.itemId) {
          throw new Error(`Награда #${idx + 1}: выберите предмет dex`)
        }
        return {
          kind,
          amount: amountParsed.amount,
          itemId: kind === 'item' ? reward.itemId : null,
        }
      })

      const payload = {
        period: questForm.period,
        action: questForm.action,
        target: parsed.target,
        title: questForm.title.trim(),
        description: questForm.description.trim(),
        emoji: questForm.emoji.trim() || '📋',
        enabled: questForm.enabled,
        targetScope: questForm.targetScope || 'any',
        targetCropKey: questForm.targetScope === 'crop' ? questForm.targetCropKey : null,
        targetItemId: questForm.targetScope === 'item' ? questForm.targetItemId : null,
        rewards,
      }

      if (questForm.mode === 'create') {
        if (!/^[a-z][a-z0-9_]{1,48}$/.test(questForm.key.trim())) {
          throw new Error('Ключ задания: латиница, цифры, _')
        }
        await createContentQuest({ ...payload, key: questForm.key.trim() })
        notifyAdmin('Задание создано')
      } else {
        await patchContentQuest(questForm.id, payload)
        notifyAdmin('Задание сохранено')
      }
      setQuestForm(null)
      await loadAll()
    } catch (err) {
      const message = err.message || 'Ошибка задания'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setSavingQuest(false)
    }
  }

  const confirmDeleteQuest = async () => {
    if (!deleteQuestTarget) return
    try {
      await deleteContentQuest(deleteQuestTarget.id)
      notifyAdmin(`Задание «${deleteQuestTarget.title}» удалено`)
      setDeleteQuestTarget(null)
      await loadAll()
    } catch (err) {
      notifyAdmin(err.message || 'Ошибка удаления', { error: true })
    }
  }

  const spriteOptions = (overview?.spriteKeys || []).map((s) => ({
    value: s.id,
    label: s.label,
  }))

  const stats = overview?.stats
  const questMeta = overview?.questMeta || { periods: [], actions: [], scopes: [], crops: [] }

  const questScopeOptions = (action) => {
    const passive = action === 'water' || action === 'claim_daily_seed'
    const craft = action === 'craft'
    return (questMeta.scopes || []).filter((item) => {
      if (passive) return item.id === 'any'
      if (craft) return item.id !== 'crop'
      return true
    })
  }

  const normalizeQuestTargetForAction = (form, action) => {
    const allowed = questScopeOptions(action).map((item) => item.id)
    const targetScope = allowed.includes(form.targetScope) ? form.targetScope : 'any'
    return {
      ...form,
      action,
      targetScope,
      targetCropKey: targetScope === 'crop' ? form.targetCropKey : '',
      targetItemId: targetScope === 'item' ? form.targetItemId : '',
    }
  }

  const questActionHint = questMeta.actionScopeHints?.[questForm?.action] || ''

  return (
    <div className="panel-content">
      <AdminActionModal
        open={Boolean(deleteCropTarget)}
        title="Удалить культуру?"
        description={`Культура «${deleteCropTarget?.key}» будет удалена. Активные грядки с этим саженцем могут работать некорректно.`}
        confirmText="Удалить"
        onConfirm={confirmDeleteCrop}
        onCancel={() => setDeleteCropTarget(null)}
      />
      <AdminActionModal
        open={Boolean(deleteCraftTarget)}
        title="Удалить рецепт?"
        description={`Рецепт «${deleteCraftTarget?.key}» будет удалён.`}
        confirmText="Удалить"
        onConfirm={confirmDeleteCraft}
        onCancel={() => setDeleteCraftTarget(null)}
      />
      <AdminActionModal
        open={Boolean(deleteQuestTarget)}
        title="Удалить задание?"
        description={`«${deleteQuestTarget?.title}» (${deleteQuestTarget?.key}) будет удалено. Прогресс игроков по ключу сохранится в JSON до сброса периода.`}
        confirmText="Удалить"
        onConfirm={confirmDeleteQuest}
        onCancel={() => setDeleteQuestTarget(null)}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Content · Контент</p>
        <h2 className="panel-page-title">Культуры, предметы, крафт, задания</h2>
        <p className="panel-page-lead">
          Создавайте предметы, культуры, крафт и задания NPC Cute всё сразу попадает в игру после сохранения
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-content-stats">
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Культур</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.crops ?? 0}</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Рецептов</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.recipes ?? 0}</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Предметов dex</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.dexItems ?? 0}</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Заданий</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.quests ?? 0}</p>
        </article>
      </div>

      <div className="panel-content-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`panel-content-tab${tab === t.id ? ' panel-content-tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Delete dex item confirm */}
      {deleteDexTarget && (
        <AdminActionModal
          open
          title={`Удалить «${deleteDexTarget.name}»?`}
          description="Предмет будет удалён из dex. Убедитесь, что он не используется в культурах, крафте или активных лотах биржи."
          confirmText="Удалить"
          danger
          onConfirm={handleDeleteDexItem}
          onCancel={() => setDeleteDexTarget(null)}
        />
      )}

      {tab === 'items' && (
        <div className="panel-content-stack">
          {/* Edit modal */}
          {editingDexItem && (
            <article className="panel-shelf panel-content-editor">
              <div className="panel-content-editor-head">
                <h3 className="panel-users-subtitle">✏️ Редактирование: {editingDexItem.emoji} {editingDexItem.name} (#{editingDexItem.id})</h3>
                <button className="pu-close-btn" onClick={() => setEditingDexItem(null)}>✕</button>
              </div>
              <div className="dex-full-form">
                <div className="dex-form-col">
                  {[
                    { key: 'name', label: 'Название *', placeholder: 'Табак' },
                    { key: 'emoji', label: 'Emoji', placeholder: '🌿' },
                    { key: 'name1', label: 'name1 (ед. число)', placeholder: 'Лист табака' },
                    { key: 'sorting', label: 'Категория (sorting)', placeholder: 'seeds' },
                  ].map(({ key, label, placeholder }) => (
                    <label key={key} className="panel-economy-field">
                      <span>{label}</span>
                      <input
                        className="panel-users-input"
                        value={editingDexItem[key] || ''}
                        onChange={(e) => setEditingDexItem({ ...editingDexItem, [key]: e.target.value })}
                        placeholder={placeholder}
                        disabled={savingDexItem}
                      />
                    </label>
                  ))}
                  <div className="panel-content-inline-2">
                    <label className="panel-economy-field">
                      <span>Цена</span>
                      <input className="panel-users-input" value={editingDexItem.price} onChange={(e) => setEditingDexItem({ ...editingDexItem, price: e.target.value.replace(/[^\d]/g, '') })} disabled={savingDexItem} />
                    </label>
                    <label className="panel-economy-field">
                      <span>Остаток</span>
                      <input className="panel-users-input" value={editingDexItem.remains} onChange={(e) => setEditingDexItem({ ...editingDexItem, remains: e.target.value.replace(/[^\d]/g, '') })} disabled={savingDexItem} />
                    </label>
                    <label className="panel-economy-field">
                      <span>Скидка %</span>
                      <input className="panel-users-input" value={editingDexItem.dis} onChange={(e) => setEditingDexItem({ ...editingDexItem, dis: e.target.value.replace(/[^\d]/g, '') })} disabled={savingDexItem} />
                    </label>
                  </div>
                </div>
                <div className="dex-form-col">
                  {[
                    { key: 'bio', label: 'Описание (bio)', rows: 3, placeholder: 'Показывается игрокам в магазине' },
                    { key: 'use', label: 'Использование (use)', rows: 2, placeholder: 'Что происходит при использовании' },
                    { key: 'bonus', label: 'Бонус (bonus)', rows: 2, placeholder: 'Бонус от предмета' },
                    { key: 'craft', label: 'Крафт-описание (craft)', rows: 2, placeholder: 'Рецепт в предмете' },
                  ].map(({ key, label, rows, placeholder }) => (
                    <label key={key} className="panel-economy-field">
                      <span>{label}</span>
                      <textarea
                        className="panel-users-input dex-textarea"
                        value={editingDexItem[key] || ''}
                        onChange={(e) => setEditingDexItem({ ...editingDexItem, [key]: e.target.value })}
                        rows={rows}
                        placeholder={placeholder}
                        disabled={savingDexItem}
                      />
                    </label>
                  ))}
                </div>
                <div className="dex-form-preview-col">
                  <DexItemPreview item={editingDexItem} />
                </div>
              </div>
              <div className="panel-content-editor-actions">
                <button className="panel-users-btn panel-users-btn-primary" onClick={handleSaveDexItem} disabled={savingDexItem}>
                  {savingDexItem ? 'Сохранение…' : 'Сохранить'}
                </button>
                <button className="panel-users-btn" onClick={() => setEditingDexItem(null)} disabled={savingDexItem}>
                  Отмена
                </button>
              </div>
            </article>
          )}

          <div className="panel-content-grid">
            <article className="panel-shelf">
              <div className="panel-content-editor-head">
                <p className="panel-shelf-label">Новый предмет</p>
                <button
                  className="pu-action-btn"
                  onClick={() => setShowDexPreview((v) => !v)}
                >
                  {showDexPreview ? 'Скрыть превью' : '👁 Превью'}
                </button>
              </div>
              <div className="dex-full-form">
                <div className="dex-form-col">
                  {[
                    { key: 'name', label: 'Название *', placeholder: 'Табак' },
                    { key: 'emoji', label: 'Emoji', placeholder: '🌿' },
                    { key: 'name1', label: 'name1 (ед. число)', placeholder: 'Лист табака' },
                    { key: 'sorting', label: 'Категория (sorting)', placeholder: 'seeds' },
                  ].map(({ key, label, placeholder }) => (
                    <label key={key} className="panel-economy-field">
                      <span>{label}</span>
                      <input
                        className="panel-users-input"
                        value={newItem[key] || ''}
                        onChange={(e) => setNewItem({ ...newItem, [key]: e.target.value })}
                        placeholder={placeholder}
                        disabled={creatingItem}
                      />
                    </label>
                  ))}
                  <div className="panel-content-inline-2">
                    <label className="panel-economy-field">
                      <span>Цена</span>
                      <input className="panel-users-input" value={newItem.price} onChange={(e) => setNewItem({ ...newItem, price: e.target.value.replace(/[^\d]/g, '') })} disabled={creatingItem} />
                    </label>
                    <label className="panel-economy-field">
                      <span>Остаток</span>
                      <input className="panel-users-input" value={newItem.remains} onChange={(e) => setNewItem({ ...newItem, remains: e.target.value.replace(/[^\d]/g, '') })} disabled={creatingItem} />
                    </label>
                    <label className="panel-economy-field">
                      <span>Скидка %</span>
                      <input className="panel-users-input" value={newItem.dis} onChange={(e) => setNewItem({ ...newItem, dis: e.target.value.replace(/[^\d]/g, '') })} disabled={creatingItem} />
                    </label>
                  </div>
                </div>
                <div className="dex-form-col">
                  {[
                    { key: 'bio', label: 'Описание (bio)', rows: 3, placeholder: 'Показывается игрокам в магазине' },
                    { key: 'use', label: 'Использование (use)', rows: 2, placeholder: 'Что происходит при использовании' },
                    { key: 'bonus', label: 'Бонус (bonus)', rows: 2, placeholder: 'Бонус от предмета' },
                    { key: 'craft', label: 'Крафт-описание (craft)', rows: 2, placeholder: 'Рецепт в предмете' },
                  ].map(({ key, label, rows, placeholder }) => (
                    <label key={key} className="panel-economy-field">
                      <span>{label}</span>
                      <textarea
                        className="panel-users-input dex-textarea"
                        value={newItem[key] || ''}
                        onChange={(e) => setNewItem({ ...newItem, [key]: e.target.value })}
                        rows={rows}
                        placeholder={placeholder}
                        disabled={creatingItem}
                      />
                    </label>
                  ))}
                </div>
                {showDexPreview && (
                  <div className="dex-form-preview-col">
                    <DexItemPreview item={newItem} />
                  </div>
                )}
              </div>
              <button type="button" className="panel-users-btn panel-users-btn-primary panel-action-btn" disabled={creatingItem} onClick={handleCreateItem}>
                {creatingItem ? 'Создаём…' : 'Создать предмет'}
              </button>
            </article>

            <article className="panel-shelf">
              <p className="panel-shelf-label">Каталог dex ({dexItems.length})</p>
              <div className="panel-content-search-row">
                <input className="panel-users-input" value={dexQuery} onChange={(e) => setDexQuery(e.target.value)} placeholder="Поиск по названию или id" />
                <button type="button" className="panel-users-btn" onClick={handleDexSearch}>Найти</button>
              </div>
              <div className="panel-content-dex-list">
                {dexItems.map((item) => (
                  <div key={item.id} className="panel-content-dex-row">
                    <span className="panel-content-dex-emoji">{item.emoji}</span>
                    <span className="panel-content-dex-name">{item.name}</span>
                    <span className="panel-shelf-muted">#{item.id}</span>
                    <span className="panel-shelf-muted">{item.price} kut · {item.remains} шт.</span>
                    {item.sorting && <span className="panel-content-dex-tag">{item.sorting}</span>}
                    <div className="panel-content-dex-actions">
                      <button
                        className="panel-users-btn"
                        onClick={() => openEditDexItem(item.id)}
                        title="Редактировать"
                      >
                        ✏️
                      </button>
                      <button
                        className="panel-users-btn panel-users-btn-danger"
                        onClick={() => setDeleteDexTarget(item)}
                        title="Удалить"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                ))}
                {!dexItems.length && !loading && <p className="panel-shelf-muted">Нет предметов</p>}
              </div>
            </article>
          </div>
        </div>
      )}

      {tab === 'crops' && (
        <div className="panel-content-stack">
          <div className="panel-content-toolbar">
            <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openNewCrop}>+ Новая культура</button>
          </div>
          <p className="panel-shelf-muted panel-content-balance-hint">
            Включённые культуры автоматически появляются на панели ресурсов фермы (семена, вода, инструмент сбора).
          </p>

          <div className="panel-content-crop-list">
            {(overview?.crops || []).map((crop) => (
              <article key={crop.id} className="panel-shelf panel-content-crop-card">
                <div className="panel-content-crop-head">
                  <div>
                    <h3 className="panel-users-subtitle">
                      {crop.displayName} ({crop.key})
                      {crop.enabled === false ? ' · выкл.' : ''}
                    </h3>
                    <p className="panel-shelf-muted">
                      {crop.seedEmoji} саженец → {formatSec(crop.growSeconds)} рост
                      {crop.harvestToolItemId ? ` · 🛠 ${crop.harvestToolName || crop.harvestToolItemId} ×${crop.harvestToolCost}` : ''}
                    </p>
                  </div>
                  <div className="panel-content-crop-actions">
                    <button type="button" className="panel-users-btn" onClick={() => openEditCrop(crop)}>Изменить</button>
                    <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => setDeleteCropTarget(crop)}>Удалить</button>
                  </div>
                </div>
                <div className="panel-content-drop-tags">
                  {(crop.harvestDrops || []).map((drop, idx) => (
                    <span key={`${crop.id}-${idx}-${drop.itemId}`} className="panel-content-drop-tag">
                      {drop.emoji} {drop.name} ×{drop.minAmount}{drop.maxAmount !== drop.minAmount ? `–${drop.maxAmount}` : ''} ({drop.chancePercent}%)
                    </span>
                  ))}
                </div>
                {crop.waterItemId && (
                  <p className="panel-shelf-muted">Полив: {crop.waterName || crop.waterItemId}{crop.waterCostPerUse ? ` ×${crop.waterCostPerUse}` : ''}</p>
                )}
              </article>
            ))}
          </div>

          {cropForm && (
            <article className="panel-shelf panel-content-editor">
              <h3 className="panel-users-subtitle">{cropForm.mode === 'create' ? 'Новая культура' : `Редактирование: ${cropForm.key}`}</h3>
              <div className="panel-economy-settings-form">
                {cropForm.mode === 'create' && (
                  <label className="panel-economy-field">
                    <span>Ключ (латиница)</span>
                    <input className="panel-users-input" value={cropForm.key} onChange={(e) => setCropForm({ ...cropForm, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') })} placeholder="tomato" />
                  </label>
                )}
                <label className="panel-economy-field">
                  <span>Название</span>
                  <input className="panel-users-input" value={cropForm.displayName} onChange={(e) => setCropForm({ ...cropForm, displayName: e.target.value })} />
                </label>
                <DexItemSearchPicker
                  label="Саженец (seed)"
                  value={cropForm.seedItemId}
                  onChange={(v) => setCropForm({ ...cropForm, seedItemId: v })}
                  hint="Любой предмет из dex: 🌱 саженец, название или id"
                />
                {(cropForm.key === 'tree' || cropForm.key === 'tobacco') ? (
                  <label className="panel-economy-field">
                    <span>Рост (секунды)</span>
                    <input className="panel-users-input" value={cropForm.growSeconds} disabled />
                    <span className="panel-shelf-muted">
                      Для дерева и табака время роста берётся из настроек Фермы — редактируется там, не здесь
                    </span>
                  </label>
                ) : (
                  <label className="panel-economy-field">
                    <span>Рост (секунды)</span>
                    <input className="panel-users-input" value={cropForm.growSeconds} onChange={(e) => setCropForm({ ...cropForm, growSeconds: e.target.value.replace(/[^\d]/g, '') })} />
                  </label>
                )}
                <DexItemSearchPicker
                  label="Инструмент сбора (топор и т.д.)"
                  value={cropForm.harvestToolItemId}
                  onChange={(v) => setCropForm({ ...cropForm, harvestToolItemId: v })}
                  hint="Предмет из dex: 🪓 топор, название или эмодзи"
                />
                <label className="panel-economy-field">
                  <span>Расход инструмента за сбор</span>
                  <input className="panel-users-input" value={cropForm.harvestToolCost} onChange={(e) => setCropForm({ ...cropForm, harvestToolCost: e.target.value.replace(/[^\d]/g, '') })} />
                </label>
                <DexItemSearchPicker
                  label="Предмет полива (пусто = глобальная вода)"
                  value={cropForm.waterItemId}
                  onChange={(v) => setCropForm({ ...cropForm, waterItemId: v })}
                  hint="Предмет из dex: 💧 вода или другой расходник"
                />
                {cropForm.waterItemId && (
                  <label className="panel-economy-field">
                    <span>Расход за полив</span>
                    <input className="panel-users-input" value={cropForm.waterCostPerUse} onChange={(e) => setCropForm({ ...cropForm, waterCostPerUse: e.target.value.replace(/[^\d]/g, '') })} />
                  </label>
                )}
                <label className="panel-economy-field">
                  <span>Спрайт на грядке</span>
                  <AdminSelect value={cropForm.spriteKey} onChange={(v) => setCropForm({ ...cropForm, spriteKey: v })} options={spriteOptions} />
                </label>
                <label className="panel-economy-field panel-craft-enabled-row">
                  <span>Включена в игре (показывается на ферме)</span>
                  <input
                    type="checkbox"
                    checked={cropForm.enabled !== false}
                    onChange={(e) => setCropForm({ ...cropForm, enabled: e.target.checked })}
                  />
                </label>

                <p className="panel-shelf-label">Урожай (можно несколько предметов)</p>
                {cropForm.harvestDrops.map((drop, idx) => (
                  <div key={idx} className="panel-content-drop-row">
                    <DexItemSearchPicker
                      label={`Предмет #${idx + 1}`}
                      value={drop.itemId}
                      hint="Урожай из dex: эмодзи, название, name1 или id"
                      onChange={(v) => {
                      const harvestDrops = [...cropForm.harvestDrops]
                      harvestDrops[idx] = { ...harvestDrops[idx], itemId: v }
                      setCropForm({ ...cropForm, harvestDrops })
                    }} />
                    <div className="panel-content-inline-3">
                      <input className="panel-users-input" value={drop.minAmount} onChange={(e) => {
                        const harvestDrops = [...cropForm.harvestDrops]
                        harvestDrops[idx] = { ...harvestDrops[idx], minAmount: e.target.value.replace(/[^\d]/g, '') }
                        setCropForm({ ...cropForm, harvestDrops })
                      }} placeholder="Мин" />
                      <input className="panel-users-input" value={drop.maxAmount} onChange={(e) => {
                        const harvestDrops = [...cropForm.harvestDrops]
                        harvestDrops[idx] = { ...harvestDrops[idx], maxAmount: e.target.value.replace(/[^\d]/g, '') }
                        setCropForm({ ...cropForm, harvestDrops })
                      }} placeholder="Макс" />
                      <input className="panel-users-input" value={drop.chancePercent} onChange={(e) => {
                        const harvestDrops = [...cropForm.harvestDrops]
                        harvestDrops[idx] = { ...harvestDrops[idx], chancePercent: e.target.value.replace(/[^\d]/g, '') }
                        setCropForm({ ...cropForm, harvestDrops })
                      }} placeholder="%" />
                    </div>
                    {cropForm.harvestDrops.length > 1 && (
                      <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => {
                        setCropForm({ ...cropForm, harvestDrops: cropForm.harvestDrops.filter((_, i) => i !== idx) })
                      }}>Убрать</button>
                    )}
                  </div>
                ))}
                <button type="button" className="panel-users-btn" onClick={() => setCropForm({ ...cropForm, harvestDrops: [...cropForm.harvestDrops, { ...EMPTY_DROP }] })}>
                  + Ещё предмет урожая
                </button>

                <div className="panel-content-form-actions">
                  <button type="button" className="panel-users-btn panel-users-btn-primary panel-action-btn" disabled={savingCrop} onClick={saveCrop}>
                    {savingCrop ? 'Сохраняем…' : 'Сохранить культуру'}
                  </button>
                  <button type="button" className="panel-users-btn" onClick={() => setCropForm(null)}>Отмена</button>
                </div>
              </div>
            </article>
          )}
        </div>
      )}

      {tab === 'craft' && (
        <div className="panel-content-stack">
          <div className="panel-content-toolbar">
            <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openNewCraft}>+ Новый крафт</button>
          </div>
          <div className="panel-content-craft-list">
            {(overview?.recipes || []).map((recipe) => (
              <article key={recipe.id} className="panel-shelf panel-content-craft-card">
                <div className="panel-content-crop-head">
                  <div>
                    <p className="panel-users-subtitle">{recipe.displayName || recipe.key}</p>
                    <p className="panel-shelf-muted">
                      {recipe.key}
                      {recipe.enabled === false ? ' · выключен' : ''}
                      {recipe.remains > 0 ? ` · осталось: ${recipe.remains}` : ' · безлимит'}
                    </p>
                    <p>
                      {recipe.ingredientAEmoji} {recipe.ingredientAName} + {recipe.ingredientBEmoji} {recipe.ingredientBName}
                      {' → '}
                      {recipe.resultEmoji} {recipe.resultName} ({recipe.successPercent}%)
                    </p>
                  </div>
                  <div className="panel-content-crop-actions">
                    <button type="button" className="panel-users-btn" onClick={() => openEditCraft(recipe)}>Изменить</button>
                    <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => setDeleteCraftTarget(recipe)}>Удалить</button>
                  </div>
                </div>
              </article>
            ))}
            {!overview?.recipes?.length && !loading && (
              <p className="panel-shelf-muted">Нет рецептов нажмите «Новый крафт»</p>
            )}
          </div>

          {craftForm && (
            <CraftRecipeWizard
              form={craftForm}
              setForm={setCraftForm}
              step={craftStep}
              setStep={setCraftStep}
              dexItems={dexItems}
              saving={savingCraft}
              onSave={saveCraft}
              onCancel={() => { setCraftForm(null); setCraftStep(1) }}
              onCreateDexItem={createDexItemForCraft}
            />
          )}
        </div>
      )}

      {tab === 'quests' && (
        <div className="panel-content-stack">
          <div className="panel-content-toolbar">
            <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openNewQuest}>
              + Новое задание
            </button>
          </div>
          <p className="panel-shelf-muted panel-content-balance-hint">
            На каждый период (час / день / неделя) игрок может взять одно активное задание. Действие считает прогресс автоматически на ферме и в крафте.
          </p>

          <div className="panel-content-craft-list">
            {(overview?.quests || []).map((quest) => (
              <article key={quest.id} className="panel-shelf panel-content-craft-card">
                <div className="panel-content-crop-head">
                  <div>
                    <p className="panel-users-subtitle">
                      {quest.emoji} {quest.title}
                      {quest.enabled === false ? ' · выкл.' : ''}
                    </p>
                    <p className="panel-shelf-muted">
                      {quest.key} · {quest.periodLabel} · {quest.actionLabel} ×{quest.target}
                      {quest.targetHint ? ` · ${quest.targetHint}` : ''}
                    </p>
                    <p className="panel-shelf-muted">{quest.description}</p>
                    <p>
                      {(quest.rewards || []).map((reward) => reward.label).filter(Boolean).join(' · ')
                        || 'Без награды (пассивное задание)'}
                    </p>
                  </div>
                  <div className="panel-content-crop-actions">
                    <button type="button" className="panel-users-btn" onClick={() => openEditQuest(quest)}>Изменить</button>
                    <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => setDeleteQuestTarget(quest)}>Удалить</button>
                  </div>
                </div>
              </article>
            ))}
            {!overview?.quests?.length && !loading && (
              <p className="panel-shelf-muted">Нет заданий нажмите «Новое задание»</p>
            )}
          </div>

          {questForm && (
            <article className="panel-shelf panel-content-editor">
              <h3 className="panel-users-subtitle">
                {questForm.mode === 'create' ? 'Новое задание' : `Редактирование: ${questForm.key}`}
              </h3>
              <div className="panel-economy-settings-form">
                {questForm.mode === 'create' && (
                  <label className="panel-economy-field">
                    <span>Ключ (латиница, не меняется)</span>
                    <input
                      className="panel-users-input"
                      value={questForm.key}
                      onChange={(e) => setQuestForm({ ...questForm, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') })}
                      placeholder="daily_sell_logs"
                    />
                  </label>
                )}
                <label className="panel-economy-field">
                  <span>Название</span>
                  <input className="panel-users-input" value={questForm.title} onChange={(e) => setQuestForm({ ...questForm, title: e.target.value })} />
                </label>
                <label className="panel-economy-field">
                  <span>Описание для игрока</span>
                  <textarea
                    className="panel-users-input panel-users-textarea"
                    rows={3}
                    value={questForm.description}
                    onChange={(e) => setQuestForm({ ...questForm, description: e.target.value })}
                  />
                </label>
                <div className="panel-content-inline-3">
                  <label className="panel-economy-field">
                    <span>Emoji</span>
                    <input className="panel-users-input" value={questForm.emoji} onChange={(e) => setQuestForm({ ...questForm, emoji: e.target.value })} />
                  </label>
                  <label className="panel-economy-field">
                    <span>Период</span>
                    <AdminSelect
                      value={questForm.period}
                      onChange={(value) => setQuestForm({ ...questForm, period: value })}
                      options={(questMeta.periods || []).map((item) => ({ value: item.id, label: item.label }))}
                    />
                  </label>
                  <label className="panel-economy-field">
                    <span>Сколько раз</span>
                    <input
                      className="panel-users-input"
                      value={questForm.target}
                      onChange={(e) => setQuestForm({ ...questForm, target: e.target.value.replace(/[^\d]/g, '') })}
                    />
                  </label>
                </div>
                <label className="panel-economy-field">
                  <span>Действие (что считать)</span>
                  <AdminSelect
                    value={questForm.action}
                    onChange={(value) => {
                      setQuestForm(normalizeQuestTargetForAction(questForm, value))
                    }}
                    options={(questMeta.actions || []).map((item) => ({ value: item.id, label: item.label }))}
                  />
                </label>
                {questActionHint ? (
                  <p className="panel-shelf-muted panel-content-balance-hint">{questActionHint}</p>
                ) : null}
                <label className="panel-economy-field">
                  <span>Что именно считать</span>
                  <AdminSelect
                    value={questForm.targetScope}
                    onChange={(value) => setQuestForm({
                      ...questForm,
                      targetScope: value,
                      targetCropKey: value === 'crop' ? questForm.targetCropKey : '',
                      targetItemId: value === 'item' ? questForm.targetItemId : '',
                    })}
                    options={questScopeOptions(questForm.action).map((item) => ({ value: item.id, label: item.label }))}
                  />
                </label>
                {questForm.targetScope === 'crop' ? (
                  <label className="panel-economy-field">
                    <span>Культура</span>
                    <AdminSelect
                      value={questForm.targetCropKey}
                      onChange={(value) => setQuestForm({ ...questForm, targetCropKey: value })}
                      options={(questMeta.crops || []).map((crop) => ({ value: crop.key, label: crop.label }))}
                    />
                  </label>
                ) : null}
                {questForm.targetScope === 'item' ? (
                  <DexItemSearchPicker
                    label="Предмет dex (семя, урожай или результат крафта)"
                    value={questForm.targetItemId}
                    onChange={(value) => setQuestForm({ ...questForm, targetItemId: value })}
                  />
                ) : null}
                {questForm.targetScope === 'random' ? (
                  <p className="panel-shelf-muted panel-content-balance-hint">
                    При взятии задания игроку случайно выпадет культура или рецепт — прогресс считается только по ней.
                  </p>
                ) : null}
                <label className="panel-economy-field panel-economy-field-inline">
                  <input
                    type="checkbox"
                    checked={questForm.enabled}
                    onChange={(e) => setQuestForm({ ...questForm, enabled: e.target.checked })}
                  />
                  <span>Включено в игре</span>
                </label>

                <p className="panel-shelf-label">Награды</p>
                {questForm.rewards.map((reward, idx) => (
                  <div key={idx} className="panel-content-drop-row">
                    <div className="panel-content-inline-3">
                      <label className="panel-economy-field">
                        <span>Тип #{idx + 1}</span>
                        <AdminSelect
                          value={reward.kind}
                          onChange={(value) => {
                            const rewards = [...questForm.rewards]
                            rewards[idx] = { ...rewards[idx], kind: value, itemId: value === 'item' ? rewards[idx].itemId : '' }
                            setQuestForm({ ...questForm, rewards })
                          }}
                          options={[
                            { value: 'kut', label: 'КУТ' },
                            { value: 'item', label: 'Предмет dex' },
                          ]}
                        />
                      </label>
                      <label className="panel-economy-field">
                        <span>Кол-во</span>
                        <input
                          className="panel-users-input"
                          value={reward.amount}
                          onChange={(e) => {
                            const rewards = [...questForm.rewards]
                            rewards[idx] = { ...rewards[idx], amount: e.target.value.replace(/[^\d]/g, '') }
                            setQuestForm({ ...questForm, rewards })
                          }}
                        />
                      </label>
                      {reward.kind === 'item' ? (
                        <DexItemSearchPicker
                          label="Предмет"
                          value={reward.itemId}
                          onChange={(value) => {
                            const rewards = [...questForm.rewards]
                            rewards[idx] = { ...rewards[idx], itemId: value }
                            setQuestForm({ ...questForm, rewards })
                          }}
                        />
                      ) : (
                        <div className="panel-economy-field" aria-hidden />
                      )}
                    </div>
                    {questForm.rewards.length > 1 && (
                      <button
                        type="button"
                        className="panel-users-btn panel-users-btn-danger"
                        onClick={() => setQuestForm({
                          ...questForm,
                          rewards: questForm.rewards.filter((_, i) => i !== idx),
                        })}
                      >
                        Убрать награду
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  className="panel-users-btn"
                  onClick={() => setQuestForm({ ...questForm, rewards: [...questForm.rewards, { ...EMPTY_QUEST_REWARD }] })}
                >
                  + Ещё награда
                </button>

                <div className="panel-content-form-actions">
                  <button type="button" className="panel-users-btn panel-users-btn-primary panel-action-btn" disabled={savingQuest} onClick={saveQuest}>
                    {savingQuest ? 'Сохраняем…' : 'Сохранить задание'}
                  </button>
                  <button type="button" className="panel-users-btn" onClick={() => setQuestForm(null)}>Отмена</button>
                </div>
              </div>
            </article>
          )}
        </div>
      )}
    </div>
  )
}
