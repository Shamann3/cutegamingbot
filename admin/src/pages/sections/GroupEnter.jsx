export function cabinetNeedsGroupPick(groupCount, preview) {
  return !preview && Number(groupCount) > 1
}

export default function GroupEnter({ groups, onPick }) {
  return (
    <div className="grp-enter">
      <div className="grp-enter-card">
        <h1>Ваши группы</h1>
        <p>Выберите группу, в которой у вас должность. Кабинет откроется в ней.</p>
        <ul>
          {(groups || []).map((group) => (
            <li key={group.chatId}>
              <button type="button" onClick={() => onPick(group.chatId)}>
                <strong>{group.title || 'Группа'}</strong>
                <span>{group.position || 'Должность'}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
