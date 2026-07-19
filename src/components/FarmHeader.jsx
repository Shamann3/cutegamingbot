import { TAB_ICONS } from './TabIcons'

export default function FarmHeader({ isPreview, onOpenInventory, onOpenCraft }) {
  const InventoryIcon = TAB_ICONS.inventory
  const CraftIcon = TAB_ICONS.craft

  return (
    <header className="farm-header text-center">
      <div className="farm-header-tools">
        <button type="button" className="farm-header-tool-btn" onClick={onOpenInventory} aria-label="Инвентарь">
          <InventoryIcon />
        </button>
        <button type="button" className="farm-header-tool-btn" onClick={onOpenCraft} aria-label="Крафты">
          <CraftIcon />
        </button>
      </div>

      <div className="farm-header-crest-wrap mx-auto">
        <div className="farm-header-crest-glow" aria-hidden />
        <img
          src="/assets/cute-crest.png?v=2"
          alt="Cute Farming"
          draggable={false}
          className="farm-header-crest-img"
        />
      </div>

      <div className="farm-header-titles">
        <p className="farm-header-cute farm-title-serif">CUTE</p>
        <h1 className="farm-header-title farm-title-serif">Фермерство</h1>
      </div>

      {isPreview && (
        <p className="farm-header-preview-badge">
          Превью UI без сервера
        </p>
      )}
    </header>
  )
}
