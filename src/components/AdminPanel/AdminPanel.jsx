import React, { useState, useEffect, useMemo } from "react";
import "./AdminPanel.scss";
import { useTranslation } from 'react-i18next';

const AdminPanel = ({ updateUserData }) => {
  const [applications, setApplications] = useState([]);
  const [selectedApplication, setSelectedApplication] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [activeTab, setActiveTab] = useState('pending');
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [regions, setRegions] = useState([]);
  const [cities, setCities] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [activeSection, setActiveSection] = useState('applications');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [userData, setUserData] = useState(null);
  const [hasAdminAccess, setHasAdminAccess] = useState(false);
  const { t } = useTranslation();
  
  // Маппинг специализаций к услуге (как в Doctors.jsx)
  const specializationsByService = useMemo(() => ({
    'Медицинские услуги': [
      'Терапевт','Кардиолог','Невролог','Офтальмолог','Дерматолог','Ортопед','Ревматолог','Педиатр','Гинеколог','Уролог','Эндокринолог','Психиатр','Хирург','Стоматолог','Онколог','Аллерголог','Иммунолог','Гастроэнтеролог','Пульмонолог','Нефролог','Гематолог','Инфекционист','Травматолог','Анестезиолог','Реаниматолог'
    ],
    'Спортивные и диетические': ['Спортивный врач','Диетолог'],
    'Физиотерапия': ['Физиотерапевт'],
    'Массаж': ['Массажист'],
    'Психологические консультации': ['Психолог','Психиатр'],
    'Уход за пожилыми': ['Гериатр']
  }), []);

  const serviceKeyMap = useMemo(() => ({
    'Медицинские услуги': 'medical',
    'Спортивные и диетические': 'sportDiet',
    'Физиотерапия': 'physio',
    'Массаж': 'massage',
    'Психологические консультации': 'psychology',
    'Уход за пожилыми': 'elderly'
  }), []);

  const getServiceBySpecialization = (spec) => {
    if (!spec) return null;
    for (const [service, list] of Object.entries(specializationsByService)) {
      if (list.includes(spec)) return service;
    }
    return null;
  };
  
  const handleLogout = async () => {
    try {
      await fetch('https://vrachiapp-production.up.railway.app/api/auth/logout/', {
        method: 'POST',
        headers: { 'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '' },
        credentials: 'include'
      }).catch(() => {});
    } catch (_) {}
    localStorage.removeItem('user');
    window.location.href = '/';
  };

  useEffect(() => {
    // Проверяем права пользователя при загрузке компонента
    checkUserPermissions();
  }, []);

  useEffect(() => {
    try {
      if (hasAdminAccess && activeSection === 'applications') {
        fetchApplications();
      } else if (hasAdminAccess && activeSection === 'users') {
        fetchUsers();
      }
    } catch (error) {
        setError(t('common.loadError', 'Ошибка загрузки данных'));
    }
  }, [activeSection, activeTab, hasAdminAccess]);

  const checkUserPermissions = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/current-user/', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setUserData(data);
        
        // Проверяем, есть ли у пользователя права администратора
        const isAdmin = data.is_staff || data.is_superuser || data.role === 'admin';
        setHasAdminAccess(isAdmin);
        
        if (!isAdmin) {
          setError(t('admin.noAccess', 'У вас нет прав для доступа к панели администратора'));
        }
      } else {
        setError(t('admin.checkError', 'Ошибка проверки прав доступа'));
        setHasAdminAccess(false);
      }
    } catch (error) {
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
      setHasAdminAccess(false);
    }
  };

  const fetchApplications = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = activeTab === 'all' 
        ? 'https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/list/'
        : `https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/list/?status=${activeTab}`;
      
      const response = await fetch(url, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setApplications(data);
      } else {
         setError(t('admin.loadApplicationsError', 'Ошибка загрузки заявок'));
        setApplications([]);
      }
    } catch (error) {
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
      setApplications([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/users/', {
        credentials: 'include'
      });
            
      if (response.ok) {
        const data = await response.json();
        
        // Проверяем, что data является массивом
        if (Array.isArray(data)) {
          setUsers(data);
        } else if (data && typeof data === 'object') {
          // Ищем массив пользователей в объекте
          const usersArray = data.users || data.results || data.data || Object.values(data).find(val => Array.isArray(val));
          if (usersArray && Array.isArray(usersArray)) {
            
            setUsers(usersArray);
          } else {
            setError(t('admin.badData', 'Неверный формат данных'));
            setUsers([]);
          }
        } else {
          setError(t('admin.badData', 'Неверный формат данных'));
          setUsers([]);
        }
        } else {
        const errorData = await response.json();
        setError(t('admin.loadUsersError', 'Ошибка загрузки пользователей') + `: ${response.status}`);
        setUsers([]);
      }
    } catch (error) {
      
      setError(t('common.serverError', 'Ошибка соединения с сервером'));
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

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
      } else {
        const errorText = await response.text();
      }
    } catch (error) {
      
    }
  };

  const loadDistrictsByCity = async (cityId) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/districts/?city_id=${cityId}`);
      
      if (response.ok) {
        const data = await response.json();
        if (data.length > 0) {
          // Если у города есть свои районы, показываем их
          setDistricts(data);
        } else {
          // Если у города нет своих районов, показываем районы региона
          
          if (editingUser.region) {
            loadDistricts(editingUser.region);
          }
        }
      } else {
        const errorText = await response.text();
        // В случае ошибки показываем районы региона
        if (editingUser.region) {
          loadDistricts(editingUser.region);
        }
      }
    } catch (error) {
      
      // В случае ошибки показываем районы региона
      if (editingUser.region) {
        loadDistricts(editingUser.region);
      }
    }
  };

  // Функция для фильтрации районов по городу
  const getFilteredDistricts = (cityId) => {
    if (!cityId || !districts.length) return [];
    
    // Получаем информацию о выбранном городе
    const selectedCity = cities.find(city => city.id == cityId);
    if (!selectedCity) return districts;
    
    
    
    // Фильтруем районы по городу, используя поле city в модели District
    const filteredDistricts = districts.filter(district => {
      // Если у района есть связанный город, проверяем совпадение
      if (district.city && district.city.id == cityId) {
        return true;
      }
      // Если у района нет связанного города, показываем все районы региона
      // (для обратной совместимости)
      return !district.city;
    });
    
    
    return filteredDistricts;
  };

  const openApplicationModal = async (application) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/${application.id}/`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setSelectedApplication(data);
        setShowModal(true);
      }
    } catch (error) {
      console.error('Ошибка загрузки деталей заявки:', error);
    }
  };

  const openUserModal = async (user) => {
    
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/users/${user.id}/profile/`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const userData = await response.json();
        
        setSelectedUser(userData);
        setEditingUser({ ...userData });
        setShowUserModal(true);
        setIsEditing(false);
        
        // Загружаем регионы
        await loadRegions();
        
        // Если есть регион, загружаем города и районы
        if (userData.region) {
           
          await loadCities(userData.region);
          await loadDistricts(userData.region);
        } else {
          
        }
      } else {
       alert(t('admin.userProfileLoadError', 'Ошибка при загрузке профиля пользователя'));
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const handleApprove = async (applicationId) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/${applicationId}/update/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({
          status: 'approved'
        })
      });
      
      if (response.ok) {
        alert(t('admin.applicationApproved', 'Заявка одобрена!'));
        fetchApplications();
        fetchUsers();
        
        // Обновляем данные пользователя в Header
        if (updateUserData) {
          await updateUserData();
        }
      } else {
        alert(t('admin.approveError', 'Ошибка при одобрении заявки'));
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const handleReject = async (applicationId) => {
    const reason = prompt(t('admin.rejectReason', 'Укажите причину отклонения:'));
    if (!reason) return;
    
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/${applicationId}/update/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({
          status: 'rejected',
          rejection_reason: reason
        })
      });
      
      if (response.ok) {
        alert(t('admin.applicationRejected', 'Заявка отклонена!'));
        fetchApplications();
        fetchUsers();
      } else {
        alert(t('admin.rejectError', 'Ошибка при отклонении заявки'));
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const handleUpdateDoctorName = async (applicationId) => {
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/doctor-applications/${applicationId}/update-name/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '' },
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        alert(t('admin.nameUpdated', 'Имя врача обновлено') + `: ${data.new_name}`);
        fetchUsers(); // Обновляем список пользователей
        
        // Обновляем данные пользователя в Header
        if (updateUserData) {
          await updateUserData();
        }
      } else {
        const error = await response.json();
         alert(t('common.error', 'Ошибка') + `: ${error.error}`);
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const handleEditUser = () => {
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditingUser({ ...selectedUser });
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setEditingUser(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleRegionChange = (e) => {
    const regionId = e.target.value;
    
    
    setEditingUser(prev => ({
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

  const handleCityChange = (e) => {
    const cityId = e.target.value;
    setEditingUser(prev => ({
      ...prev,
      city: cityId,
      district: null
    }));
    
    // Загружаем районы для выбранного города
    if (cityId) {
      loadDistrictsByCity(cityId);
    } else {
      // Если город не выбран, загружаем районы только по региону
      if (editingUser.region) {
        loadDistricts(editingUser.region);
      } else {
        setDistricts([]);
      }
    }
  };

  const handleSaveUser = async () => {
    try {
      
      
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/users/${selectedUser.user.id}/profile/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify(editingUser)
      });
      
      if (response.ok) {
        const data = await response.json();
         alert(t('admin.userUpdated', 'Профиль пользователя успешно обновлен!'));
        setSelectedUser(data.profile);
        setEditingUser({ ...data.profile });
        setIsEditing(false);
        fetchUsers();
        
        // Обновляем данные пользователя в Header если это текущий пользователь
        if (updateUserData) {
          await updateUserData();
        }
      } else {
        const error = await response.json();
         alert(t('common.error', 'Ошибка') + `: ${JSON.stringify(error)}`);
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    
    const confirmed = window.confirm(
      t('admin.deleteConfirm', 'Вы уверены, что хотите удалить пользователя') + ` ${selectedUser.user.email}?\n\n` + t('admin.cannotUndo', 'Это действие нельзя отменить!')
    );
    
    if (!confirmed) return;
    
    try {
      const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/users/${selectedUser.user.id}/delete/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || '' },
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        alert(data.message);
        setShowUserModal(false);
        setSelectedUser(null);
        setEditingUser(null);
        setIsEditing(false);
        fetchUsers();
      } else {
        const error = await response.json();
        alert(t('common.error', 'Ошибка') + `: ${error.error}`);
      }
    } catch (error) {
      alert(t('common.serverError', 'Ошибка соединения с сервером'));
    }
  };

  const getStatusCount = (status) => {
    return applications.filter(app => app.status === status).length;
  };

  const getUserRoleDisplay = (user) => {
    if (user.is_staff || user.is_superuser) return 'Администратор';
    if (user.role === 'doctor') return 'Врач';
    return 'Пациент';
  };

  

  // Если у пользователя нет прав администратора, показываем сообщение об ошибке
  if (!hasAdminAccess) {
    return (
      <div className="admin-panel">
        <div className="admin-panel__header">
          <h1>Панель администратора</h1>
        </div>
        <div className="admin-panel__error">
          <p>{error || 'У вас нет прав для доступа к панели администратора'}</p>
          <p>Для доступа к панели администратора необходимо иметь права администратора.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-panel">
      <div className="admin-panel__header">
        <h1>Панель администратора</h1>
        <div className="admin-panel__tabs">
          <button 
            className={`admin-panel__tab ${activeSection === 'applications' ? 'active' : ''}`}
            onClick={() => setActiveSection('applications')}
          >
            Заявки на роль врача
          </button>
          <button 
            className={`admin-panel__tab ${activeSection === 'users' ? 'active' : ''}`}
            onClick={() => setActiveSection('users')}
          >
            Управление пользователями
          </button>
        </div>
      </div>
      
      <div className="admin-panel__logout">
        <button className="admin-panel__logout-btn" onClick={handleLogout}>
          Выйти из аккаунта
        </button>
      </div>

      {activeSection === 'applications' && (
        <>
          <div className="admin-panel__stats">
            <div className="admin-panel__stat">
              <span className="admin-panel__stat-number">{getStatusCount('pending')}</span>
              <span className="admin-panel__stat-label">Ожидают рассмотрения</span>
            </div>
            <div className="admin-panel__stat">
              <span className="admin-panel__stat-number">{getStatusCount('approved')}</span>
              <span className="admin-panel__stat-label">Одобрены</span>
            </div>
            <div className="admin-panel__stat">
              <span className="admin-panel__stat-number">{getStatusCount('rejected')}</span>
              <span className="admin-panel__stat-label">Отклонены</span>
            </div>
          </div>

          <div className="admin-panel__filters">
            <button 
              className={`admin-panel__filter ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              Все заявки
            </button>
            <button 
              className={`admin-panel__filter ${activeTab === 'pending' ? 'active' : ''}`}
              onClick={() => setActiveTab('pending')}
            >
              Ожидают рассмотрения
            </button>
            <button 
              className={`admin-panel__filter ${activeTab === 'approved' ? 'active' : ''}`}
              onClick={() => setActiveTab('approved')}
            >
              Одобрены
            </button>
            <button 
              className={`admin-panel__filter ${activeTab === 'rejected' ? 'active' : ''}`}
              onClick={() => setActiveTab('rejected')}
            >
              Отклонены
            </button>
          </div>

          <div className="admin-panel__applications">
            {loading ? (
              <div className="admin-panel__empty">
                <p>Загрузка заявок...</p>
              </div>
            ) : error ? (
              <div className="admin-panel__empty">
                <p>{error}</p>
              </div>
            ) : applications.length === 0 ? (
              <div className="admin-panel__empty">
                <p>Нет заявок для отображения</p>
              </div>
            ) : (
              applications.map(application => (
                <div key={application.id} className="admin-panel__application-card">
                  <div className="admin-panel__application-info">
                    <h3>{application.full_name}</h3>
                    <p className="admin-panel__application-specialization">
                      {application.specialization}
                    </p>
                    {getServiceBySpecialization(application.specialization) && (
                      <p className="admin-panel__application-service">
                        Категория: {t(`services.categories.${serviceKeyMap[getServiceBySpecialization(application.specialization)]}`)}
                      </p>
                    )}
                    <p className="admin-panel__application-location">
                      {application.region_name && `${application.region_name}, `}{application.city_name}, {application.district_name}
                    </p>
                    <p className="admin-panel__application-status">
                      Статус: <span className={`status-${application.status}`}>
                        {application.status === 'pending' && 'Ожидает рассмотрения'}
                        {application.status === 'approved' && 'Одобрена'}
                        {application.status === 'rejected' && 'Отклонена'}
                      </span>
                    </p>
                  </div>
                  <div className="admin-panel__application-actions">
                    <button 
                      className="admin-panel__view-btn"
                      onClick={() => openApplicationModal(application)}
                    >
                      Просмотреть
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {activeSection === 'users' && (
        <div className="admin-panel__users">
          {loading ? (
            <div className="admin-panel__empty">
              <p>Загрузка пользователей...</p>
            </div>
          ) : error ? (
            <div className="admin-panel__empty">
              <p>{error}</p>
            </div>
          ) : !Array.isArray(users) || users.length === 0 ? (
            <div className="admin-panel__empty">
              <p>Нет пользователей для отображения</p>
            </div>
          ) : (
            users.map(user => (
              <div key={user.id} className="admin-panel__user-card">
                <div className="admin-panel__user-info">
                  <h3>{user.first_name} {user.last_name}</h3>
                  <p className="admin-panel__user-email">{user.email}</p>
                  <p className="admin-panel__user-role">
                    Роль: <span className={`role-${user.role || 'patient'}`}>
                      {getUserRoleDisplay(user)}
                    </span>
                  </p>
                </div>
                <div className="admin-panel__user-actions">
                  <button 
                    className="admin-panel__view-btn"
                    onClick={() => {
                      openUserModal(user);
                    }}
                  >
                    Управлять профилем
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Модальные окна остаются без изменений */}
      {showModal && selectedApplication && (
        <div className="admin-panel__modal-overlay">
          <div className="admin-panel__modal">
            <div className="admin-panel__modal-header">
              <h2>Детали заявки</h2>
              <button 
                className="admin-panel__modal-close"
                onClick={() => {
                  setShowModal(false);
                  setSelectedApplication(null);
                }}
              >
                ×
              </button>
            </div>
            <div className="admin-panel__modal-content">
              <div className="admin-panel__modal-section">
                <h3>Основная информация</h3>
                <p><strong>ФИО:</strong> {selectedApplication.full_name}</p>
                <p><strong>Специализация:</strong> {selectedApplication.specialization || 'Не указана'}</p>
                <p><strong>Категория услуги:</strong> {
                  (() => {
                    const svc = getServiceBySpecialization(selectedApplication.specialization);
                    return svc ? t(`services.categories.${serviceKeyMap[svc]}`) : 'Не указана';
                  })()
                }</p>
                <p><strong>Местоположение:</strong> {selectedApplication.region_name && `${selectedApplication.region_name}, `}{selectedApplication.city_name}, {selectedApplication.district_name}</p>
                <p><strong>Языки:</strong> {Array.isArray(selectedApplication.languages) && selectedApplication.languages.length > 0 ? selectedApplication.languages.join(', ') : 'Не указаны'}</p>
                <p><strong>Телефон:</strong> {selectedApplication.phone || 'Не указан'}</p>
                <p><strong>Дата рождения:</strong> {selectedApplication.date_of_birth || 'Не указана'}</p>
                <p><strong>Пол:</strong> {
                  selectedApplication.gender === 'male' ? 'Мужской' :
                  selectedApplication.gender === 'female' ? 'Женский' :
                  selectedApplication.gender === 'other' ? 'Другой' : 'Не указан'
                }</p>
                <p><strong>Адрес:</strong> {selectedApplication.address || 'Не указан'}</p>
                {selectedApplication.emergency_contact && (
                  <p><strong>Экстренный контакт:</strong> {selectedApplication.emergency_contact}</p>
                )}
                {selectedApplication.medical_info && (
                  <p><strong>Медицинская информация:</strong> {selectedApplication.medical_info}</p>
                )}
              </div>
              
              <div className="admin-panel__modal-section">
                <h3>Образование и опыт</h3>
                <p><strong>Образование:</strong> {selectedApplication.education}</p>
                <p><strong>Опыт работы:</strong> {selectedApplication.experience}</p>
                <p><strong>Номер лицензии:</strong> {selectedApplication.license_number}</p>
              </div>
              
              {selectedApplication.additional_info && (
                <div className="admin-panel__modal-section">
                  <h3>Дополнительная информация</h3>
                  <p>{selectedApplication.additional_info}</p>
                </div>
              )}
              
              <div className="admin-panel__modal-section">
                <h3>Документы</h3>
                <div className="admin-panel__documents">
                      {selectedApplication.photo && (
                    <div className="admin-panel__document">
                      <h4>Фотография</h4>
                          <img
                            src={`https://vrachiapp-production.up.railway.app/api/auth/protected-media/${selectedApplication.photo.replace(/^\/media\//, '')}`}
                            alt="Фото врача"
                            className="admin-panel__document-image"
                          />
                    </div>
                  )}
                  
                      {selectedApplication.diploma && (
                    <div className="admin-panel__document">
                      <h4>Диплом</h4>
                      <a 
                             href={`https://vrachiapp-production.up.railway.app/api/auth/protected-media/${selectedApplication.diploma.replace(/^\/media\//, '')}`}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="admin-panel__document-link"
                      >
                        Просмотреть диплом
                      </a>
                    </div>
                  )}
                  
                      {selectedApplication.license && (
                    <div className="admin-panel__document">
                      <h4>Лицензия</h4>
                      <a 
                             href={`https://vrachiapp-production.up.railway.app/api/auth/protected-media/${selectedApplication.license.replace(/^\/media\//, '')}`}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="admin-panel__document-link"
                      >
                        Просмотреть лицензию
                      </a>
                    </div>
                  )}
                </div>
              </div>
              
              {selectedApplication.status === 'rejected' && selectedApplication.rejection_reason && (
                <div className="admin-panel__modal-section">
                  <h3>Причина отклонения</h3>
                  <p>{selectedApplication.rejection_reason}</p>
                </div>
              )}
              
              {selectedApplication.status === 'pending' && (
                <div className="admin-panel__modal-section">
                  <h3>Действия</h3>
                  <div className="admin-panel__modal-actions">
                    <button 
                      className="admin-panel__approve-btn"
                      onClick={() => handleApprove(selectedApplication.id)}
                    >
                      Одобрить
                    </button>
                    <button 
                      className="admin-panel__reject-btn"
                      onClick={() => handleReject(selectedApplication.id)}
                    >
                      Отклонить
                    </button>
                  </div>
                </div>
              )}
              
              {selectedApplication.status === 'approved' && (
                <div className="admin-panel__modal-section">
                  <h3>Действия</h3>
                  <div className="admin-panel__modal-actions">
                    <button 
                      className="admin-panel__update-name-btn"
                      onClick={() => handleUpdateDoctorName(selectedApplication.id)}
                    >
                      Обновить имя врача
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {showUserModal && selectedUser && (
        <div className="admin-panel__modal-overlay">
          <div className="admin-panel__modal admin-panel__modal--large">
            <div className="admin-panel__modal-header">
              <h2>Управление профилем пользователя</h2>
              <button 
                className="admin-panel__modal-close"
                onClick={() => {
                  setShowUserModal(false);
                  setSelectedUser(null);
                  setEditingUser(null);
                  setIsEditing(false);
                }}
              >
                ×
              </button>
            </div>
            <div className="admin-panel__modal-content">
              <div className="admin-panel__modal-section">
                <h3>Основная информация</h3>
                {isEditing ? (
                  <div className="admin-panel__form">
                    <div className="admin-panel__form-row">
                      <div className="admin-panel__form-group">
                        <label>Имя</label>
                        <input
                          type="text"
                          name="first_name"
                          value={editingUser.first_name || ''}
                          onChange={handleInputChange}
                          className="admin-panel__input"
                        />
                      </div>
                      <div className="admin-panel__form-group">
                        <label>Фамилия</label>
                        <input
                          type="text"
                          name="last_name"
                          value={editingUser.last_name || ''}
                          onChange={handleInputChange}
                          className="admin-panel__input"
                        />
                      </div>
                    </div>
                    <div className="admin-panel__form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        value={selectedUser.user.email}
                        className="admin-panel__input"
                        disabled
                      />
                    </div>
                    <div className="admin-panel__form-group">
                      <label>Роль</label>
                      <select
                        name="role"
                        value={editingUser.role || 'patient'}
                        onChange={handleInputChange}
                        className="admin-panel__select"
                      >
                        <option value="patient">Пациент</option>
                        <option value="doctor">Врач</option>
                        <option value="admin">Администратор</option>
                      </select>
                    </div>
                  </div>
                ) : (
                  <div className="admin-panel__info">
                    <p><strong>ФИО:</strong> {selectedUser.first_name} {selectedUser.last_name}</p>
                    <p><strong>Email:</strong> {selectedUser.user.email}</p>
                    <p><strong>Роль:</strong> {getUserRoleDisplay(selectedUser.user)}</p>
                  </div>
                )}
              </div>
              
              <div className="admin-panel__modal-section">
                <h3>Контактная информация</h3>
                {isEditing ? (
                  <div className="admin-panel__form">
                    <div className="admin-panel__form-group">
                      <label>Телефон</label>
                      <input
                        type="tel"
                        name="phone"
                        value={editingUser.phone || ''}
                        onChange={handleInputChange}
                        className="admin-panel__input"
                      />
                    </div>
                    <div className="admin-panel__form-row">
                      <div className="admin-panel__form-group">
                        <label>Регион</label>
                        <select
                          name="region"
                          value={editingUser.region || ''}
                          onChange={handleRegionChange}
                          className="admin-panel__select"
                        >
                          <option value="">Выберите регион</option>
                          {regions.map(region => (
                            <option key={region.id} value={region.id}>
                              {region.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="admin-panel__form-group">
                        <label>Город</label>
                        <select
                          name="city"
                          value={editingUser.city || ''}
                          onChange={handleCityChange}
                          className="admin-panel__select"
                          disabled={!editingUser.region}
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
                    <div className="admin-panel__form-group">
                      <label>Район</label>
                      <select
                        name="district"
                        value={editingUser.district || ''}
                        onChange={handleInputChange}
                        className="admin-panel__select"
                        disabled={!editingUser.city}
                      >
                        <option value="">Выберите район</option>
                        {getFilteredDistricts(editingUser.city).map(district => (
                          <option key={district.id} value={district.id}>
                            {district.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="admin-panel__form-group">
                      <label>Адрес</label>
                      <input
                        type="text"
                        name="address"
                        value={editingUser.address || ''}
                        onChange={handleInputChange}
                        className="admin-panel__input"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="admin-panel__info">
                    <p><strong>Телефон:</strong> {selectedUser.phone || 'Не указан'}</p>
                    <p><strong>Регион:</strong> {selectedUser.region_name || selectedUser.region || 'Не указан'}</p>
                    <p><strong>Город:</strong> {selectedUser.city_name || selectedUser.city || 'Не указан'}</p>
                    <p><strong>Район:</strong> {selectedUser.district_name || selectedUser.district || 'Не указан'}</p>
                    <p><strong>Адрес:</strong> {selectedUser.address || 'Не указан'}</p>
                  </div>
                )}
              </div>
              
              {selectedUser.role === 'doctor' && (
                <div className="admin-panel__modal-section">
                  <h3>Информация врача</h3>
                  {isEditing ? (
                    <div className="admin-panel__form">
                      <div className="admin-panel__form-row">
                        <div className="admin-panel__form-group">
                          <label>Категория услуги</label>
                          <select
                            name="service"
                            value={getServiceBySpecialization(editingUser.specialization) || ''}
                            onChange={(e) => {
                              const service = e.target.value;
                              setEditingUser(prev => ({ ...prev, specialization: '' , service }));
                            }}
                            className="admin-panel__select"
                          >
                            <option value="">Выберите услугу</option>
                            {Object.keys(specializationsByService).map(service => (
                              <option key={service} value={service}>{t(`services.categories.${serviceKeyMap[service]}`)}</option>
                            ))}
                          </select>
                        </div>
                        <div className="admin-panel__form-group">
                          <label>Специализация</label>
                          <select
                            name="specialization"
                            value={editingUser.specialization || ''}
                            onChange={handleInputChange}
                            className="admin-panel__select"
                          >
                            <option value="">Выберите специализацию</option>
                            {(specializationsByService[getServiceBySpecialization(editingUser.specialization)] || []).map(spec => (
                              <option key={spec} value={spec}>{spec}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="admin-panel__form-group">
                        <label>Образование</label>
                        <textarea
                          name="education"
                          value={editingUser.education || ''}
                          onChange={handleInputChange}
                          className="admin-panel__textarea"
                          rows={3}
                        />
                      </div>
                      <div className="admin-panel__form-group">
                        <label>Опыт работы</label>
                        <textarea
                          name="experience"
                          value={editingUser.experience || ''}
                          onChange={handleInputChange}
                          className="admin-panel__textarea"
                          rows={3}
                        />
                      </div>
                      <div className="admin-panel__form-group">
                        <label>Номер лицензии</label>
                        <input
                          type="text"
                          name="license_number"
                          value={editingUser.license_number || ''}
                          onChange={handleInputChange}
                          className="admin-panel__input"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="admin-panel__info">
                      <p><strong>Категория услуги:</strong> {
                        (() => {
                          const svc = getServiceBySpecialization(selectedUser.specialization);
                          return svc ? t(`services.categories.${serviceKeyMap[svc]}`) : 'Не указана';
                        })()
                      }</p>
                      <p><strong>Специализация:</strong> {selectedUser.specialization || 'Не указана'}</p>
                      <p><strong>Образование:</strong> {selectedUser.education || 'Не указано'}</p>
                      <p><strong>Опыт работы:</strong> {selectedUser.experience || 'Не указан'}</p>
                      <p><strong>Номер лицензии:</strong> {selectedUser.license_number || 'Не указан'}</p>
                      <p><strong>Языки:</strong> {selectedUser.languages ? selectedUser.languages.join(', ') : 'Не указаны'}</p>
                    </div>
                  )}
                </div>
              )}
              
              <div className="admin-panel__modal-section">
                <h3>Действия</h3>
                <div className="admin-panel__modal-actions">
                  {isEditing ? (
                    <>
                      <button 
                        className="admin-panel__save-btn"
                        onClick={handleSaveUser}
                      >
                        Сохранить
                      </button>
                      <button 
                        className="admin-panel__cancel-btn"
                        onClick={handleCancelEdit}
                      >
                        Отмена
                      </button>
                    </>
                  ) : (
                    <>
                      <button 
                        className="admin-panel__edit-btn"
                        onClick={handleEditUser}
                      >
                        Редактировать профиль
                      </button>
                      <button 
                        className="admin-panel__delete-btn"
                        onClick={handleDeleteUser}
                      >
                        Удалить пользователя
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel; 


