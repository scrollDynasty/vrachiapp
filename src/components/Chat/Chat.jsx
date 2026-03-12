import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './Chat.scss';
import { useTranslation } from 'react-i18next';

const Chat = () => {
  const { consultationId } = useParams();
  const navigate = useNavigate();
  const [consultation, setConsultation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // WebSocket и keepalive лучше держать в ref, чтобы не триггерить лишние рендеры
  const wsRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [sending, setSending] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showAcceptModal, setShowAcceptModal] = useState(false);
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [justSentMessage, setJustSentMessage] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    fetchConsultation();
    fetchMessages();
    connectWebSocket();

    return () => {
      try {
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          
          wsRef.current.close();
        }
      } catch (_) {}
      setWsConnected(false);
    };
  }, [consultationId]);

  // Автоматический скролл к последнему сообщению только когда сам пользователь отправил сообщение
  useEffect(() => {
    if (justSentMessage) {
      scrollToBottom();
      setJustSentMessage(false);
    }
  }, [messages, justSentMessage]);

  const fetchConsultation = async () => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/consultations/${consultationId}/`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        setConsultation(data);
      } else {
        setError(t('chat.notFoundTitle'));
      }
      } catch (error) {
        setError(t('doctorsPage.errorServer'));
    }
  };

  const fetchMessages = async () => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/consultations/${consultationId}/messages/`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        setMessages(data);
        // При первой загрузке сообщений прокручиваем вниз
        setTimeout(() => scrollToBottom(), 100);
      } else {
        setError(t('consultations.loading'));
      }
    } catch (error) {
      
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    // Закрываем существующее подключение если есть
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/chat/${consultationId}/`;
    
    
    
    // WebSocket не поддерживает передачу заголовков, но браузер автоматически передает куки
    // для того же домена, если они httpOnly
    const websocket = new WebSocket(wsUrl);
    wsRef.current = websocket;

    websocket.onopen = () => {
      
      setWsConnected(true);
      // Запускаем keepalive ping каждые 25 секунд
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      pingIntervalRef.current = setInterval(() => {
        try {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        } catch (e) {
          
        }
      }, 25000);
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        
        if (data.type === 'chat_message') {
          const currentUser = getCurrentUser();
          const isMyMessage = data.sender_id === currentUser?.id;
          
          setMessages(prev => {
            // Проверяем, нет ли уже такого сообщения
            const messageExists = prev.some(msg => msg.id === data.message_id);
            if (messageExists) {
              return prev;
            }
            
            return [...prev, {
              id: data.message_id,
              content: data.message,
              sender: {
                id: data.sender_id,
                full_name: data.sender_name,
                initials: data.sender_initials
              },
              created_at: data.timestamp,
              is_read: false
            }];
          });
          
          // Если это мое сообщение, прокручиваем вниз
          if (isMyMessage) {
            setJustSentMessage(true);
          }
        } else if (data.type === 'connection_established') {
          
        } else if (data.type === 'error') {
          
          setError(data.message);
        } else if (data.type === 'pong') {
          
        }
      } catch (error) {
        
      }
    };

    websocket.onerror = (error) => {
      
      setWsConnected(false);
    };

    websocket.onclose = (event) => {
      
      setWsConnected(false);
      // Чистим keepalive
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
      
      // Проверяем код закрытия для понимания причины
      if (event.code === 4001) {
        
        setError('Ошибка аутентификации. Перезайдите в систему.');
        return;
      } else if (event.code === 4003) {
        
        setError('У вас нет доступа к этой консультации.');
        return;
      }
      
      // Попытка переподключения через 3 секунды для других ошибок
      setTimeout(() => {
        // Проверяем актуальное состояние подключения
        setWsConnected(currentConnected => {
          if (!currentConnected) {
            
            connectWebSocket();
          }
          return currentConnected;
        });
      }, 3000);
    };

  };

  const scrollToBottom = () => {
    // Убираем автоматический скролл при отправке сообщений
    // messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    
    if (!newMessage.trim() || sending || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    setSending(true);

    try {
      // Отправляем сообщение через WebSocket
      wsRef.current.send(JSON.stringify({
        type: 'chat_message',
        message: newMessage.trim()
      }));
      
      setNewMessage('');
      // Отмечаем, что мы только что отправили сообщение
      setJustSentMessage(true);
    } catch (error) {
      
      setError('Ошибка соединения с сервером');
    } finally {
      setSending(false);
    }
  };

  const handleAcceptConsultation = async () => {
    setActionLoading(true);
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/consultations/${consultationId}/accept/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        setConsultation(data.consultation);
        setShowAcceptModal(false);
        // Показываем уведомление об успехе
        showNotification('Консультация успешно принята!', 'success');
      } else {
        const error = await response.json();
        showNotification(error.error || 'Ошибка принятия консультации', 'error');
      }
    } catch (error) {
      showNotification(t('doctorsPage.errorServer'), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCompleteConsultation = async () => {
    setActionLoading(true);
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/consultations/${consultationId}/complete/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        setConsultation(data.consultation);
        setShowCompleteModal(false);
        showNotification('Консультация успешно завершена!', 'success');
      } else {
        const error = await response.json();
        showNotification(error.error || 'Ошибка завершения консультации', 'error');
      }
    } catch (error) {
      showNotification(t('doctorsPage.errorServer'), 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const showNotification = (message, type = 'info') => {
    // Создаем уведомление
    const notification = document.createElement('div');
    notification.className = `chat__notification chat__notification--${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Удаляем уведомление через 3 секунды
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 3000);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const lng = (localStorage.getItem('i18nextLng') || 'ru').startsWith('uz') ? 'uz-UZ' : (localStorage.getItem('i18nextLng') || 'ru');
    return date.toLocaleDateString(lng, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const canWrite = () => {
    if (!consultation) return false;
    
    // Получаем текущего пользователя из localStorage
    const userData = JSON.parse(localStorage.getItem('user') || '{}');
    
    if (userData.role === 'patient') {
      return consultation.can_patient_write;
    } else if (userData.role === 'doctor') {
      return consultation.can_doctor_write;
    }
    
    return false;
  };

  const isDoctor = () => {
    const userData = JSON.parse(localStorage.getItem('user') || '{}');
    return userData.role === 'doctor';
  };

  const getCurrentUser = () => {
    return JSON.parse(localStorage.getItem('user') || '{}');
  };

  const isMyMessage = (message) => {
    const currentUser = getCurrentUser();
    return message.sender.id === currentUser.id;
  };

  const getOtherParticipant = () => {
    if (!consultation) return null;
    const currentUser = getCurrentUser();
    if (currentUser.role === 'doctor') {
      return consultation.patient;
    } else {
      return consultation.doctor;
    }
  };

  const getOtherParticipantRole = () => {
    const currentUser = getCurrentUser();
    if (currentUser.role === 'doctor') {
      return 'Пациент';
    } else {
      return 'Врач';
    }
  };

  const getMessageProgress = () => {
    const messageCount = consultation?.messages_count || 0;
    const maxMessages = 50;
    return Math.round((messageCount / maxMessages) * 100);
  };

  const formatConsultationDate = (dateString) => {
    const date = new Date(dateString);
    const lng = (localStorage.getItem('i18nextLng') || 'ru').startsWith('uz') ? 'uz-UZ' : (localStorage.getItem('i18nextLng') || 'ru');
    return date.toLocaleString(lng, {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
      hour12: true
    });
  };

  const formatMessageTime = (dateString) => {
    const date = new Date(dateString);
    const lng = (localStorage.getItem('i18nextLng') || 'ru').startsWith('uz') ? 'uz-UZ' : (localStorage.getItem('i18nextLng') || 'ru');
    return date.toLocaleTimeString(lng, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  if (loading) {
    return (
      <div className="chat">
        <div className="chat__loading">
          <div className="loading-spinner"></div>
          <p>{t('chat.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="chat">
        <div className="chat__error">
          <h2>{t('chat.errorTitle')}</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/consultations')} className="chat__back-btn">
            {t('common.back')}
          </button>
        </div>
      </div>
    );
  }

  if (!consultation) {
    return (
      <div className="chat">
        <div className="chat__error">
          <h2>{t('chat.notFoundTitle')}</h2>
          <p>{t('chat.notFoundText')}</p>
          <button onClick={() => navigate('/consultations')} className="chat__back-btn">
            {t('common.back')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat">
      <div className="chat__header">
        <button onClick={() => navigate('/consultations')} className="chat__back-btn">
          {t('chat.back')}
        </button>
        
        <div className="chat__consultation-title">
          <h1>{getOtherParticipant()?.full_name || 'Участник'}</h1>
        </div>
      </div>

      <div className="chat__participant-bar">
        <div className="chat__participant-info">
          <span className={`chat__participant-status chat__participant-status--${consultation.status}`}>
            {consultation.status === 'pending' && 'Ожидание'}
            {consultation.status === 'active' && 'Активна'}
            {consultation.status === 'completed' && 'Завершена'}
            {consultation.status === 'cancelled' && 'Отменена'}
          </span>
        </div>
        <div className="chat__message-counter">
          {consultation.messages_count || 0}/50
        </div>
      </div>

        {/* Кнопки действий для врача */}
      {isDoctor() && consultation.status === 'pending' && (
        <div className="chat__doctor-actions">
          <button 
            onClick={() => setShowAcceptModal(true)}
            disabled={actionLoading}
            className="chat__accept-btn"
          >
            {actionLoading ? 'Принятие...' : 'Принять консультацию'}
          </button>
        </div>
      )}

      {isDoctor() && consultation.status === 'active' && (
        <div className="chat__doctor-actions">
          <button 
            onClick={() => setShowCompleteModal(true)}
            disabled={actionLoading}
            className="chat__complete-btn"
          >
            {actionLoading ? 'Завершение...' : 'Завершить консультацию'}
          </button>
        </div>
      )}

      <div className="chat__messages">
        {messages.length === 0 ? (
          <div className="chat__empty">
            <div className="chat__empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p>Сообщений пока нет</p>
                      {consultation.status === 'pending' && (
            <div className="chat__status-info chat__status-info--pending">
              <div className="chat__status-icon">⏳</div>
              <div className="chat__status-content">
                <h3>
                  {isDoctor() 
                    ? 'Ожидает вашего принятия'
                    : 'Ожидает принятия врачом'
                  }
                </h3>
                <p>
                  {isDoctor() 
                    ? 'Примите консультацию, чтобы начать общение с пациентом'
                    : 'Врач рассмотрит вашу заявку и примет консультацию. После этого вы сможете общаться в чате.'
                  }
                </p>
              </div>
            </div>
          )}
          
          {consultation.status === 'completed' && (
            <div className="chat__status-info chat__status-info--completed">
              <div className="chat__status-icon">✅</div>
              <div className="chat__status-content">
                <h3>Консультация завершена</h3>
                <p>Этот чат заархивирован. Вы можете просматривать историю сообщений, но не можете отправлять новые.</p>
              </div>
            </div>
          )}
          
          {consultation.status === 'cancelled' && (
            <div className="chat__status-info chat__status-info--cancelled">
              <div className="chat__status-icon">❌</div>
              <div className="chat__status-content">
                <h3>Консультация отменена</h3>
                <p>Эта консультация была отменена и недоступна для общения.</p>
              </div>
            </div>
          )}
          </div>
        ) : (
          <div className="chat__messages-list">
            {messages.map((message) => (
              <div 
                key={message.id} 
                className={`chat__message ${isMyMessage(message) ? 'chat__message--own' : 'chat__message--other'}`}
              >
                <div className="chat__message-avatar">
                  {message.sender.initials}
                </div>
                <div className="chat__message-content">
                  <div className="chat__message-header">
                    <span className="chat__message-sender">{message.sender.initials}</span>
                    <span className="chat__message-time">{formatMessageTime(message.created_at)}</span>
                  </div>
                  <div className="chat__message-text">{message.content}</div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="chat__input-area">
        {canWrite() ? (
          <form className="chat__input-form" onSubmit={handleSendMessage}>
            <div className="chat__input-container">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Введите сообщение..."
                className="chat__input"
                disabled={sending}
              />
              <button 
                type="submit" 
                className="chat__send-btn"
                disabled={!newMessage.trim() || sending}
              >
                {sending ? '...' : '➤'}
              </button>
            </div>
          </form>
        ) : (
          <div className="chat__input-disabled">
            <div className="chat__input-disabled-content">
              {consultation.status === 'pending' && (
                <>
                  <span className="chat__disabled-icon">🔒</span>
                  <p>
                    {isDoctor() 
                      ? 'Примите консультацию, чтобы разблокировать чат'
                      : 'Чат будет разблокирован после принятия консультации врачом'
                    }
                  </p>
                </>
              )}
              {consultation.status === 'completed' && (
                <>
                  <span className="chat__disabled-icon">🔐</span>
                  <p>Консультация завершена. Чат заархивирован.</p>
                </>
              )}
            </div>
          </div>
        )}
        

      </div>

      {/* Модальное окно принятия консультации */}
      {showAcceptModal && (
        <div className="chat__modal-overlay" onClick={() => setShowAcceptModal(false)}>
          <div className="chat__modal" onClick={(e) => e.stopPropagation()}>
            <div className="chat__modal-header">
              <h3>Принять консультацию</h3>
              <button 
                className="chat__modal-close"
                onClick={() => setShowAcceptModal(false)}
              >
                ×
              </button>
            </div>
            <div className="chat__modal-content">
              <p>Вы уверены, что хотите принять эту консультацию?</p>
              <p>После принятия вы сможете общаться с пациентом.</p>
            </div>
            <div className="chat__modal-actions">
              <button 
                className="chat__modal-btn chat__modal-btn--secondary"
                onClick={() => setShowAcceptModal(false)}
                disabled={actionLoading}
              >
                Отмена
              </button>
              <button 
                className="chat__modal-btn chat__modal-btn--primary"
                onClick={handleAcceptConsultation}
                disabled={actionLoading}
              >
                {actionLoading ? 'Принятие...' : 'Принять'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно завершения консультации */}
      {showCompleteModal && (
        <div className="chat__modal-overlay" onClick={() => setShowCompleteModal(false)}>
          <div className="chat__modal" onClick={(e) => e.stopPropagation()}>
            <div className="chat__modal-header">
              <h3>Завершить консультацию</h3>
              <button 
                className="chat__modal-close"
                onClick={() => setShowCompleteModal(false)}
              >
                ×
              </button>
            </div>
            <div className="chat__modal-content">
              <p>Вы уверены, что хотите завершить эту консультацию?</p>
              <p>После завершения новые сообщения будут недоступны.</p>
            </div>
            <div className="chat__modal-actions">
              <button 
                className="chat__modal-btn chat__modal-btn--secondary"
                onClick={() => setShowCompleteModal(false)}
                disabled={actionLoading}
              >
                Отмена
              </button>
              <button 
                className="chat__modal-btn chat__modal-btn--danger"
                onClick={handleCompleteConsultation}
                disabled={actionLoading}
              >
                {actionLoading ? 'Завершение...' : 'Завершить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chat; 


