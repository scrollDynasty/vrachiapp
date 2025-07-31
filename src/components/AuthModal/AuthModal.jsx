import React, { useState } from 'react';
import './AuthModal.scss';

const AuthModal = ({ isOpen, onClose, onAuthSuccess }) => {
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

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const endpoint = isLogin ? '/api/auth/login/' : '/api/auth/register/';
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        // Сохраняем пользователя
        localStorage.setItem('user', JSON.stringify(data.user));
        
        onAuthSuccess(data.user);
        onClose();
      } else {
        setError(data.error || data.message || 'Произошла ошибка');
      }
    } catch (err) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setLoading(true);
    setError('');

    try {
      // Используем Google Identity Services (более современный подход)
      if (window.google && window.google.accounts) {
        const client = google.accounts.oauth2.initTokenClient({
          client_id: '735617581412-e8ceb269bj7qqrv9sl066q63g5dr5sne.apps.googleusercontent.com',
          scope: 'email profile',
          callback: async (response) => {
            if (response.access_token) {
              try {
                // Отправляем токен на сервер
                const serverResponse = await fetch('http://localhost:8000/api/auth/google-auth/', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  credentials: 'include',
                  body: JSON.stringify({ access_token: response.access_token })
                });

                const data = await serverResponse.json();

                if (serverResponse.ok) {
                  localStorage.setItem('user', JSON.stringify(data.user));
                  onAuthSuccess(data.user);
                  onClose();
                } else {
                  setError(data.error || 'Ошибка аутентификации через Google');
                }
              } catch (err) {
                setError('Ошибка соединения с сервером');
              }
            }
            setLoading(false);
          },
        });
        
        client.requestAccessToken();
      } else {
        // Fallback - простой redirect
        const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=735617581412-e8ceb269bj7qqrv9sl066q63g5dr5sne.apps.googleusercontent.com&redirect_uri=${encodeURIComponent(window.location.origin)}&response_type=token&scope=email profile`;
        
        // Сохраняем текущее состояние
        localStorage.setItem('pendingGoogleAuth', 'true');
        
        // Перенаправляем на Google
        window.location.href = googleAuthUrl;
      }
    } catch (err) {
      setError('Ошибка при аутентификации через Google');
      setLoading(false);
    }
  };



  if (!isOpen) return null;

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button className="auth-modal__close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        <div className="auth-modal__content">
          <h2 className="auth-modal__title">
            {isLogin ? 'Войти в аккаунт' : 'Создать аккаунт'}
          </h2>

          {error && (
            <div className="auth-modal__error">
              {error}
            </div>
          )}

          <form className="auth-modal__form" onSubmit={handleSubmit}>
            {!isLogin && (
              <>
                <div className="auth-modal__form-row">
                  <div className="auth-modal__form-group">
                    <label htmlFor="first_name">Имя</label>
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
                    <label htmlFor="last_name">Фамилия</label>
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
                  <label htmlFor="username">Имя пользователя</label>
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
              <label htmlFor="password">Пароль</label>
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
                <label htmlFor="password_confirm">Подтвердите пароль</label>
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
              {loading ? 'Загрузка...' : (isLogin ? 'Войти' : 'Зарегистрироваться')}
            </button>
          </form>

          <div className="auth-modal__divider">
            <span>или</span>
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
            {isLogin ? 'Войти через Google' : 'Зарегистрироваться через Google'}
          </button>

          <div className="auth-modal__footer">
            <p>
              {isLogin ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}
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
                }}
              >
                {isLogin ? 'Зарегистрироваться' : 'Войти'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthModal; 