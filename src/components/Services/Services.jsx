import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Services.scss';
import { useTranslation } from 'react-i18next';

const Services = ({ onShowAllServices, onShowDoctors, userData }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const services = [
    // Медицинские услуги
    {
      id: 1,
      title: t('services.items.consultation.title'),
      description: t('services.items.consultation.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M12 2v20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12h20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.medical')
    },
    {
      id: 2,
      title: t('services.items.labs.title'),
      description: t('services.items.labs.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <polyline points="10,9 9,9 8,9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.medical')
    },
    {
      id: 3,
      title: t('services.items.usg.title'),
      description: t('services.items.usg.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M8 14s1.5 2 4 2 4-2 4-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="9" y1="9" x2="9.01" y2="9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="15" y1="9" x2="15.01" y2="9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.medical')
    },
    {
      id: 4,
      title: t('services.items.dentistry.title'),
      description: t('services.items.dentistry.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.medical')
    },
    // Спортивные и диетические услуги
    {
      id: 5,
      title: t('services.items.sports.title'),
      description: t('services.items.sports.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M6 4h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M6 1h3v4H6z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M15 1h3v4h-3z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M6 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M6 14h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M6 18h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.sportDiet')
    },
    {
      id: 6,
      title: t('services.items.diet.title'),
      description: t('services.items.diet.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M18 8h1a4 4 0 0 1 0 8h-1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="6" y1="1" x2="6" y2="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="10" y1="1" x2="10" y2="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="14" y1="1" x2="14" y2="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.sportDiet')
    },
    // Физиотерапия
    {
      id: 7,
      title: t('services.items.physio.title'),
      description: t('services.items.physio.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M12 2v20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.physio')
    },
    // Массаж
    {
      id: 8,
      title: t('services.items.massage.title'),
      description: t('services.items.massage.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.massage')
    },
    // Психологические консультации
    {
      id: 9,
      title: t('services.items.psycho.title'),
      description: t('services.items.psycho.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M8 9h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M8 13h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.psychology')
    },
    // Уход за пожилыми
    {
      id: 10,
      title: t('services.items.elderlyCare.title'),
      description: t('services.items.elderlyCare.description'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M12 2v20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12h20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
      category: t('services.categories.elderly')
    }
  ];

  const handleShowAllServices = () => {
    if (onShowAllServices) {
      onShowAllServices();
    }
  };

  const handleShowDoctors = () => {
    if (onShowDoctors && userData && userData.role === 'patient') {
      onShowDoctors();
    }
  };

  return (
    <section className="services">
      <div className="container">
        <div className="services__header">
          <h2 className="services__title">{t('services.title')}</h2>
          <p className="services__subtitle">{t('services.subtitle')}</p>
        </div>

        {/* Все услуги в одной сетке */}
        <div className="services__grid">
          {services.map((service) => (
            <div key={service.id} className="service-card">
              {userData && userData.role !== 'doctor' && (
                <div className="service-card__icon">
                  {service.icon}
                </div>
              )}
              <div className="service-card__content">
                <div className="service-card__category">{service.category}</div>
                <h3 className="service-card__title">{service.title}</h3>
                <p className="service-card__description">{service.description}</p>
                {userData && userData.role !== 'doctor' && (
                  <button className="service-card__btn" onClick={() => navigate('/services')}>
                    {t('common.readMore')}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Мобильная карусель */}
        <div className="services__carousel">
          <div className="services__carousel-container">
            <div className="services__carousel-track">
              <div className="services__carousel-slide">
                {services.map((service) => (
                  <div key={service.id} className="service-card">
                    {userData && userData.role !== 'doctor' && (
                      <div className="service-card__icon">
                        {service.icon}
                      </div>
                    )}
                    <div className="service-card__content">
                      <div className="service-card__category">{service.category}</div>
                      <h3 className="service-card__title">{service.title}</h3>
                      <p className="service-card__description">{service.description}</p>
                      {userData && userData.role !== 'doctor' && (
                        <button className="service-card__btn" onClick={() => navigate('/services')}>
                          {t('common.readMore')}
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                            <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="services__cta">
          {userData && userData.role !== 'doctor' && (
            <button className="btn btn--primary" onClick={() => navigate('/services')}>
              {t('common.allServices')}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
          {userData && userData.role === 'patient' && (
            <button className="btn btn--secondary" onClick={() => navigate('/doctors')}>
              {t('common.findDoctor')}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="8.5" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M20 8v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M23 11h-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
        </div>
      </div>
    </section>
  );
};

export default Services; 


