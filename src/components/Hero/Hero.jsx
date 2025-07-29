import React from 'react';
import './Hero.scss';

const Hero = () => {
  return (
    <section className="hero">
      <div className="container">
        <div className="hero__content">
          <div className="hero__text">
            <h1 className="hero__title">
              Ваше здоровье - наш приоритет
            </h1>
            <p className="hero__subtitle">
              Современная медицинская платформа для качественного обслуживания
            </p>
            <p className="hero__description">
              Получите доступ к лучшим врачам, быстрой диагностике и современным методам лечения
            </p>
            <div className="hero__buttons">
              <button className="btn btn--primary">
                Найти врача
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button className="btn btn--outline">
                AI Диагностика
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
          
          <div className="hero__image">
            <div className="hero__image-container">
              <div className="hero__stats">
                <div className="hero__stat">
                  <div className="hero__stat-number">500+</div>
                  <div className="hero__stat-label">Врачей</div>
                </div>
                <div className="hero__stat">
                  <div className="hero__stat-number">50+</div>
                  <div className="hero__stat-label">Клиник</div>
                </div>
                <div className="hero__stat">
                  <div className="hero__stat-number">10k+</div>
                  <div className="hero__stat-label">Пациентов</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero; 