import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './MobileNav.scss';
import { useTranslation } from 'react-i18next';

const MobileNav = ({ isAuthenticated, userData, isDarkTheme, toggleTheme }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [activeItem, setActiveItem] = useState('home');
  const [consultationsStats, setConsultationsStats] = useState({
    active: 0,
    completed: 0,
    pending: 0
  });

  // Определяем текущую страницу на основе URL
  const getCurrentPage = () => {
    const path = location.pathname;
    if (path === '/') return 'home';
    if (path === '/doctors') return 'doctors';
    if (path.startsWith('/doctors/')) return 'doctors';
    if (path === '/services') return 'services';
    if (path === '/profile') return 'profile';
    if (path === '/admin') return 'admin';
    if (path === '/doctor-application') return 'doctor-application';
    if (path === '/consultations' || path.startsWith('/consultations/')) return 'consultations';

    return 'home';
  };

  // Синхронизируем activeItem с текущей страницей
  useEffect(() => {
    setActiveItem(getCurrentPage());
  }, [location.pathname]);

  // Загружаем статистику консультаций для авторизованных пользователей
  useEffect(() => {
    if (isAuthenticated) {
      fetchConsultationsStats();
    }
  }, [isAuthenticated]);

  const fetchConsultationsStats = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/consultations/', {
        credentials: 'include'
      });

      if (response.ok) {
        const consultations = await response.json();
        const stats = consultations.reduce((acc, consultation) => {
          acc[consultation.status] = (acc[consultation.status] || 0) + 1;
          return acc;
        }, {});

        setConsultationsStats({
          active: stats.active || 0,
          completed: stats.completed || 0,
          pending: stats.pending || 0
        });
      }
    } catch (error) { }
  };

  const handleItemClick = (itemId) => {
    setActiveItem(itemId);
    switch (itemId) {
      case 'home':
        navigate('/');
        break;
      case 'about':
        navigate('/about');
        break;
      case 'doctors':
        navigate('/doctors');
        break;
      case 'services':
        navigate('/services');
        break;
      case 'profile':
        navigate('/profile');
        break;
      case 'admin':
        navigate('/admin');
        break;
      case 'doctor-application':
        navigate('/doctor-application');
        break;
      case 'consultations':
        navigate('/consultations');
        break;
      case 'theme-toggle':
        toggleTheme();
        break;

      default:
        navigate('/');
    }
  };

  // Определяем роль пользователя
  const isAdmin = userData && (userData.is_staff || userData.is_superuser);
  const isDoctor = userData && userData.role === 'doctor';

  // Базовые пункты меню для всех пользователей
  const baseNavigationItems = [
    {
      id: 'home',
      label: t('common.home'),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <polyline points="9,22 9,12 15,12 15,22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 'theme-toggle',
      label: isDarkTheme ? t('common.themeLight') : t('common.themeDark'),
      icon: isDarkTheme ? (
        // Солнце для темной темы
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ) : (
        // Луна для светлой темы
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  ];

  // Пункты меню для обычных авторизованных пользователей (пациентов)
  const patientNavigationItems = [
    {
      id: 'doctors',
      label: t('common.doctors'),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="8.5" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M20 8v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M23 11h-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 'consultations',
      label: t('common.records'),
      badge: consultationsStats.active + consultationsStats.pending || 0,
      badgeType: consultationsStats.active > 0 ? 'active' : 'pending',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 'services',
      label: t('common.services'),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 'profile',
      label: t('common.profile'),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1 1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  ];

  // Пункты меню для администраторов
  const adminNavigationItems = [
    {
      id: 'admin',
      label: t('common.adminPanel'),
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="7" height="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="14" y="3" width="7" height="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="14" y="14" width="7" height="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="3" y="14" width="7" height="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  ];

  // Формируем итоговый список пунктов меню
  let navigationItems = [...baseNavigationItems];
  
  if (isAuthenticated) {
    if (isAdmin) {
      // Для администраторов показываем только админские пункты + главная и о нас
      navigationItems = [...navigationItems, ...adminNavigationItems];
    } else if (isDoctor) {
      // Для врачей показываем только базовые пункты + профиль + консультации (без пункта "Врачи")
      const doctorNavigationItems = patientNavigationItems.filter(item => item.id !== 'doctors');
      navigationItems = [...navigationItems, ...doctorNavigationItems];
    } else {
      // Для обычных пользователей (пациентов) показываем все пункты включая "Врачи"
      navigationItems = [...navigationItems, ...patientNavigationItems];
    }
  } else {
    // Для неавторизованных пользователей показываем только основные пункты
    navigationItems = navigationItems.filter(item => ['home', 'theme-toggle', 'services'].includes(item.id));
  }

  return (
    <nav className="mobile-nav">
      <div className="mobile-nav__container">
        {navigationItems.map((item) => (
          <div 
            key={item.id}
            data-id={item.id}
            className={`mobile-nav__item ${activeItem === item.id && item.id !== 'theme-toggle' ? 'mobile-nav__item--active' : ''}`}
            onClick={() => handleItemClick(item.id)}
          >
            <div className="mobile-nav__icon">
              {item.icon}
              {item.badge > 0 && (
                <span className={`mobile-nav__badge mobile-nav__badge--${item.badgeType}`}>
                  {item.badge}
                </span>
              )}
            </div>
            {activeItem === item.id && item.id !== 'theme-toggle' && (
              <span className="mobile-nav__text">{item.label}</span>
            )}
          </div>
        ))}
      </div>
    </nav>
  );
};

export default MobileNav; 


