export default function SearchBar({ query, onChange, count }) {
  return (
    <div className="craftmap-search">
      <input
        className="panel-users-input"
        placeholder="Поиск: название, ID, категория, описание…"
        value={query}
        onChange={(e) => onChange(e.target.value)}
      />
      {query ? <span className="panel-shelf-muted">Найдено: {count}</span> : null}
    </div>
  )
}
