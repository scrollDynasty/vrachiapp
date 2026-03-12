import React, { useState, useEffect } from 'react';
import './DoctorApplication.scss';
import { useTranslation } from 'react-i18next';
import { translateLocation } from '../../utils/i18nMaps';
import { translateSpec } from '../../utils/i18nMaps';

const DoctorApplication = () => {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    service: 'all',
    specialization: '',
    region: '',
    city: '',
    district: '',
    languages: [],
    experience: '',
    education: '',
    license_number: '',
    additional_info: '',
    // Поля профиля
    date_of_birth: '',
    gender: '',
    phone: '',
    address: '',
    medical_info: '',
    emergency_contact: '',
    // Файлы
    photo: null,
    diploma: null,
    license: null
  });

  const [regions, setRegions] = useState([]);
  const [cities, setCities] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');
  const { t } = useTranslation();

  // Услуги и специализации как на странице врачей
  const serviceKeys = [
    'Медицинские услуги',
    'Спортивные и диетические',
    'Физиотерапия',
    'Массаж',
    'Психологические консультации',
    'Уход за пожилыми'
  ];
  const serviceKeyMap = {
    'Медицинские услуги': 'medical',
    'Спортивные и диетические': 'sportDiet',
    'Физиотерапия': 'physio',
    'Массаж': 'massage',
    'Психологические консультации': 'psychology',
    'Уход за пожилыми': 'elderly'
  };
  const services = ['all', ...serviceKeys];

  const specializationsByService = {
    'Медицинские услуги': [
      'Терапевт',
      'Кардиолог',
      'Невролог',
      'Офтальмолог',
      'Дерматолог',
      'Ортопед',
      'Ревматолог',
      'Педиатр',
      'Гинеколог',
      'Уролог',
      'Эндокринолог',
      'Психиатр',
      'Хирург',
      'Стоматолог',
      'Онколог',
      'Аллерголог',
      'Иммунолог',
      'Гастроэнтеролог',
      'Пульмонолог',
      'Нефролог',
      'Гематолог',
      'Инфекционист',
      'Травматолог',
      'Анестезиолог',
      'Реаниматолог'
    ],
    'Спортивные и диетические': [
      'Спортивный врач',
      'Диетолог'
    ],
    'Физиотерапия': [
      'Физиотерапевт'
    ],
    'Массаж': [
      'Массажист'
    ],
    'Психологические консультации': [
      'Психолог',
      'Психиатр'
    ],
    'Уход за пожилыми': [
      'Гериатр'
    ]
  };

  const languages = [
    { code: 'ru', name: 'Русский' },
    { code: 'uz', name: 'Узбекский' },
    { code: 'en', name: 'Английский' },
    { code: 'kz', name: 'Казахский' },
    { code: 'ky', name: 'Киргизский' },
    { code: 'tg', name: 'Таджикский' },
    { code: 'tk', name: 'Туркменский' }
  ];

  useEffect(() => {
    loadRegions();
  }, []);

  const loadRegions = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/regions/');
      if (response.ok) {
        const data = await response.json();
        setRegions(data);
      }
    } catch (error) {
    }
  };

  const loadCities = async (regionId) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/cities/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setCities(data);
      }
    } catch (error) {
    }
  };

  const loadDistricts = async (regionId) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/districts/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setDistricts(data);
      }
    } catch (error) {
    }
  };

  const loadDistrictsByCity = async (cityId) => {
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
            loadDistricts(formData.region);
          }
        }
      }
    } catch (error) {
      // В случае ошибки показываем районы региона
      if (formData.region) {
        loadDistricts(formData.region);
      }
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Смена услуги — сбрасываем специализацию
    if (name === 'service') {
      setFormData(prev => ({
        ...prev,
        specialization: ''
      }));
    }

    // Если изменился регион, загружаем города и районы
    if (name === 'region' && value) {
      loadCities(value);
      loadDistricts(value);
      // Очищаем город и район при смене региона
      setFormData(prev => ({
        ...prev,
        city: '',
        district: ''
      }));
    }
    
    // Если изменился город, загружаем районы для этого города
    if (name === 'city' && value) {
      loadDistrictsByCity(value);
      // Очищаем выбранный район
      setFormData(prev => ({
        ...prev,
        district: ''
      }));
    }
  };

  const handleLanguageChange = (e) => {
    const languageCode = e.target.value;
    setFormData(prev => ({
      ...prev,
      languages: prev.languages.includes(languageCode)
        ? prev.languages.filter(lang => lang !== languageCode)
        : [...prev.languages, languageCode]
    }));
  };

  const handleFileChange = (e, field) => {
    const file = e.target.files[0];
    if (file) {
      setFormData(prev => ({
        ...prev,
        [field]: file
      }));
    }
  };

  const showMessage = (text, type = 'success') => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const formDataToSend = new FormData();

      // Добавляем все поля формы
      Object.keys(formData).forEach(key => {
        if (key === 'languages') {
          formDataToSend.append(key, JSON.stringify(formData[key]));
        } else if (key === 'region' || key === 'city' || key === 'district') {
          // Для региона, города и района отправляем ID
          if (formData[key]) {
            formDataToSend.append(key, formData[key]);
          }
        } else if (key === 'date_of_birth' && formData[key]) {
          // Форматируем дату
          formDataToSend.append(key, formData[key]);
        } else if (
          formData[key] !== null &&
          formData[key] !== '' &&
          key !== 'photo' &&
          key !== 'diploma' &&
          key !== 'license' &&
          key !== 'service'
        ) {
          formDataToSend.append(key, formData[key]);
        }
      });

      // Добавляем файлы
      if (formData.photo) formDataToSend.append('photo', formData.photo);
      if (formData.diploma) formDataToSend.append('diploma', formData.diploma);
      if (formData.license) formDataToSend.append('license', formData.license);


      const csrfToken = (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '';
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken
        },
        credentials: 'include',
        body: formDataToSend
      });

      if (response.ok) {
        const result = await response.json();
        showMessage(result.message || 'Заявка успешно отправлена!');
        setFormData({
          first_name: '',
          last_name: '',
          service: 'all',
          specialization: '',
          region: '',
          city: '',
          district: '',
          languages: [],
          experience: '',
          education: '',
          license_number: '',
          additional_info: '',
          // Поля профиля
          date_of_birth: '',
          gender: '',
          phone: '',
          address: '',
          medical_info: '',
          emergency_contact: '',
          // Файлы
          photo: null,
          diploma: null,
          license: null
        });
      } else {
        const error = await response.json();
        showMessage(error.message || 'Ошибка отправки заявки', 'error');
      }
    } catch (error) {
      showMessage('Ошибка соединения с сервером', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="doctor-application">
      {message && (
        <div className={`doctor-application__message ${messageType}`}>
          {message}
        </div>
      )}

      <div className="doctor-application__content">
        <div className="doctor-application__header">
          <h1>{t('doctorApplication.title', 'Подача заявки на роль врача')}</h1>
          <p>{t('doctorApplication.subtitle', 'Заполните форму ниже, чтобы стать врачом в нашей системе. Мы рассмотрим вашу заявку в течение 1-3 рабочих дней.')}</p>
        </div>

        <form className="doctor-application__form" onSubmit={handleSubmit}>
          <div className="doctor-application__section">
            <h3 className="doctor-application__section-title">{t('doctorApplication.sectionData', 'Данные для заявки')}</h3>
            <p className="doctor-application__section-subtitle">{t('doctorApplication.sectionDataSub', 'Заполните форму ниже и предоставьте необходимые документы')}</p>
            
            <div className="doctor-application__form-row">
              <div className="doctor-application__form-group">
                <label htmlFor="first_name" className="required">{t('profile.firstName', 'Имя')}</label>
                <input
                  type="text"
                  id="first_name"
                  name="first_name"
                  value={formData.first_name}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__input"
                  placeholder={t('doctorApplication.placeholderFirst', 'Иван')}
                />
              </div>
              
              <div className="doctor-application__form-group">
                <label htmlFor="last_name" className="required">{t('profile.lastName', 'Фамилия')}</label>
                <input
                  type="text"
                  id="last_name"
                  name="last_name"
                  value={formData.last_name}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__input"
                  placeholder={t('doctorApplication.placeholderLast', 'Иванов')}
                />
              </div>
            </div>

            <div className="doctor-application__form-row">
              <div className="doctor-application__form-group">
                <label htmlFor="service" className="required">{t('doctorsPage.service', 'Услуга')}</label>
                <select
                  id="service"
                  name="service"
                  value={formData.service}
                  onChange={handleInputChange}
                  className="doctor-application__select"
                >
                  {services.map(service => (
                    <option key={service} value={service}>
                      {service === 'all' ? t('doctorApplication.chooseService', 'Выберите услугу') : t(`services.categories.${serviceKeyMap[service]}`)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="doctor-application__form-group">
                <label htmlFor="specialization" className="required">{t('doctorsPage.specialization', 'Специализация')}</label>
                <select
                  id="specialization"
                  name="specialization"
                  value={formData.specialization}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__select"
                  disabled={formData.service === 'all'}
                >
                  <option value="">{t('doctorApplication.chooseSpecialization', 'Выберите специализацию')}</option>
                  {formData.service !== 'all' && specializationsByService[formData.service]?.map(spec => (
                    <option key={spec} value={spec}>
                      {translateSpec(
                        spec,
                        (typeof window !== 'undefined' && localStorage.getItem('i18nextLng')) || 'ru'
                      )}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="doctor-application__form-row">
              <div className="doctor-application__form-group">
                <label htmlFor="region" className="required">{t('doctorsPage.region', 'Регион')}</label>
                <select
                  id="region"
                  name="region"
                  value={formData.region}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__select"
                >
                  <option value="">{t('doctorApplication.chooseRegion', 'Выберите регион')}</option>
                  {regions.map(region => (
                    <option key={region.id} value={region.id}>
                      {translateLocation(region.name, (typeof window !== 'undefined' && localStorage.getItem('i18nextLng')) || 'ru')}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="doctor-application__form-group">
                <label htmlFor="city" className="required">{t('profile.city', 'Город')}</label>
                <select
                  id="city"
                  name="city"
                  value={formData.city}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__select"
                  disabled={!formData.region}
                >
                  <option value="">{t('doctorApplication.chooseCity', 'Выберите город')}</option>
                  {cities.map(city => (
                    <option key={city.id} value={city.id}>
                      {translateLocation(city.name, (typeof window !== 'undefined' && localStorage.getItem('i18nextLng')) || 'ru')}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="doctor-application__form-group">
                <label htmlFor="district" className="required">{t('doctorApplication.district', 'Район практики')}</label>
                <select
                  id="district"
                  name="district"
                  value={formData.district}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__select"
                  disabled={!formData.region}
                >
                  <option value="">{t('doctorApplication.chooseDistrict', 'Выберите район')}</option>
                  {districts.map(district => (
                    <option key={district.id} value={district.id}>
                      {translateLocation(district.name, (typeof window !== 'undefined' && localStorage.getItem('i18nextLng')) || 'ru')}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="doctor-application__form-row">
              <div className="doctor-application__form-group">
                <label htmlFor="phone" className="required">{t('doctorProfile.phone', 'Телефон:').replace(':','')}</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleInputChange}
                  required
                  className="doctor-application__input"
                  placeholder={t('profile.phoneMask', '+998 XX XXX XX XX')}
                />
              </div>
              
              <div className="doctor-application__form-group">
                <label htmlFor="date_of_birth">{t('profile.birthdate', 'Дата рождения')}</label>
                <input
                  type="date"
                  id="date_of_birth"
                  name="date_of_birth"
                  value={formData.date_of_birth}
                  onChange={handleInputChange}
                  className="doctor-application__input"
                />
              </div>
              
              <div className="doctor-application__form-group">
                <label htmlFor="gender">{t('profile.gender', 'Пол')}</label>
                <select
                  id="gender"
                  name="gender"
                  value={formData.gender}
                  onChange={handleInputChange}
                  className="doctor-application__select"
                >
                  <option value="">{t('profile.chooseGender', 'Выберите пол')}</option>
                  <option value="male">{t('profile.male', 'Мужской')}</option>
                  <option value="female">{t('profile.female', 'Женский')}</option>
                  <option value="other">{t('profile.other', 'Другой')}</option>
                </select>
              </div>
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="address">{t('doctorProfile.address', 'Адрес:').replace(':','')}</label>
              <textarea
                id="address"
                name="address"
                value={formData.address}
                onChange={handleInputChange}
                className="doctor-application__textarea"
                  placeholder={t('doctorApplication.fullAddress', 'Введите полный адрес')}
                rows="3"
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="medical_info">{t('profile.medInfo', 'Медицинская информация')}</label>
              <textarea
                id="medical_info"
                name="medical_info"
                value={formData.medical_info}
                onChange={handleInputChange}
                className="doctor-application__textarea"
                  placeholder={t('doctorApplication.medInfoPlaceholder', 'Информация о заболеваниях, аллергиях и т.д.')}
                rows="3"
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="emergency_contact">{t('profile.emergency', 'Экстренный контакт')}</label>
              <input
                type="tel"
                id="emergency_contact"
                name="emergency_contact"
                value={formData.emergency_contact}
                onChange={handleInputChange}
                className="doctor-application__input"
                placeholder="+998 XX XXX XX XX"
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="languages" className="required">{t('doctorApplication.languages', 'Языки консультаций')}</label>
              <div className="doctor-application__checkbox-group">
                {['ru', 'uz', 'en'].map(lang => (
                  <label key={lang} className="doctor-application__checkbox">
                    <input
                      type="checkbox"
                      value={lang}
                      checked={formData.languages.includes(lang)}
                      onChange={handleLanguageChange}
                    />
                    <span className="doctor-application__checkbox-text">
                      {lang === 'ru' ? t('language.ru', 'Русский') : lang === 'uz' ? t('language.uz', 'Узбекский') : t('language.en', 'Английский')}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="experience" className="required">{t('doctorProfile.workExperience', '💼 Опыт работы')}</label>
              <textarea
                id="experience"
                name="experience"
                value={formData.experience}
                onChange={handleInputChange}
                required
                className="doctor-application__textarea"
                  placeholder={t('doctorApplication.experiencePlaceholder', 'Опишите ваш опыт работы в медицине')}
                rows="4"
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="education" className="required">{t('doctorProfile.education', '🎓 Образование')}</label>
              <textarea
                id="education"
                name="education"
                value={formData.education}
                onChange={handleInputChange}
                required
                className="doctor-application__textarea"
                  placeholder={t('doctorApplication.educationPlaceholder', 'Укажите ваше медицинское образование')}
                rows="4"
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="license_number" className="required">{t('doctorProfile.license', 'Номер лицензии')}</label>
              <input
                type="text"
                id="license_number"
                name="license_number"
                value={formData.license_number}
                onChange={handleInputChange}
                required
                className="doctor-application__input"
                  placeholder={t('doctorApplication.licensePlaceholder', 'Введите номер лицензии')}
              />
            </div>

            <div className="doctor-application__form-group">
                <label htmlFor="additional_info">{t('doctorProfile.additionalInfo', 'ℹ️ Дополнительная информация')}</label>
              <textarea
                id="additional_info"
                name="additional_info"
                value={formData.additional_info}
                onChange={handleInputChange}
                className="doctor-application__textarea"
                  placeholder={t('doctorApplication.additionalPlaceholder', 'Любая дополнительная информация о вас')}
                rows="4"
              />
            </div>
          </div>

          <div className="doctor-application__section">
            <h3 className="doctor-application__section-title">{t('doctorApplication.uploadTitle', 'Загрузка документов')}</h3>
            <p className="doctor-application__section-subtitle">{t('doctorApplication.uploadSubtitle', 'Загрузите необходимые документы для подтверждения вашей квалификации')}</p>
            
            <div className="doctor-application__file-section">
              <div className="doctor-application__file-group">
                <label className="doctor-application__file-label required">{t('doctorApplication.photo', 'Фотография')}</label>
                <div className={`doctor-application__file-upload ${formData.photo ? 'has-file' : ''}`}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => handleFileChange(e, 'photo')}
                    className="doctor-application__file-input"
                    required
                  />
                  <div className="doctor-application__file-placeholder">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <polyline points="7,10 12,15 17,10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>{t('doctorApplication.clickToUpload', 'Нажмите для загрузки')}</span>
                    <small>{t('doctorApplication.photoHint', 'Фото для профиля')}</small>
                  </div>
                </div>
                {formData.photo && (
                  <div className="doctor-application__file-preview">
                    <img src={URL.createObjectURL(formData.photo)} alt="Preview" />
                    <div className="file-name">{formData.photo.name}</div>
                  </div>
                )}
              </div>

              <div className="doctor-application__file-group">
                <label className="doctor-application__file-label required">{t('doctorApplication.diploma', 'Скан диплома')}</label>
                <div className={`doctor-application__file-upload ${formData.diploma ? 'has-file' : ''}`}>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(e) => handleFileChange(e, 'diploma')}
                    className="doctor-application__file-input"
                    required
                  />
                  <div className="doctor-application__file-placeholder">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>{t('doctorApplication.clickToUpload', 'Нажмите для загрузки')}</span>
                    <small>{t('doctorApplication.pdfHint', 'PDF, JPG или PNG')}</small>
                  </div>
                </div>
                {formData.diploma && (
                  <div className="doctor-application__file-preview">
                    <div className="file-name">{formData.diploma.name}</div>
                  </div>
                )}
              </div>

              <div className="doctor-application__file-group">
                <label className="doctor-application__file-label required">{t('doctorApplication.license', 'Скан лицензии')}</label>
                <div className={`doctor-application__file-upload ${formData.license ? 'has-file' : ''}`}>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={(e) => handleFileChange(e, 'license')}
                    className="doctor-application__file-input"
                    required
                  />
                  <div className="doctor-application__file-placeholder">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span>{t('doctorApplication.clickToUpload', 'Нажмите для загрузки')}</span>
                    <small>{t('doctorApplication.pdfHint', 'PDF, JPG или PNG')}</small>
                  </div>
                </div>
                {formData.license && (
                  <div className="doctor-application__file-preview">
                    <div className="file-name">{formData.license.name}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="doctor-application__actions">
            <button
              type="submit"
              className="doctor-application__submit"
              disabled={loading}
            >
              {loading ? t('doctorApplication.sending', 'Отправка...') : t('doctorApplication.submit', 'Отправить заявку')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DoctorApplication; 


