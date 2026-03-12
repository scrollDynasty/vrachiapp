import React, { useState, useEffect } from 'react';
import './Profile.scss';
import { useTranslation } from 'react-i18next';

const Profile = () => {
  const [userData, setUserData] = useState(null);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [regions, setRegions] = useState([]);
  const [cities, setCities] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [isEditingAvatar, setIsEditingAvatar] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState('');
  const [avatarFile, setAvatarFile] = useState(null);
  const { t } = useTranslation();

  const handleLogout = async () => {
    try {
      // Пытаемся завершить серверную сессию, если эндпоинт существует
      await fetch('https://vrachiapp-production.up.railway.app/api/auth/logout/', {
        method: 'POST',
        headers: { 'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '' },
        credentials: 'include'
      }).catch(() => {});
    } catch (_) {}
    // Чистим локальные данные и уходим на главную
    localStorage.removeItem('user');
    window.location.href = '/';
  };

  useEffect(() => {
    fetchUserData();
    fetchRegions();
  }, []);

  const fetchUserData = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/current-user/', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setUserData(data);
        setProfileData(data.profile);
        setFormData({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          phone: data.profile?.phone || '',
          date_of_birth: data.profile?.date_of_birth || '',
          gender: data.profile?.gender || '',
          region: data.profile?.region?.id || '',
          city: data.profile?.city?.id || '',
          district: data.profile?.district?.id || '',
          address: data.profile?.address || '',
          medical_info: data.profile?.medical_info || '',
          emergency_contact: data.profile?.emergency_contact || ''
        });
        setAvatarUrl(data.avatar || '');
        
        // Загружаем города и районы если есть регион
        if (data.profile?.region?.id) {
          await fetchCities(data.profile.region.id);
          await fetchDistricts(data.profile.region.id);
        }
      } else {
        setError(t('profile.loadError', 'Ошибка загрузки данных профиля'));
      }
    } catch (err) {
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
    } finally {
      setLoading(false);
    }
  };

  const fetchRegions = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/regions/');
      if (response.ok) {
        const data = await response.json();
        setRegions(data);
      }
    } catch (err) { }
  };

  const fetchCities = async (regionId) => {
    if (!regionId) {
      setCities([]);
      return;
    }
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/cities/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setCities(data);
        
        // Если у пользователя есть город, устанавливаем его
        if (userData?.profile?.city?.id) {
          setFormData(prev => ({
            ...prev,
            city: userData.profile.city.id
          }));
        }
      }
    } catch (err) { }
  };

  const fetchDistricts = async (regionId) => {
    if (!regionId) {
      setDistricts([]);
      return;
    }
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/districts/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setDistricts(data);
        
        // Если у пользователя есть район, устанавливаем его
        if (userData?.profile?.district?.id) {
          setFormData(prev => ({
            ...prev,
            district: userData.profile.district.id
          }));
        }
      }
    } catch (err) {
    }
  };

  const fetchDistrictsByCity = async (cityId) => {
    if (!cityId) {
      setDistricts([]);
      return;
    }
    try {
      // Сначала пытаемся найти районы конкретного города
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/districts/?city_id=${cityId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.length > 0) {
          // Если у города есть свои районы, показываем их
          setDistricts(data);
        } else {
          // Если у города нет своих районов, показываем районы региона
          if (formData.region) {
            fetchDistricts(formData.region);
          }
        }
      }
    } catch (err) {
      // В случае ошибки показываем районы региона
      if (formData.region) {
        fetchDistricts(formData.region);
      }
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Загружаем города при изменении региона
    if (name === 'region') {
      fetchCities(value);
      fetchDistricts(value);
      setFormData(prev => ({
        ...prev,
        city: '',
        district: ''
      }));
    }

    // Загружаем районы при изменении города
    if (name === 'city') {
      fetchDistrictsByCity(value);
      setFormData(prev => ({
        ...prev,
        district: ''
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/profile/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        const data = await response.json();
        setUserData(data);
        setIsEditing(false);
        setError(null);
      } else {
        const errorData = await response.json();
        setError(errorData.error || t('profile.saveError', 'Ошибка сохранения профиля'));
      }
    } catch (err) {
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarSubmit = async () => {
    if (!avatarFile) {
      setError(t('profile.pickAvatar', 'Пожалуйста, выберите файл аватарки'));
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('avatar', avatarFile);

      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/profile/', {
        method: 'PUT',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setUserData(data);
        setIsEditingAvatar(false);
        setAvatarFile(null);
        setError(null);
        // Обновляем данные в localStorage
        localStorage.setItem('user', JSON.stringify(data));
      } else {
        const errorData = await response.json();
        setError(errorData.error || t('profile.saveAvatarError', 'Ошибка сохранения аватарки'));
      }
    } catch (err) {
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="profile">
        <div className="profile__loading">
          <div className="loading-spinner"></div>
          <p>{t('profile.loading', 'Загрузка профиля...')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="profile">
        <div className="profile__error">
          <h2>{t('common.error', 'Ошибка')}</h2>
          <p>{error}</p>
          <button onClick={fetchUserData} className="btn btn--primary">
            {t('common.tryAgain', 'Попробовать снова')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile">
      <div className="profile__container">
        {/* Заголовок */}
        <div className="profile__header">
          <div className="profile__avatar">
            {userData?.avatar ? (
              <img src={userData.avatar} alt="Аватар" />
            ) : (
              <div className="profile__avatar-placeholder">
                {userData?.first_name && userData?.last_name 
                  ? `${userData.first_name[0]}${userData.last_name[0]}`.toUpperCase()
                  : userData?.first_name?.[0]?.toUpperCase() || 'U'}
              </div>
            )}
            {/* Кнопка редактирования аватарки для врачей */}
            {userData?.role === 'doctor' && (
              <button 
                className="profile__avatar-edit-btn"
                onClick={() => setIsEditingAvatar(true)}
                 title={t('profile.changeAvatar', 'Изменить аватарку')}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            )}
          </div>
          <div className="profile__info">
            <h1 className="profile__name">{userData?.full_name || t('profile.user', 'Пользователь')}</h1>
            <p className="profile__email">{userData?.email}</p>
            <div className="profile__role">
              <span className={`role-badge role-badge--${userData?.role}`}>
                 {userData?.role === 'patient' ? t('role.patient') : 
                  userData?.role === 'doctor' ? t('role.doctor') : t('role.admin')}
              </span>
            </div>
          </div>
          <div className="profile__actions">
            {/* Показываем кнопку редактирования только для пациентов и администраторов */}
            {userData?.role !== 'doctor' && (
              !isEditing ? (
                <button 
                  onClick={() => setIsEditing(true)}
                  className="btn btn--primary"
                >
                  {t('profile.edit', 'Редактировать')}
                </button>
              ) : (
                <div className="profile__edit-actions">
                  <button 
                    onClick={() => setIsEditing(false)}
                    className="btn btn--secondary"
                  >
                    {t('common.cancel', 'Отмена')}
                  </button>
                  <button 
                    onClick={handleSubmit}
                    className="btn btn--primary"
                    disabled={loading}
                  >
                    {loading ? t('profile.saving', 'Сохранение...') : t('common.save', 'Сохранить')}
                  </button>
                </div>
              )
            )}
            {userData?.role === 'doctor' && (
              <div className="profile__doctor-notice">
                <p>{t('profile.doctorNotice', 'Врачи могут изменять только аватарку. Остальные данные может изменить только администратор.')}</p>
              </div>
            )}
          </div>
        </div>

        {/* Форма профиля */}
        <div className="profile__content">
          <form onSubmit={handleSubmit} className="profile__form">
            <div className="profile__section">
              <h2 className="profile__section-title">{t('profile.mainInfo', 'Основная информация')}</h2>
              <div className="profile__form-grid">
                <div className="profile__form-group">
                  <label htmlFor="first_name">{t('profile.firstName', 'Имя')}</label>
                  <input
                    type="text"
                    id="first_name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  />
                </div>
                <div className="profile__form-group">
                  <label htmlFor="last_name">{t('profile.lastName', 'Фамилия')}</label>
                  <input
                    type="text"
                    id="last_name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  />
                </div>
                <div className="profile__form-group">
                  <label htmlFor="phone">{t('doctorProfile.phone', 'Телефон:').replace(':','')}</label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  />
                </div>
                <div className="profile__form-group">
                  <label htmlFor="date_of_birth">{t('profile.birthdate', 'Дата рождения')}</label>
                  <input
                    type="date"
                    id="date_of_birth"
                    name="date_of_birth"
                    value={formData.date_of_birth}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  />
                </div>
                <div className="profile__form-group">
                  <label htmlFor="gender">{t('profile.gender', 'Пол')}</label>
                  <select
                    id="gender"
                    name="gender"
                    value={formData.gender}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  >
                    <option value="">{t('profile.chooseGender', 'Выберите пол')}</option>
                    <option value="male">{t('profile.male', 'Мужской')}</option>
                    <option value="female">{t('profile.female', 'Женский')}</option>
                    <option value="other">{t('profile.other', 'Другой')}</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="profile__section">
              <h2 className="profile__section-title">{t('profile.address', 'Адрес')}</h2>
              <div className="profile__form-grid">
                <div className="profile__form-group">
                  <label htmlFor="region">{t('doctorsPage.region', 'Регион')}</label>
                  <select
                    id="region"
                    name="region"
                    value={formData.region}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                  >
                    <option value="">Выберите регион</option>
                    {regions.map(region => (
                      <option key={region.id} value={region.id}>
                        {region.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="profile__form-group">
                  <label htmlFor="city">{t('profile.city', 'Город')}</label>
                  <select
                    id="city"
                    name="city"
                    value={formData.city}
                    onChange={handleInputChange}
                    disabled={!isEditing || !formData.region}
                  >
                    <option value="">Выберите город</option>
                    {cities.map(city => (
                      <option key={city.id} value={city.id}>
                        {city.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="profile__form-group">
                  <label htmlFor="district">{t('profile.district', 'Район')}</label>
                  <select
                    id="district"
                    name="district"
                    value={formData.district}
                    onChange={handleInputChange}
                    disabled={!isEditing || !formData.region}
                  >
                    <option value="">Выберите район</option>
                    {districts.map(district => (
                      <option key={district.id} value={district.id}>
                        {district.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="profile__form-group profile__form-group--full">
                  <label htmlFor="address">{t('doctorProfile.address', 'Адрес:').replace(':','')}</label>
                  <textarea
                    id="address"
                    name="address"
                    value={formData.address}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    rows="3"
                  />
                </div>
              </div>
            </div>

            <div className="profile__section">
              <h2 className="profile__section-title">{t('profile.medInfo', 'Медицинская информация')}</h2>
              <div className="profile__form-grid">
                <div className="profile__form-group profile__form-group--full">
                  <label htmlFor="medical_info">{t('profile.medInfo', 'Медицинская информация')}</label>
                  <textarea
                    id="medical_info"
                    name="medical_info"
                    value={formData.medical_info}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    rows="4"
                    placeholder={t('profile.medInfoPlaceholder', 'Аллергии, хронические заболевания, принимаемые лекарства...')}
                  />
                </div>
                <div className="profile__form-group">
                  <label htmlFor="emergency_contact">{t('profile.emergency', 'Экстренный контакт')}</label>
                  <input
                    type="tel"
                    id="emergency_contact"
                    name="emergency_contact"
                    value={formData.emergency_contact}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    placeholder={t('profile.phoneMask', '+998 XX XXX XX XX')}
                  />
                </div>
              </div>
            </div>

            {/* Секция для врачей */}
            {userData?.role === 'doctor' && profileData && (
              <div className="profile__section">
                <h2 className="profile__section-title">{t('profile.doctorInfo', 'Информация врача')}</h2>
                <div className="profile__form-grid">
                  <div className="profile__form-group">
                     <label>{t('doctorsPage.specialization', 'Специализация')}</label>
                    <div className="profile__info-display">
                       {profileData.specialization || t('profile.notSpecified', 'Не указана')}
                    </div>
                  </div>
                  <div className="profile__form-group">
                     <label>{t('doctorProfile.license', 'Номер лицензии')}</label>
                    <div className="profile__info-display">
                       {profileData.license_number || t('profile.notSpecifiedM', 'Не указан')}
                    </div>
                  </div>
                  <div className="profile__form-group profile__form-group--full">
                     <label>{t('doctorProfile.education', '🎓 Образование')}</label>
                    <div className="profile__info-display">
                       {profileData.education || t('profile.notSpecifiedN', 'Не указано')}
                    </div>
                  </div>
                  <div className="profile__form-group profile__form-group--full">
                     <label>{t('doctorProfile.workExperience', '💼 Опыт работы')}</label>
                    <div className="profile__info-display">
                       {profileData.experience || t('profile.notSpecifiedM', 'Не указан')}
                    </div>
                  </div>
                  <div className="profile__form-group">
                     <label>{t('doctorProfile.languages', '🌍 Языки')}</label>
                    <div className="profile__info-display">
                       {profileData.languages && profileData.languages.length > 0 
                         ? profileData.languages.join(', ') 
                         : t('profile.notSpecifiedPlural', 'Не указаны')}
                    </div>
                  </div>
                  {profileData.additional_info && (
                    <div className="profile__form-group profile__form-group--full">
                       <label>{t('doctorProfile.additionalInfo', 'ℹ️ Дополнительная информация')}</label>
                      <div className="profile__info-display">
                        {profileData.additional_info}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Настройки / выход */}
            <div className="profile__section">
             <h2 className="profile__section-title">{t('profile.settings', 'Настройки')}</h2>
              <div className="profile__settings-actions">
                <button type="button" className="btn btn--secondary profile__logout-btn" onClick={handleLogout}>
                  {t('profile.logout', 'Выйти из аккаунта')}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Модальное окно для редактирования аватарки */}
      {isEditingAvatar && (
        <div className="profile__modal-overlay">
          <div className="profile__modal">
            <div className="profile__modal-header">
              <h3>{t('profile.changeAvatar', 'Изменить аватарку')}</h3>
              <button 
                className="profile__modal-close"
                onClick={() => {
                  setIsEditingAvatar(false);
                  setAvatarFile(null);
                }}
              >
                ×
              </button>
            </div>
            <div className="profile__modal-content">
              <div className="profile__form-group">
                <label htmlFor="avatar_file">{t('profile.chooseAvatar', 'Выберите файл аватарки')}</label>
                <input
                  type="file"
                  id="avatar_file"
                  accept="image/*"
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                      setAvatarFile(file);
                    }
                  }}
                />
                <small>{t('profile.avatarHint', 'Выберите изображение (JPG, PNG, GIF). Максимальный размер: 5MB')}</small>
              </div>
              <div className="profile__modal-actions">
                <button 
                  className="btn btn--secondary"
                  onClick={() => {
                    setIsEditingAvatar(false);
                    setAvatarFile(null);
                  }}
                >
                  {t('common.cancel', 'Отмена')}
                </button>
                <button 
                  className="btn btn--primary"
                  onClick={handleAvatarSubmit}
                  disabled={loading}
                >
                  {loading ? t('profile.saving', 'Сохранение...') : t('common.save', 'Сохранить')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile; 


