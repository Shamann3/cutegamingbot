export default function ShopSearch({
  value,
  onChange,
  disabled,
  className = '',
  placeholder = 'Найти предмет…',
  ariaLabel = 'Поиск в магазине',
}) {
  return (
    <label className={`shop-search ${className}`.trim()}>
      <span className="shop-search-icon" aria-hidden>🔎</span>
      <input
        type="text"
        inputMode="search"
        enterKeyHint="search"
        className="shop-search-input"
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
      />
      {value ? (
        <button
          type="button"
          className="shop-search-clear"
          disabled={disabled}
          onClick={() => onChange('')}
          aria-label="Очистить поиск"
        >
          ✕
        </button>
      ) : null}
    </label>
  )
}
