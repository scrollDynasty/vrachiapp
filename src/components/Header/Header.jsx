import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import healzyLogo from '../../assets/images/healzy.svg';
import AuthModal from '../AuthModal/AuthModal';
import SupportModal from '../SupportModal/SupportModal';
import './Header.scss';
import { useTranslation } from 'react-i18next';
import i18n from 'i18next';

const Header = ({ isAuthenticated, userData, onLogout, onAuthSuccess, isDarkTheme, toggleTheme }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [currentLanguage, setCurrentLanguage] = useState(() => (i18n.language || 'ru').slice(0,2).toUpperCase());
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [currentUserData, setCurrentUserData] = useState(null);
  const [showSupportModal, setShowSupportModal] = useState(false);

  // Получаем актуальные данные пользователя с сервера
  useEffect(() => {
    const fetchCurrentUser = async () => {
      if (isAuthenticated) {
        try {
          const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/current-user/', {
            credentials: 'include'
          });
          if (response.ok) {
            const data = await response.json();
            setCurrentUserData(data);
          }
        } catch (error) { }
      }
    };

    fetchCurrentUser();
  }, [isAuthenticated]);

  const handleLogoClick = () => {
    navigate('/');
  };

  const languages = [
    { code: 'ru', name: 'Русский' },
    { code: 'uz', name: 'O‘zbekcha' },
    { code: 'en', name: 'English' }
  ];

  const handleAuthSuccess = (user) => {
    // Обновляем состояние в App.jsx
    if (onAuthSuccess) {
      onAuthSuccess();
    }
    setShowAuthModal(false);
  };

  const handleLogout = () => {
    if (onLogout) {
      onLogout();
    }
  };

  // Определяем роль пользователя
  const getUserRole = () => {
    const data = currentUserData || userData;
    if (!data) return t('role.guest');
    
    if (data.is_staff || data.is_superuser) {
      return t('role.admin');
    }
    
    if (data.role === 'doctor') {
      return t('role.doctor');
    }
    
    return t('role.patient');
  };

  return (
    <header className="header">
      <div className="container">
        <div className="header__content">
          <div className="header__logo">
            <div className="header__logo-container" onClick={handleLogoClick} style={{ cursor: 'pointer' }}>
              <img src={healzyLogo} alt="Healzy" className="header__logo-img" />
            </div>
          </div>

          <div className="header__actions">
            {/* Телефон */}
            <div className="header__phone">
              <div className="header__phone-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <span className="header__phone-number">{t('header.phoneNumber')}</span>
            </div>

            {/* Смена языка */}
            <div className="header__language">
              <div className="header__language-container">
                <div className="header__language-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div className="header__language-divider"></div>
                <div className="header__language-buttons">
                  <button
                    className="header__language-btn"
                    onClick={() => {
                      const currentIdx = languages.findIndex(l => l.code === (i18n.language || 'ru').slice(0,2));
                      const nextIdx = (currentIdx + 1) % languages.length;
                      const next = languages[nextIdx].code;
                      i18n.changeLanguage(next);
                      localStorage.setItem('i18nextLng', next);
                      setCurrentLanguage(next.toUpperCase());
                    }}
                    title={languages.find(l => l.code === (i18n.language || 'ru').slice(0,2))?.name}
                  >
                    {currentLanguage}
                  </button>
                </div>
              </div>
            </div>

            {/* Пользовательская секция */}
            {isAuthenticated && (currentUserData || userData) ? (
              <div className="header__user">
                <div className="header__user-avatar">
                  {(currentUserData || userData).avatar ? (
                    <img src={(currentUserData || userData).avatar} alt="Аватар" />
                  ) : (
                    <div className="header__user-avatar-placeholder">
                      {(currentUserData || userData).first_name && (currentUserData || userData).last_name 
                        ? `${(currentUserData || userData).first_name[0]}${(currentUserData || userData).last_name[0]}`.toUpperCase()
                        : (currentUserData || userData).first_name?.[0]?.toUpperCase() || 'U'}
                    </div>
                  )}
                </div>
                <div className="header__user-info">
                  <div className="header__user-name">{(currentUserData || userData).full_name || (currentUserData || userData).first_name || (currentUserData || userData).username}</div>
                  <div className="header__user-status">{getUserRole()}</div>
                </div>
                <button className="header__logout-btn" onClick={handleLogout} title={t('common.logout')}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <polyline points="16,17 21,12 16,7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            ) : (
              <button 
                className="header__auth-btn"
                onClick={() => setShowAuthModal(true)}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <polyline points="10,17 15,12 10,7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <line x1="15" y1="12" x2="3" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span>{t('common.login')}</span>
              </button>
            )}

            {/* Кнопка поддержки на одном уровне с иконкой */}
            <div className="header__support-btn" onClick={() => {
              if (isAuthenticated) setShowSupportModal(true); else setShowAuthModal(true);
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M22 2H2v8h20V2zM2 14h20v8H2v-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M6 6h.01M10 6h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>{t('common.support')}</span>
            </div>
          </div>
        </div>
      </div>

      <AuthModal 
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
        isDarkTheme={isDarkTheme}
      />
      <SupportModal isOpen={showSupportModal} onClose={() => setShowSupportModal(false)} />
    </header>
  );
};

export default Header; 


