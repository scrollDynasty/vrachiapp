import React, { useState, useEffect } from 'react';
import './Profile.scss';

const Profile = () => {
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    region: null,
    city: null,
    district: null,
    address: '',
    medical_info: ''
  });
  
  const [regions, setRegions] = useState([]);
  const [cities, setCities] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [message, setMessage] = useState('');

  // Загружаем данные профиля
  useEffect(() => {
    loadProfile();
    loadRegions();
  }, []);

  const loadProfile = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/auth/profile/', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setProfile({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          phone: data.phone || '',
          region: data.region?.id || null,
          city: data.city?.id || null,
          district: data.district?.id || null,
          address: data.address || '',
          medical_info: data.medical_info || ''
        });
        
        // Загружаем города и районы если есть регион
        if (data.region?.id) {
          loadCities(data.region.id);
          loadDistricts(data.region.id);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки профиля:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRegions = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/auth/regions/');
      if (response.ok) {
        const data = await response.json();
        setRegions(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки регионов:', error);
    }
  };

  const loadCities = async (regionId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/auth/cities/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setCities(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки городов:', error);
    }
  };

  const loadDistricts = async (regionId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/auth/districts/?region_id=${regionId}`);
      if (response.ok) {
        const data = await response.json();
        setDistricts(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки районов:', error);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleRegionChange = (e) => {
    const regionId = e.target.value;
    setProfile(prev => ({
      ...prev,
      region: regionId,
      city: null,
      district: null
    }));
    
    if (regionId) {
      loadCities(regionId);
      loadDistricts(regionId);
    } else {
      setCities([]);
      setDistricts([]);
    }
  };

  const detectLocation = async () => {
    setDetecting(true);
    setMessage('');

    if (!navigator.geolocation) {
      setMessage('Геолокация не поддерживается вашим браузером');
      setDetecting(false);
      return;
    }

    try {
      const position = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000
        });
      });

      const { latitude, longitude } = position.coords;
      
      // Отправляем координаты на сервер
      const response = await fetch('http://localhost:8000/api/auth/detect-location/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          latitude,
          longitude
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setProfile(prev => ({
          ...prev,
          region: data.region.id,
          city: data.city?.id || null,
          district: data.district?.id || null,
          address: data.address_suggestion || ''
        }));
        
        // Загружаем города и районы для определенного региона
        loadCities(data.region.id);
        loadDistricts(data.region.id);
        
        // Формируем сообщение в зависимости от типа региона
        let messageText = `✅ ${data.message}`;
        if (data.region.type === 'city') {
          messageText += ' - автоматически заполнены регион, район и адрес (город республиканского подчинения)';
        } else {
          messageText += ' - автоматически заполнены регион, город, район и адрес';
        }
        
        setMessage(messageText);
        setTimeout(() => setMessage(''), 5000);
      } else {
        setMessage(`❌ ${data.message}`);
      }
    } catch (error) {
      if (error.code === 1) {
        setMessage('❌ Доступ к геолокации запрещен. Разрешите доступ в настройках браузера.');
      } else if (error.code === 2) {
        setMessage('❌ Не удалось определить местоположение. Проверьте подключение к интернету.');
      } else if (error.code === 3) {
        setMessage('❌ Превышено время ожидания определения местоположения.');
      } else {
        setMessage('❌ Ошибка определения местоположения: ' + error.message);
      }
    } finally {
      setDetecting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/auth/profile/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(profile)
      });

      if (response.ok) {
        setMessage('Профиль успешно обновлен!');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const error = await response.json();
        setMessage('Ошибка: ' + (error.message || 'Не удалось обновить профиль'));
      }
    } catch (error) {
      setMessage('Ошибка соединения с сервером');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="profile">
        <div className="profile__loading">Загрузка профиля...</div>
      </div>
    );
  }

  return (
    <div className="profile">
      <div className="profile__container">
        {message && (
          <div className={`profile__message ${message.includes('успешно') ? 'profile__message--success' : 'profile__message--error'}`}>
            {message}
          </div>
        )}

        <form className="profile__form" onSubmit={handleSubmit}>
          <div className="profile__section">
            <h2 className="profile__section-title">Основная информация</h2>
            
            <div className="profile__row">
              <div className="profile__field">
                <label className="profile__label">Полное имя</label>
                <input
                  type="text"
                  name="first_name"
                  value={profile.first_name}
                  onChange={handleInputChange}
                  className="profile__input"
                  placeholder="Введите ваше имя"
                />
              </div>
              
              <div className="profile__field">
                <label className="profile__label">Фамилия</label>
                <input
                  type="text"
                  name="last_name"
                  value={profile.last_name}
                  onChange={handleInputChange}
                  className="profile__input"
                  placeholder="Введите вашу фамилию"
                />
              </div>
            </div>

            <div className="profile__field">
              <label className="profile__label">Номер телефона</label>
              <input
                type="tel"
                name="phone"
                value={profile.phone}
                onChange={handleInputChange}
                className="profile__input"
                placeholder="+998XXXXXXXXX"
              />
            </div>
          </div>

          <div className="profile__section">
            <h2 className="profile__section-title">Адрес</h2>
            
            <div className="profile__location-detect">
              <button
                type="button"
                onClick={detectLocation}
                disabled={detecting}
                className="profile__detect-btn"
              >
                {detecting ? (
                  <>
                    <svg className="profile__detect-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M6.34 6.34l-2.83 2.83m8.48 8.48l2.83-2.83" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Определение...
                  </>
                ) : (
                  <>
                    <svg className="profile__detect-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <circle cx="12" cy="10" r="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Определить мое местоположение
                  </>
                )}
              </button>
            </div>
            
            <div className="profile__row">
              <div className="profile__field">
                <label className="profile__label">Регион</label>
                <select
                  name="region"
                  value={profile.region || ''}
                  onChange={handleRegionChange}
                  className="profile__select"
                >
                  <option value="">Выберите регион</option>
                  {regions.map(region => (
                    <option key={region.id} value={region.id}>
                      {region.name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="profile__field">
                <label className="profile__label">Город</label>
                <select
                  name="city"
                  value={profile.city || ''}
                  onChange={handleInputChange}
                  className="profile__select"
                  disabled={!profile.region}
                >
                  <option value="">Выберите город</option>
                  {cities.map(city => (
                    <option key={city.id} value={city.id}>
                      {city.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="profile__row">
              <div className="profile__field">
                <label className="profile__label">Район</label>
                <select
                  name="district"
                  value={profile.district || ''}
                  onChange={handleInputChange}
                  className="profile__select"
                  disabled={!profile.region}
                >
                  <option value="">Выберите район</option>
                  {districts.map(district => (
                    <option key={district.id} value={district.id}>
                      {district.name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="profile__field">
                <label className="profile__label">Адрес</label>
                <input
                  type="text"
                  name="address"
                  value={profile.address}
                  onChange={handleInputChange}
                  className="profile__input"
                  placeholder="Улица, дом, квартира"
                />
              </div>
            </div>
          </div>

          <div className="profile__section">
            <h2 className="profile__section-title">Медицинская информация</h2>
            
            <div className="profile__field">
              <label className="profile__label">Медицинская информация</label>
              <textarea
                name="medical_info"
                value={profile.medical_info}
                onChange={handleInputChange}
                className="profile__textarea"
                placeholder="Опишите ваши заболевания, аллергии, принимаемые лекарства и т.д."
                rows={4}
              />
            </div>
          </div>

          <div className="profile__actions">
            <button
              type="submit"
              className="profile__submit"
              disabled={saving}
            >
              {saving ? 'Сохранение...' : 'Сохранить изменения'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Profile; 