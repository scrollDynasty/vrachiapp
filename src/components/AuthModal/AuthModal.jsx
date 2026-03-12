import React, { useState } from 'react';
import ReactDOM from 'react-dom';
import './AuthModal.scss';
import { useTranslation } from 'react-i18next';

const AuthModal = ({ isOpen, onClose, onAuthSuccess, isDarkTheme }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
    username: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [needsVerification, setNeedsVerification] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const { t } = useTranslation();

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleResendVerification = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/resend-verification/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({ email: verificationEmail })
      });

      const data = await response.json();

      if (response.ok) {
        setSuccessMessage(t('auth.resendSuccess', 'Confirmation email resent. Please check your email..'));
        setNeedsVerification(false);
        // Очищаем сообщение через 5 секунд
        setTimeout(() => setSuccessMessage(''), 5000);
      } else {
        setError(data.error || 'Ошибка отправки email');
      }
    } catch (err) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMessage('');
    setNeedsVerification(false);

    // без отладочного лога

    try {
      const endpoint = isLogin ? '/api/auth/login/' : '/api/auth/register/';
      const response = await fetch(`https://vrachiapp-production.up.railway.app${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        if (isLogin) {
          // Сохраняем пользователя при входе
          localStorage.setItem('user', JSON.stringify(data.user));
          onAuthSuccess(data.user);
          onClose();
        } else {
          // При регистрации показываем сообщение о необходимости подтверждения
          setSuccessMessage(data.message || 'Регистрация успешна! Проверьте ваш email для подтверждения аккаунта.');
          // Закрываем модальное окно через 3 секунды
          setTimeout(() => {
            onClose();
            setSuccessMessage('');
          }, 3000);
        }
      } else {
        // Обрабатываем конкретные ошибки
         let errorMessage = t('auth.genericError', 'Произошла ошибка');
        
        if (response.status === 400) {
          if (data.needs_verification) {
            // Пользователь не подтвердил email
            setNeedsVerification(true);
            setVerificationEmail(data.email);
            errorMessage = data.error;
          } else if (data.error) {
            errorMessage = data.error;
          } else if (data.email) {
            errorMessage = data.email[0];
          } else if (data.password) {
            errorMessage = data.password[0];
          } else if (data.username) {
            errorMessage = data.username[0];
          } else if (data.non_field_errors) {
            errorMessage = data.non_field_errors[0];
          }
        } else if (response.status === 401) {
          errorMessage = t('auth.invalidCredentials', 'Неверный email или пароль');
        } else if (response.status === 403) {
          errorMessage = t('auth.blocked', 'Аккаунт заблокирован');
        } else if (response.status === 404) {
          errorMessage = t('auth.notFound', 'Пользователь не найден');
        } else if (response.status === 500) {
          errorMessage = t('auth.serverError', 'Ошибка сервера. Попробуйте позже');
        }
        
        setError(errorMessage);
      }
    } catch (err) {
      setError('Ошибка соединения с сервером. Проверьте интернет-соединение');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setError('');
    // Динамический redirect_uri = текущий origin (добавьте оба варианта в Google Console: https://vrachiapp-production.up.railway.app и https://www.healzy.uz)
    const redirectUri = window.location.origin.replace(/\/$/, '');
    const params = new URLSearchParams({
      client_id: '735617581412-e8ceb269bj7qqrv9sl066q63g5dr5sne.apps.googleusercontent.com',
      redirect_uri: redirectUri,
      response_type: 'token',
      scope: 'openid email profile',
      prompt: 'select_account',
      include_granted_scopes: 'true'
    });
    const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
    localStorage.setItem('pendingGoogleAuth', 'true');
    window.location.href = googleAuthUrl;
  };

  if (!isOpen) return null;

  const modalContent = (
    <div className={`auth-modal-overlay ${isDarkTheme ? 'dark-theme' : ''}`} onClick={onClose}>
      <div className={`auth-modal ${isDarkTheme ? 'dark-theme' : ''}`} onClick={(e) => e.stopPropagation()}>
        <button className="auth-modal__close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        <div className="auth-modal__content">
          <h2 className="auth-modal__title">
           {isLogin ? t('common.login') : t('auth.createAccount', 'Создать аккаунт')}
          </h2>

          {error && (
            <div className="auth-modal__error">
              {error}
            </div>
          )}

          {successMessage && (
            <div className="auth-modal__success-message">
              {successMessage}
            </div>
          )}

          {needsVerification && (
            <div className="auth-modal__verification-message">
              <p>{t('auth.verifyPlease', 'Пожалуйста, подтвердите ваш email')}: {verificationEmail}</p>
              <button 
                className="auth-modal__resend-verification"
                onClick={handleResendVerification}
                disabled={loading}
              >
                {loading ? t('auth.sending', 'Отправка...') : t('auth.resend', 'Отправить повторно')}
              </button>
            </div>
          )}

          <form className="auth-modal__form" onSubmit={handleSubmit}>
            {!isLogin && (
              <>
                <div className="auth-modal__form-row">
                  <div className="auth-modal__form-group">
                    <label htmlFor="first_name">{t('profile.firstName', 'Имя')}</label>
                    <input
                      type="text"
                      id="first_name"
                      name="first_name"
                      value={formData.first_name}
                      onChange={handleInputChange}
                      required={!isLogin}
                    />
                  </div>
                  <div className="auth-modal__form-group">
                    <label htmlFor="last_name">{t('profile.lastName', 'Фамилия')}</label>
                    <input
                      type="text"
                      id="last_name"
                      name="last_name"
                      value={formData.last_name}
                      onChange={handleInputChange}
                      required={!isLogin}
                    />
                  </div>
                </div>
                <div className="auth-modal__form-group">
                  <label htmlFor="username">{t('auth.username', 'Имя пользователя')}</label>
                  <input
                    type="text"
                    id="username"
                    name="username"
                    value={formData.username}
                    onChange={handleInputChange}
                    required={!isLogin}
                  />
                </div>
              </>
            )}

            <div className="auth-modal__form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="auth-modal__form-group">
              <label htmlFor="password">{t('auth.password', 'Пароль')}</label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                required
              />
            </div>

            {!isLogin && (
              <div className="auth-modal__form-group">
                <label htmlFor="password_confirm">{t('auth.passwordConfirm', 'Подтвердите пароль')}</label>
                <input
                  type="password"
                  id="password_confirm"
                  name="password_confirm"
                  value={formData.password_confirm}
                  onChange={handleInputChange}
                  required={!isLogin}
                />
              </div>
            )}

            <button 
              type="submit" 
              className="auth-modal__submit"
              disabled={loading}
            >
              {loading ? t('auth.loading', 'Загрузка...') : (isLogin ? t('common.login') : t('auth.register', 'Зарегистрироваться'))}
            </button>
          </form>

          <div className="auth-modal__divider">
            <span>{t('auth.or', 'или')}</span>
          </div>

          <button 
            className="auth-modal__google-btn"
            onClick={handleGoogleAuth}
            disabled={loading}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {isLogin ? t('auth.loginWithGoogle', 'Войти через Google') : t('auth.registerWithGoogle', 'Зарегистрироваться через Google')}
          </button>

          <div className="auth-modal__footer">
            <p>
              {isLogin ? t('auth.noAccount', 'Нет аккаунта?') : t('auth.haveAccount', 'Уже есть аккаунт?')}
              <button 
                className="auth-modal__toggle"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                  setFormData({
                    email: '',
                    password: '',
                    password_confirm: '',
                    first_name: '',
                    last_name: '',
                    username: ''
                  });
                  setNeedsVerification(false);
                  setVerificationEmail('');
                  setSuccessMessage(''); // Очищаем сообщение при переключении
                }}
              >
                {isLogin ? t('auth.register', 'Зарегистрироваться') : t('common.login')}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modalContent, document.body);
};

export default AuthModal; 


