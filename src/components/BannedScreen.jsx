import { getSupportBotUrl } from '../lib/apiClient'

export default function BannedScreen({ message }) {
  const isMute = message && message.includes('замучены')
  const supportUrl = getSupportBotUrl()

  return (
    <div className="banned-screen">
      <div className="banned-card">
        <div className="banned-icon">{isMute ? '🔇' : '🔨'}</div>
        <div className="banned-stamp" style={{
          background: isMute ? '#f9731618' : '#ef444418',
          borderColor: isMute ? '#f9731640' : '#ef444440',
          color: isMute ? '#f97316' : '#ef4444',
        }}>
          {isMute ? 'МУТ' : 'БАН'}
        </div>

        <h1 className="banned-title">
          {isMute ? 'Вы временно ограничены' : 'Аккаунт заблокирован'}
        </h1>

        <p className="banned-message">
          {message || (isMute
            ? 'Вы временно не можете пользоваться игрой.'
            : 'Ваш аккаунт заблокирован администратором.'
          )}
        </p>

        {!isMute && (
          <a
            className="banned-appeal-btn"
            href={`${supportUrl}?start=appeal`}
            target="_blank"
            rel="noreferrer"
          >
            📬 Подать апелляцию
          </a>
        )}

        <div className="banned-support">
          <span className="banned-support-label">Поддержка:</span>
          <a
            className="banned-support-link"
            href={supportUrl}
            target="_blank"
            rel="noreferrer"
          >
            @cutegamingsupportbot
          </a>
        </div>
      </div>

      <style>{`
        .banned-screen {
          min-height: 100dvh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          background: #070f0a;
        }
        .banned-card {
          background: linear-gradient(180deg, rgba(10, 24, 16, 0.96) 0%, rgba(6, 16, 10, 0.98) 100%);
          border: 1px solid rgba(212, 175, 55, 0.32);
          border-radius: 20px;
          padding: 36px 24px;
          max-width: 360px;
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          text-align: center;
          box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }
        .banned-icon { font-size: 56px; line-height: 1; }
        .banned-stamp {
          font-size: 11px; font-weight: 900; letter-spacing: 0.2em;
          border: 1px solid; padding: 4px 16px; border-radius: 20px;
        }
        .banned-title {
          font-size: 20px; font-weight: 800; color: #f5e6c8;
          margin: 0; line-height: 1.3;
        }
        .banned-message {
          font-size: 13px; color: rgba(245, 230, 200, 0.6); margin: 0; line-height: 1.6;
        }
        .banned-appeal-btn {
          display: block; width: 100%; box-sizing: border-box;
          background: #d4a84b18; border: 1px solid #d4a84b60; color: #d4a84b;
          padding: 12px 24px; border-radius: 12px;
          font-size: 14px; font-weight: 700; text-decoration: none;
          transition: all 0.2s;
        }
        .banned-appeal-btn:hover { background: #d4a84b28; }
        .banned-support {
          display: flex; flex-direction: column; gap: 6px;
          background: rgba(6, 16, 10, 0.9); border: 1px solid rgba(212, 175, 55, 0.18);
          border-radius: 12px; padding: 14px 18px; width: 100%;
          box-sizing: border-box;
        }
        .banned-support-label { font-size: 11px; color: rgba(245, 230, 200, 0.4); }
        .banned-support-link {
          font-size: 14px; font-weight: 700; color: #fbbf24; text-decoration: none;
        }
      `}</style>
    </div>
  )
}
