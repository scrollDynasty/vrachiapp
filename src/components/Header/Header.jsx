import React, { useState } from 'react';
import healzyLogo from '../../assets/images/healzy.svg';
import AuthModal from '../AuthModal/AuthModal';
import './Header.scss';

const Header = ({ onPageChange, isAuthenticated, userData, onAuthSuccess, onLogout }) => {
  const [currentLanguage, setCurrentLanguage] = useState('RU');
  const [showAuthModal, setShowAuthModal] = useState(false);

  const handleLogoClick = () => {
    if (onPageChange) {
      onPageChange('home');
    }
  };

  const languages = [
    { code: 'RU', name: 'Русский' },
    { code: 'UZ', name: 'Узбекский' },
    { code: 'EN', name: 'Английский' }
  ];

  const handleAuthSuccess = (user) => {
    onAuthSuccess(user);
    setShowAuthModal(false);
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
              <span className="header__phone-number">1188</span>
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
                      const currentIndex = languages.findIndex(lang => lang.code === currentLanguage);
                      const nextIndex = (currentIndex + 1) % languages.length;
                      setCurrentLanguage(languages[nextIndex].code);
                    }}
                  >
                    {currentLanguage}
                  </button>
                </div>
              </div>
            </div>

            {/* Пользовательская секция */}
            {isAuthenticated && userData ? (
              <div className="header__user">
                <div className="header__user-avatar">
                  {userData.initials || userData.first_name?.[0] || 'U'}
                </div>
                <div className="header__user-info">
                  <div className="header__user-name">{userData.full_name || userData.first_name || userData.username}</div>
                  <div className="header__user-status">
                    {userData.is_staff ? 'Администратор' : userData.is_doctor ? 'Врач' : 'Пациент'}
                  </div>
                </div>
                <button className="header__logout-btn" onClick={onLogout} title="Выйти">
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
                <span>Войти</span>
              </button>
            )}

            {/* Кнопка поддержки */}
            <button className="header__support-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M22 2H2v8h20V2zM2 14h20v8H2v-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M6 6h.01M10 6h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>Поддержка</span>
            </button>
          </div>
        </div>
      </div>

      <AuthModal 
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
      />
    </header>
  );
};

export default Header; 