import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './Doctors.scss';
import { useTranslation } from 'react-i18next';
import { translateSpec, translateLocation } from '../../utils/i18nMaps';

const Doctors = () => {
  const [doctors, setDoctors] = useState([]);
  const [filteredDoctors, setFilteredDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedService, setSelectedService] = useState('all');
  const [selectedSpecialization, setSelectedSpecialization] = useState('all');
  const [selectedRegion, setSelectedRegion] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [userData, setUserData] = useState(null);
  const { t, i18n } = useTranslation();



  // Услуги для фильтрации (значения-ключи, отображаем переводы по ключу)
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

  // Специализации, сгруппированные по услугам
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

  // Регионы для фильтрации (значения — русские ключи, метки переводим)
  const regionKeys = [
    'Ташкентская область',
    'Город Ташкент',
    'Самаркандская область',
    'Город Самарканд',
    'Бухарская область',
    'Город Бухара',
    'Ферганская область',
    'Андижанская область',
    'Наманганская область',
    'Кашкадарьинская область',
    'Сурхандарьинская область',
    'Сырдарьинская область',
    'Джизакская область',
    'Навоийская область',
    'Хорезмская область',
    'Республика Каракалпакстан'
  ];

  useEffect(() => {
    // Получаем данные пользователя
    const fetchUserData = async () => {
      try {
        const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/current-user/', {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setUserData(data);
          
          // Загружаем врачей только если пользователь - пациент
          if (data.role === 'patient') {
            fetchDoctors();
          } else {
            setLoading(false);
            setError(t('doctorsPage.accessDeniedTitle'));
          }
        } else {
          setLoading(false);
          setError(t('doctorsPage.errorUser'));
        }
      } catch (error) {
        setLoading(false);
        setError(t('doctorsPage.errorServer'));
      }
    };
    
    fetchUserData();
  }, []);

  useEffect(() => {
    filterDoctors();
  }, [doctors, selectedService, selectedSpecialization, selectedRegion, searchQuery]);

  // Сброс специализации при изменении услуги
  useEffect(() => {
    if (selectedService === 'all') {
      setSelectedSpecialization('all');
    } else {
      setSelectedSpecialization('all');
    }
  }, [selectedService]);

  // Сброс региона при изменении специализации
  useEffect(() => {
    if (selectedSpecialization === 'all') {
      setSelectedRegion('all');
    }
  }, [selectedSpecialization]);

  const resetFilters = () => {
    setSelectedService('all');
    setSelectedSpecialization('all');
    setSelectedRegion('all');
    setSearchQuery('');
  };



  const fetchDoctors = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/doctors/', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setDoctors(data);
        setFilteredDoctors(data);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Ошибка загрузки врачей');
      }
    } catch (error) {
      setError('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const filterDoctors = () => {
    let filtered = [...doctors];

    // Фильтр по услугам (первый уровень)
    if (selectedService !== 'all') {
      const serviceSpecializations = specializationsByService[selectedService];
      if (serviceSpecializations) {
        filtered = filtered.filter(doctor => 
          doctor.specialization && 
          serviceSpecializations.some(spec => 
            doctor.specialization.toLowerCase() === spec.toLowerCase()
          )
        );
      }
    }

    // Фильтр по специализации (второй уровень)
    if (selectedSpecialization !== 'all') {
      filtered = filtered.filter(doctor => 
        doctor.specialization && 
        doctor.specialization.toLowerCase() === selectedSpecialization.toLowerCase()
      );
    }

    // Фильтр по региону (третий уровень)
    if (selectedRegion !== 'all') {
      filtered = filtered.filter(doctor => {
        // Проверяем, совпадает ли регион врача с выбранным регионом
        if (doctor.region && doctor.region.toLowerCase().includes(selectedRegion.toLowerCase())) {
          return true;
        }
        
        // Проверяем, находится ли город врача в выбранном регионе
        if (doctor.city) {
          const cityRegionMap = {
            'Фергана': 'Ферганская область',
            'Андижан': 'Андижанская область',
            'Наманган': 'Наманганская область',
            'Ташкент': 'Город Ташкент',
            'Самарканд': 'Город Самарканд',
            'Бухара': 'Город Бухара',
            'Карши': 'Кашкадарьинская область',
            'Термез': 'Сурхандарьинская область',
            'Гулистан': 'Сырдарьинская область',
            'Джизак': 'Джизакская область',
            'Навои': 'Навоийская область',
            'Ургенч': 'Хорезмская область',
            'Нукус': 'Республика Каракалпакстан'
          };
          
          const cityRegion = cityRegionMap[doctor.city];
          if (cityRegion && cityRegion.toLowerCase().includes(selectedRegion.toLowerCase())) {
            return true;
          }
        }
        
        return false;
      });
    }

    // Поиск по имени (работает независимо от фильтров)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(doctor => {
        // Поиск по имени
        if (doctor.full_name.toLowerCase().includes(query)) {
          return true;
        }
        
        // Поиск по специализации
        if (doctor.specialization && doctor.specialization.toLowerCase().includes(query)) {
          return true;
        }
        
        // Поиск по городу
        if (doctor.city && doctor.city.toLowerCase().includes(query)) {
          return true;
        }
        
        // Поиск по региону
        if (doctor.region && doctor.region.toLowerCase().includes(query)) {
          return true;
        }
        
        // Поиск по региону через город
        if (doctor.city) {
          const cityRegionMap = {
            'Фергана': 'Ферганская область',
            'Андижан': 'Андижанская область',
            'Наманган': 'Наманганская область',
            'Ташкент': 'Город Ташкент',
            'Самарканд': 'Город Самарканд',
            'Бухара': 'Город Бухара',
            'Карши': 'Кашкадарьинская область',
            'Термез': 'Сурхандарьинская область',
            'Гулистан': 'Сырдарьинская область',
            'Джизак': 'Джизакская область',
            'Навои': 'Навоийская область',
            'Ургенч': 'Хорезмская область',
            'Нукус': 'Республика Каракалпакстан'
          };
          
          const cityRegion = cityRegionMap[doctor.city];
          if (cityRegion && cityRegion.toLowerCase().includes(query)) {
            return true;
          }
        }
        
        return false;
      });
    }

    setFilteredDoctors(filtered);
  };



  const getSpecializationIcon = (specialization) => {
    const icons = {
      'Терапевт': '🩺',
      'Кардиолог': '❤️',
      'Невролог': '🧠',
      'Офтальмолог': '👁️',
      'Дерматолог': '🔬',
      'Ортопед': '🦴',
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

  if (loading) {
    return (
      <div className="doctors">
        <div className="doctors__loading">
          <div className="loading-spinner"></div>
          <p>{t('doctorsPage.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="doctors">
        <div className="doctors__error">
          <h2>{t('doctorsPage.accessDeniedTitle')}</h2>
          <p>{error}</p>
          {userData?.role === 'doctor' && (
            <p>{t('doctorsPage.doctorsOnly')}</p>
          )}
          {userData?.role === 'admin' && (
            <p>{t('doctorsPage.adminsOnly')}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="doctors">
      <div className="doctors__header">
        <h1>{t('doctorsPage.title')}</h1>
        <p>{t('doctorsPage.subtitle')}</p>
      </div>

      <div className="doctors__filters">
        <div className="doctors__search">
          <input
            type="text"
            placeholder={t('doctorsPage.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="doctors__search-input"
          />
        </div>

        <div className="doctors__filter-hint">
          <p>{t('doctorsPage.filterHint')}</p>
          <button 
            onClick={resetFilters}
            className="doctors__reset-btn"
            disabled={selectedService === 'all' && selectedSpecialization === 'all' && selectedRegion === 'all' && !searchQuery}
          >
            {t('doctorsPage.resetFilters')}
          </button>
        </div>

        <div className="doctors__filter-controls">
          <div className="doctors__filter-group">
            <label className="doctors__filter-label">{t('doctorsPage.service')}</label>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="doctors__filter-select"
            >
              {services.map(service => (
                <option key={service} value={service}>
                  {service === 'all' ? t('doctorsPage.allServices') : t(`services.categories.${serviceKeyMap[service]}`)}
                </option>
              ))}
            </select>
          </div>

          <div className="doctors__filter-group">
            <label className="doctors__filter-label">{t('doctorsPage.specialization')}</label>
            <select
              value={selectedSpecialization}
              onChange={(e) => setSelectedSpecialization(e.target.value)}
              className="doctors__filter-select"
              disabled={selectedService === 'all'}
            >
              <option value="all">{t('doctorsPage.allSpecializations')}</option>
              {selectedService !== 'all' && specializationsByService[selectedService]?.map(spec => (
                <option key={spec} value={spec}>
                  {translateSpec(spec, i18n.language)}
                </option>
              ))}
            </select>
          </div>

          <div className="doctors__filter-group">
            <label className="doctors__filter-label">{t('doctorsPage.region')}</label>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="doctors__filter-select"
              disabled={selectedSpecialization === 'all'}
            >
              <option value="all">{t('doctorsPage.allRegions')}</option>
              {selectedSpecialization !== 'all' && regionKeys.map(regionKey => (
                <option key={regionKey} value={regionKey}>
                  {translateLocation(regionKey, i18n.language)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="doctors__stats">
        <p>{t('doctorsPage.foundDoctors', { count: filteredDoctors.length })}</p>
      </div>

      {filteredDoctors.length === 0 ? (
        <div className="doctors__empty">
          <div className="doctors__empty-icon"></div>
          <h3>{t('doctorsPage.notFoundTitle')}</h3>
          <p>{t('doctorsPage.notFoundSubtitle')}</p>
        </div>
      ) : (
        <div className="doctors__grid">
          {filteredDoctors.map(doctor => (
            <Link 
              key={doctor.id} 
              to={`/doctors/${doctor.id}`}
              className="doctor-card"
            >
              <div className="doctor-card__header">
                <div className="doctor-card__avatar">
                  {doctor.avatar ? (
                    <img src={doctor.avatar} alt={doctor.full_name} />
                  ) : (
                    <div className="doctor-card__avatar-placeholder">
                      {doctor.first_name && doctor.last_name 
                        ? `${doctor.first_name[0]}${doctor.last_name[0]}`.toUpperCase()
                        : doctor.first_name?.[0]?.toUpperCase() || 'U'}
                    </div>
                  )}
                </div>
                <div className="doctor-card__info">
                  <h3 className="doctor-card__name">{doctor.full_name}</h3>
                  <p className="doctor-card__specialization">
                    {getSpecializationIcon(doctor.specialization)} {translateSpec(doctor.specialization, i18n.language)}
                  </p>
                </div>
              </div>

              <div className="doctor-card__details">
                {doctor.region && (
                  <p className="doctor-card__location">
                    📍 {doctor.city ? `${translateLocation(doctor.city, i18n.language)}, ${translateLocation(doctor.region, i18n.language)}` : translateLocation(doctor.region, i18n.language)}
                  </p>
                )}
                {doctor.experience && (
                  <p className="doctor-card__experience">
                    💼 {doctor.experience.length > 100 
                      ? `${doctor.experience.substring(0, 100)}...` 
                      : doctor.experience}
                  </p>
                )}
                {doctor.languages && doctor.languages.length > 0 && (
                  <p className="doctor-card__languages">
                    🌍 {doctor.languages.join(', ')}
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default Doctors; 


