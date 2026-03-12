import React, { useState } from 'react';
import './SupportModal.scss';
import { useTranslation } from 'react-i18next';

const getCsrfToken = () => (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '';

const SupportModal = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!message.trim()) return;
    setIsSending(true);
    try {
      const resp = await fetch('/api/auth/support/send/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        credentials: 'include',
        body: JSON.stringify({ message: message.trim() })
      });
      if (resp.ok) {
        onClose();
      } else {
        alert(t('common.error', 'Ошибка'));
      }
    } catch (e) {
      alert(t('common.serverError', 'Ошибка сети'));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="support-modal__overlay" onClick={onClose}>
      <div className="support-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="support-modal__header">
          <div className="support-modal__title">
            <div className="support-modal__icon" aria-hidden>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3>{t('common.support', 'Поддержка')}</h3>
          </div>
          <button className="support-modal__close" aria-label="Close" onClick={onClose}>×</button>
        </div>
        <div className="support-modal__body">
          <p className="support-modal__subtitle">{t('support.subtitle', 'Опишите проблему — мы постараемся помочь как можно быстрее.')}</p>
          <textarea
            className="support-modal__textarea"
            rows={6}
            placeholder={t('footer.writeSupport', 'Опишите вашу проблему...')}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isSending && message.trim()) {
                handleSend();
              }
            }}
          />
        </div>
        <div className="support-modal__footer">
          <button className="support-modal__send" disabled={isSending || !message.trim()} onClick={handleSend}>
            {isSending ? t('common.sending', 'Отправка...') : t('common.send', 'Отправить')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SupportModal;





