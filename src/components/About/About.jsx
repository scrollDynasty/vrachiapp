import React from 'react';
import './About.scss';
import { useTranslation } from 'react-i18next';

const About = () => {
  const { t } = useTranslation();
  const commitments = [
    {
      id: 1,
      title: t('about.commit1.title', 'Мы верим в правильные поступки'),
      description: t('about.commit1.desc', 'Мы верим в правильные поступки — всегда. Для вашего здоровья, ваших данных и вашего спокойствия.'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <polyline points="22,4 12,14.01 9,11.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 2,
      title: t('about.commit2.title', 'Мы делаем здравоохранение доступным для всех'),
      description: t('about.commit2.desc', 'Мы делаем качественное здравоохранение доступным для всех — независимо от того, кто вы и где находитесь.'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="9" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 3,
      title: t('about.commit3.title', 'Мы ставим вас в центр всего'),
      description: t('about.commit3.desc', 'Ваши потребности, ваши цели и ваш комфорт — вот что движет каждым решением, которое мы принимаем.'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="12" cy="10" r="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 4,
      title: t('about.commit4.title', 'Мы никогда не прекращаем совершенствоваться'),
      description: t('about.commit4.desc', 'Здравоохранение развивается. И мы тоже. Мы постоянно учимся, растем и адаптируемся для лучшего обслуживания.'),
      icon: (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M12 2v20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  ];

  const values = [
    {
      id: 1,
      title: t('about.values.care', 'Безграничная забота'),
      icon: (
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 2,
      title: t('about.values.community', 'Сообщество'),
      icon: (
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="9" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    {
      id: 3,
      title: t('about.values.innovation', 'Инновации'),
      icon: (
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    }
  ];

  return (
    <div className="about">
      <div className="container">
        {/* Заголовок */}
        <div className="about__header">
          <h1 className="about__title">{t('footer.about', 'О нас')}</h1>
          <p className="about__subtitle">
            {t('about.header', 'Мы верим, что доступ к качественному здравоохранению — это не привилегия, а основное право человека. Каждый, везде, заслуживает возможности понимать, отслеживать и улучшать свое здоровье — в любое время, в любом месте.')}
          </p>
        </div>

        {/* Наше видение */}
        <section className="about__section">
          <div className="about__section-content">
            <h2 className="about__section-title">{t('about.visionTitle', 'Наше видение')}</h2>
            <div className="about__vision-text">
              <p>{t('about.vision1', 'Мы создаем мир, где здравоохранение не знает границ. Мир, где забота о здоровье так же естественна и проста, как дыхание. Где экспертная медицинская помощь находится всего в одном клике — независимо от того, кто вы и где живете.')}</p>
              <p>{t('about.vision2', 'Это здравоохранение, созданное заново: персональное, интеллектуальное и человечное. Мы упрощаем понимание здравоохранения. И делаем все это, ставя вашу конфиденциальность, безопасность и уверенность в центр.')}</p>
              <p>{t('about.vision3', 'Мы создаем не просто инструмент. Мы строим движение — где каждое сердцебиение имеет значение, каждый человек замечен, и ни один вопрос не остается без ответа.')}</p>
            </div>
          </div>
        </section>

        {/* Наши ценности */}
        <section className="about__section">
          <h2 className="about__section-title">{t('about.valuesTitle', 'Наши ценности')}</h2>
          <div className="about__values">
            {values.map((value) => (
              <div key={value.id} className="about__value">
                <div className="about__value-icon">
                  {value.icon}
                </div>
                <h3 className="about__value-title">{value.title}</h3>
              </div>
            ))}
          </div>
        </section>

        {/* Наши обязательства */}
        <section className="about__section">
          <div className="about__section-content">
            <h2 className="about__section-title">{t('about.commitmentsTitle', 'Наши обязательства')}</h2>
            <p className="about__commitment-intro">{t('about.commitmentsIntro', 'Мы стремимся создать бесшовный опыт — построенный с эмпатией, руководимый инновациями и сформированный вокруг реальных человеческих потребностей. Потому что для нас здравоохранение — это не просто услуга. Это связь. Обязательство. Общая ответственность.')}</p>
            <div className="about__commitment-footer">
              <p className="about__commitment-quote">
                <strong>{t('about.yourHealth', 'Это ваше здоровье. Это ваш момент.')}</strong><br />
                {t('about.withYou', 'И мы здесь, на каждом шаге пути.')}
              </p>
            </div>
          </div>
        </section>

        {/* За что мы выступаем */}
        <section className="about__section">
          <h2 className="about__section-title">{t('about.whatWeStandFor', 'За что мы выступаем')}</h2>
          <div className="about__commitments">
            {commitments.map((commitment) => (
              <div key={commitment.id} className="about__commitment">
                <div className="about__commitment-icon">
                  {commitment.icon}
                </div>
                <div className="about__commitment-content">
                  <h3 className="about__commitment-title">{commitment.title}</h3>
                  <p className="about__commitment-description">{commitment.description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Заключение */}
        <section className="about__section about__section--conclusion">
          <div className="about__conclusion">
            <h2 className="about__conclusion-title">
              {t('about.conclusionTitle', 'Мы здесь, чтобы изменить то, как мир воспринимает здравоохранение')}
            </h2>
            <p className="about__conclusion-subtitle">
              {t('about.conclusionSubtitle', 'Не только для сегодня, но и для завтра.')}
            </p>
            <div className="about__conclusion-signature">
              <p>
                <strong>{t('about.signature', 'С вами. С сердцем. Без границ.')}</strong>
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default About; 


