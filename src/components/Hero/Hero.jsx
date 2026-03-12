import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Hero.scss';
import { useTranslation } from 'react-i18next';

const Hero = () => {
  const navigate = useNavigate();

  const { t } = useTranslation();
  const handleFindDoctor = () => {
    navigate('/doctors');
  };

  const handleAIDiagnosis = () => {
    navigate('/ai-diagnosis');
  };

  return (
    <section className="hero">
      <div className="container">
        <div className="hero__content">
          <div className="hero__text">
            <h1 className="hero__title">{t('hero.title')}</h1>
            <p className="hero__subtitle">{t('hero.subtitle')}</p>
            <p className="hero__description">{t('hero.description')}</p>
            <div className="hero__buttons">
              <button className="btn btn--primary" onClick={handleFindDoctor}>
                {t('common.findDoctor')}
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button className="btn btn--outline" onClick={handleAIDiagnosis}>
                {t('common.aiDiagnosis')}
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
                  <div className="hero__stat-label">{t('hero.statsDoctors')}</div>
                </div>
                <div className="hero__stat">
                  <div className="hero__stat-number">50+</div>
                  <div className="hero__stat-label">{t('hero.statsClinics')}</div>
                </div>
                <div className="hero__stat">
                  <div className="hero__stat-number">10k+</div>
                  <div className="hero__stat-label">{t('hero.statsPatients')}</div>
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


