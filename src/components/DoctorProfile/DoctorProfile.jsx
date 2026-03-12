import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './DoctorProfile.scss';
import { useTranslation } from 'react-i18next';
import { translateSpec, translateLocation } from '../../utils/i18nMaps';

const DoctorProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doctor, setDoctor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAppointmentModal, setShowAppointmentModal] = useState(false);
  const [showConsultationModal, setShowConsultationModal] = useState(false);
  const [consultationData, setConsultationData] = useState({
    title: '',
    description: ''
  });
  const [creatingConsultation, setCreatingConsultation] = useState(false);
  const { t, i18n } = useTranslation();

  useEffect(() => {
    const fetchDoctorProfile = async () => {
      try {
        const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/doctors/${id}/`, {
          credentials: 'include'
        });
        
        if (response.ok) {
          const data = await response.json();
          setDoctor(data);
        } else {
          setError(t('doctorProfile.notFoundTitle'));
        }
      } catch (error) {
        setError(t('doctorsPage.errorServer'));
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchDoctorProfile();
    }
  }, [id]);

  const getSpecializationIcon = (specialization) => {
    const icons = {
      'Терапевт': '🩺',
      'Кардиолог': '❤️',
      'Невролог': '🧠',
      'Офтальмолог': '👁️',
      'Дерматолог': '🔬',
      'Ортопед': '🦴',
      'Ревматолог': '🦴',
      'Педиатр': '👶',
      'Гинеколог': '👩‍⚕️',
      'Уролог': '🔬',
      'Эндокринолог': '⚖️',
      'Психиатр': '🧠',
      'Хирург': '🔪',
      'Стоматолог': '🦷',
      'Физиотерапевт': '💪',
      'Массажист': '🤲',
      'Психолог': '🧘',
      'Диетолог': '🥗',
      'Спортивный врач': '🏃',
      'Гериатр': '👴'
    };
    
    return icons[specialization] || '👨‍⚕️';
  };

  const handleAppointment = () => {
    setShowAppointmentModal(true);
  };

  const closeAppointmentModal = () => {
    setShowAppointmentModal(false);
  };

  const handleConsultation = () => {
    setShowConsultationModal(true);
  };

  const closeConsultationModal = () => {
    setShowConsultationModal(false);
    setConsultationData({ title: '', description: '' });
  };

  const handleCreateConsultation = async (e) => {
    e.preventDefault();
    
    if (!consultationData.title.trim()) {
      alert(t('doctorProfile.topicRequired', 'Пожалуйста, укажите тему консультации'));
      return;
    }

    setCreatingConsultation(true);

    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/consultations/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({
          doctor_id: parseInt(id),
          title: consultationData.title,
          description: consultationData.description
        })
      });

      const data = await response.json();

      if (response.ok) {
        alert(t('doctorProfile.success'));
        closeConsultationModal();
        // Перенаправляем на страницу консультаций
        navigate('/consultations');
      } else {
        alert(data.error || t('doctorProfile.createError', 'Ошибка создания консультации'));
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    } finally {
      setCreatingConsultation(false);
    }
  };

  if (loading) {
    return (
      <div className="doctor-profile">
        <div className="doctor-profile__loading">
          <div className="loading-spinner"></div>
          <p>{t('doctorProfile.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="doctor-profile">
        <div className="doctor-profile__error">
          <h2>{t('doctorProfile.errorTitle')}</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/doctors')} className="doctor-profile__back-btn">
            {t('doctorProfile.backToList')}
          </button>
        </div>
      </div>
    );
  }

  if (!doctor) {
    return (
      <div className="doctor-profile">
        <div className="doctor-profile__error">
          <h2>{t('doctorProfile.notFoundTitle')}</h2>
          <p>{t('doctorProfile.notFoundText')}</p>
          <button onClick={() => navigate('/doctors')} className="doctor-profile__back-btn">
            {t('doctorProfile.backToList')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="doctor-profile">
      <div className="doctor-profile__container">
        {/* Кнопка назад */}
        <button onClick={() => navigate('/doctors')} className="doctor-profile__back-btn">
          {t('doctorProfile.backToList')}
        </button>

        {/* Основная информация */}
        <div className="doctor-profile__header">
          <div className="doctor-profile__avatar-section">
            <div className="doctor-profile__avatar">
              {doctor.avatar ? (
                <img src={doctor.avatar} alt={doctor.full_name} />
              ) : (
                <div className="doctor-profile__avatar-placeholder">
                  {doctor.first_name && doctor.last_name 
                    ? `${doctor.first_name[0]}${doctor.last_name[0]}`.toUpperCase()
                    : doctor.first_name?.[0]?.toUpperCase() || 'U'}
                </div>
              )}
            </div>
            <div className="doctor-profile__basic-info">
              <h1 className="doctor-profile__name">{doctor.full_name}</h1>
              <p className="doctor-profile__specialization">
                {getSpecializationIcon(doctor.specialization)} {translateSpec(doctor.specialization, i18n.language)}
              </p>
              {doctor.region && (
                <p className="doctor-profile__location">
                  📍 {doctor.city ? `${translateLocation(doctor.city, i18n.language)}, ${translateLocation(doctor.region, i18n.language)}` : translateLocation(doctor.region, i18n.language)}
                  {doctor.district && `, ${translateLocation(doctor.district, i18n.language)}`}
                </p>
              )}
              {doctor.license_number && (
                <p className="doctor-profile__license">
                  📋 Лицензия: {doctor.license_number}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Детальная информация */}
        <div className="doctor-profile__content">
          <div className="doctor-profile__main-info">
            {doctor.experience && (
              <div className="doctor-profile__section">
                <h2>{t('doctorProfile.workExperience')}</h2>
                <div className="doctor-profile__section-content">
                  <p>{doctor.experience}</p>
                </div>
              </div>
            )}

            {doctor.education && (
              <div className="doctor-profile__section">
                <h2>{t('doctorProfile.education')}</h2>
                <div className="doctor-profile__section-content">
                  <p>{doctor.education}</p>
                </div>
              </div>
            )}

            {doctor.languages && doctor.languages.length > 0 && (
              <div className="doctor-profile__section">
                <h2>{t('doctorProfile.languages')}</h2>
                <div className="doctor-profile__section-content">
                  <div className="doctor-profile__languages">
                    {doctor.languages.map((language, index) => (
                      <span key={index} className="doctor-profile__language-tag">
                        {language}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {doctor.additional_info && (
              <div className="doctor-profile__section">
                <h2>{t('doctorProfile.additionalInfo')}</h2>
                <div className="doctor-profile__section-content">
                  <p>{doctor.additional_info}</p>
                </div>
              </div>
            )}
          </div>

          {/* Боковая панель с контактами */}
          <div className="doctor-profile__sidebar">
            <div className="doctor-profile__contact-card">
              <h3>{t('doctorProfile.contacts')}</h3>
              {doctor.phone && (
                <div className="doctor-profile__contact-item">
                  <span className="doctor-profile__contact-label">{t('doctorProfile.phone')}</span>
                  <a href={`tel:${doctor.phone}`} className="doctor-profile__contact-value">
                    {doctor.phone}
                  </a>
                </div>
              )}
              {doctor.email && (
                <div className="doctor-profile__contact-item">
                  <span className="doctor-profile__contact-label">{t('doctorProfile.email')}</span>
                  <a href={`mailto:${doctor.email}`} className="doctor-profile__contact-value">
                    {doctor.email}
                  </a>
                </div>
              )}
              {doctor.address && (
                <div className="doctor-profile__contact-item">
                  <span className="doctor-profile__contact-label">{t('doctorProfile.address')}</span>
                  <span className="doctor-profile__contact-value">{doctor.address}</span>
                </div>
              )}
            </div>

            <div className="doctor-profile__action-card">
              <h3>{t('doctorProfile.contactDoctor')}</h3>
              <p>{t('doctorProfile.chooseMethod')}</p>
              <div className="doctor-profile__action-buttons">
                {doctor.phone && (
                  <a href={`tel:${doctor.phone}`} className="doctor-profile__call-btn">
                    {t('doctorProfile.call')}
                  </a>
                )}
                {doctor.email && (
                  <a href={`mailto:${doctor.email}`} className="doctor-profile__appointment-btn">
                    {t('doctorProfile.writeEmail')}
                  </a>
                )}
                <button 
                  onClick={handleConsultation}
                  className="doctor-profile__consultation-btn"
                >
                  {t('doctorProfile.startConsultation')}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Модальное окно записи на прием */}
      {showAppointmentModal && (
        <div className="appointment-modal">
          <div className="appointment-modal__overlay" onClick={closeAppointmentModal}></div>
          <div className="appointment-modal__content">
            <div className="appointment-modal__header">
              <h3>{t('doctorProfile.appointmentTitle')}</h3>
              <button onClick={closeAppointmentModal} className="appointment-modal__close">
                ✕
              </button>
            </div>
            <div className="appointment-modal__body">
              <p>{t('doctorProfile.appointmentSoon')}</p>
              <p>{t('doctorProfile.appointmentPhone')}</p>
              {doctor.phone && (
                <a href={`tel:${doctor.phone}`} className="appointment-modal__phone-btn">
                  {t('doctorProfile.call')} {doctor.phone}
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно создания консультации */}
      {showConsultationModal && (
        <div className="consultation-modal">
          <div className="consultation-modal__overlay" onClick={closeConsultationModal}></div>
          <div className="consultation-modal__content">
            <div className="consultation-modal__header">
              <h3>{t('doctorProfile.createConsultation')}</h3>
              <button onClick={closeConsultationModal} className="consultation-modal__close">
                ✕
              </button>
            </div>
            <div className="consultation-modal__body">
              <form onSubmit={handleCreateConsultation}>
                <div className="consultation-modal__form-group">
                  <label htmlFor="title" className="consultation-modal__label">{t('doctorProfile.topic')}</label>
                  <input
                    type="text"
                    id="title"
                    value={consultationData.title}
                    onChange={(e) => setConsultationData({...consultationData, title: e.target.value})}
                    className="consultation-modal__input"
                    placeholder={t('doctorProfile.topicPlaceholder')}
                    required
                  />
                </div>
                <div className="consultation-modal__form-group">
                  <label htmlFor="description" className="consultation-modal__label">{t('doctorProfile.description')}</label>
                  <textarea
                    id="description"
                    value={consultationData.description}
                    onChange={(e) => setConsultationData({...consultationData, description: e.target.value})}
                    className="consultation-modal__textarea"
                    placeholder={t('doctorProfile.descriptionPlaceholder')}
                    rows="4"
                  />
                </div>
                <div className="consultation-modal__actions">
                  <button 
                    type="button" 
                    onClick={closeConsultationModal}
                    className="consultation-modal__cancel-btn"
                  >
                    {t('common.cancel')}
                  </button>
                  <button 
                    type="submit" 
                    className="consultation-modal__submit-btn"
                    disabled={creatingConsultation}
                  >
                    {creatingConsultation ? t('doctorProfile.creating') : t('doctorProfile.create')}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DoctorProfile; 


