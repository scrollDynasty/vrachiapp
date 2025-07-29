import React, { useState } from 'react';
import healzyLogo from '../../assets/images/healzy.svg';
import './Header.scss';

const Header = () => {
  const [currentLanguage, setCurrentLanguage] = useState('RU');
  const [isLoggedIn] = useState(true); // Тестовые данные - пользователь авторизован

  const languages = [
    { code: 'RU', name: 'Русский' },
    { code: 'UZ', name: 'Узбекский' },
    { code: 'EN', name: 'Английский' }
  ];

  const userData = {
    name: 'Матёкубов Умар',
    status: 'Пациент',
    avatar: 'Y' // Первая буква имени для аватара
  };

  return (
    <header className="header">
      <div className="container">
        <div className="header__content">
          <div className="header__logo">
            <div className="header__logo-container">
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
            {isLoggedIn && (
              <div className="header__user">
                <div className="header__user-avatar">
                  {userData.avatar}
                </div>
                <div className="header__user-info">
                  <div className="header__user-name">{userData.name}</div>
                  <div className="header__user-status">{userData.status}</div>
                </div>
              </div>
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
    </header>
  );
};

export default Header; 