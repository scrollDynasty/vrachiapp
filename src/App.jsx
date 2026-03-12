import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.scss';
import Sidebar from './components/Sidebar/Sidebar';
import MobileNav from './components/MobileNav/MobileNav';
import Header from './components/Header/Header';
import Hero from './components/Hero/Hero';
import Services from './components/Services/Services';
import ServicesPage from './components/Services/ServicesPage';
import About from './components/About/About';
import Doctors from './components/Doctors/Doctors';
import DoctorProfile from './components/DoctorProfile/DoctorProfile';
import Profile from './components/Profile/Profile';
import AIDiagnosis from './components/AIDiagnosis/AIDiagnosis';
import AdminPanel from './components/AdminPanel/AdminPanel';
import AuthModal from './components/AuthModal/AuthModal';
import DoctorApplication from './components/DoctorApplication/DoctorApplication';
import Consultations from './components/Consultations/Consultations';
import Chat from './components/Chat/Chat';
import Footer from './components/Footer/Footer';
import { useTranslation } from 'react-i18next';

function App() {
  const { t } = useTranslation();
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    const saved = localStorage.getItem('darkTheme');
    return saved ? JSON.parse(saved) : false;
  });
  
  const [currentPage, setCurrentPage] = useState('home');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userData, setUserData] = useState(null);

  // Серверная проверка сессии: истинный источник авторизации
  const validateAuth = async () => {
    try {
      const resp = await fetch('https://vrachiapp-production.up.railway.app/api/auth/check-auth/', { credentials: 'include' });
      if (resp.ok) {
        const data = await resp.json();
        if (data.authenticated) {
          setIsAuthenticated(true);
          setUserData(data.user || null);
          if (data.user) localStorage.setItem('user', JSON.stringify(data.user));
        } else {
          setIsAuthenticated(false);
          setUserData(null);
          localStorage.removeItem('user');
        }
      } else {
        setIsAuthenticated(false);
        setUserData(null);
        localStorage.removeItem('user');
      }
    } catch (_) {
      // В оффлайне не меняем состояние резко, но не повышаем привилегии
    }
  };

  // Проверяем авторизацию при загрузке и при возвращении в приложение
  useEffect(() => {
    // Быстрый первичный рендер из localStorage (опционально), затем серверная валидация
    try {
      const cached = localStorage.getItem('user');
      if (cached) {
        const parsed = JSON.parse(cached);
        setUserData(parsed);
        setIsAuthenticated(true);
      }
    } catch (_) {}
    validateAuth();

    const onFocus = () => validateAuth();
    const onVisibility = () => { if (document.visibilityState === 'visible') validateAuth(); };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  // Инициализация CSRF cookie для SPA (нужно до любых POST/PUT/DELETE)
  useEffect(() => {
    try {
      fetch('https://vrachiapp-production.up.railway.app/api/auth/csrf/', {
        credentials: 'include'
      });
    } catch (_) {}
  }, []);

  useEffect(() => {
    localStorage.setItem('darkTheme', JSON.stringify(isDarkTheme));
    const appElement = document.querySelector('.app');
    const htmlElement = document.documentElement;
    const bodyElement = document.body;
    if (isDarkTheme) {
      appElement.classList.add('dark-theme');
      htmlElement.classList.add('dark-theme');
      bodyElement.classList.add('dark-theme');
    } else {
      appElement.classList.remove('dark-theme');
      htmlElement.classList.remove('dark-theme');
      bodyElement.classList.remove('dark-theme');
    }
  }, [isDarkTheme]);

  // Обработка возврата от Google OAuth
  useEffect(() => {
    const handleGoogleAuthReturn = async () => {
      const currentUrl = window.location.href;
      
      if (currentUrl.includes('access_token=')) {
        // Извлекаем токен из URL
        const urlParams = new URLSearchParams(currentUrl.split('#')[1]);
        const accessToken = urlParams.get('access_token');
        
        if (accessToken) {
          try {
            // Отправляем токен на сервер
            const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/google-auth/', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
              },
              credentials: 'include',
              body: JSON.stringify({ access_token: accessToken })
            });

            const data = await response.json();

            if (response.ok) {
              localStorage.setItem('user', JSON.stringify(data.user));
              setUserData(data.user);
              setIsAuthenticated(true);
              // Очищаем URL
              window.history.replaceState({}, document.title, window.location.pathname);
            } else {
              window.history.replaceState({}, document.title, window.location.pathname);
            }
          } catch (err) {
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        }
      }
    };

    handleGoogleAuthReturn();
  }, []);

  // Обработка верификации email
  useEffect(() => {
    const handleEmailVerification = async () => {
      const currentUrl = window.location.href;
      
      if (currentUrl.includes('verify-email/')) {
        const token = currentUrl.split('verify-email/')[1];
        
        if (token) {
          try {
            const response = await fetch(`https://vrachiapp-production.up.railway.app/api/auth/verify-email/${token}/`, {
              method: 'GET',
              credentials: 'include'
            });

            const data = await response.json();

            if (response.ok) {
              // Показываем сообщение об успешной верификации
              alert(t('app.emailVerified', 'Email successfully confirmed! Now you can log in.'));
            } else {
              alert(t('app.emailVerifyError', 'Ошибка подтверждения email') + ': ' + (data.error || t('app.unknownError', 'Неизвестная ошибка')));
            }
            
            // Перенаправляем на главную страницу
            window.location.href = '/';
          } catch (err) {
            alert(t('common.serverError', 'Ошибка соединения с сервером'));
            window.location.href = '/';
          }
        }
      }
    };

    handleEmailVerification();
  }, []);

  const toggleTheme = () => {
    setIsDarkTheme(!isDarkTheme);
  };

  const handleLogout = () => {
    localStorage.removeItem('user');
    setIsAuthenticated(false);
    setUserData(null);
    // Перенаправляем на главную страницу
    window.location.href = '/';
  };

  const updateUserData = async () => {
    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/current-user/', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setUserData(data);
        localStorage.setItem('user', JSON.stringify(data));
      }
    } catch (error) {
      console.error('Ошибка обновления данных пользователя:', error);
    }
  };

  const handleShowAllServices = () => {
    setCurrentPage('services');
    window.location.href = '/services';
  };

  const handleShowDoctors = () => {
    setCurrentPage('doctors');
    window.location.href = '/doctors';
  };

  // Компонент для главной страницы
  const HomePage = () => (
    <>
      <Hero />
      <Services onShowAllServices={handleShowAllServices} onShowDoctors={handleShowDoctors} userData={userData} />
    </>
  );

  // Компонент для страницы врачей (только для авторизованных пациентов)
  const DoctorsPage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <Doctors />;
  };

  // Компонент для профиля врача (доступен всем)
  const DoctorProfilePage = () => {
    return <DoctorProfile />;
  };

  // Компонент для профиля пользователя (только для авторизованных)
  const ProfilePage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <Profile />;
  };

  // Компонент для админ панели (только для админов)
  const AdminPanelPage = () => {
    if (!isAuthenticated || userData?.role !== 'admin') {
      return <Navigate to="/" replace />;
    }
    return <AdminPanel />;
  };

  // Компонент для заявки врача (только для авторизованных)
  const DoctorApplicationPage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <DoctorApplication updateUserData={updateUserData} />;
  };

  // Компонент для консультаций (только для авторизованных)
  const ConsultationsPage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <Consultations />;
  };

  // Компонент для чата (только для авторизованных)
  const ChatPage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <Chat />;
  };

  // Компонент для AI диагностики (только для авторизованных)
  const AIDiagnosisPage = () => {
    if (!isAuthenticated) {
      return <Navigate to="/" replace />;
    }
    return <AIDiagnosis />;
  };

  return (
    <Router>
      <div className="app">
        <Header 
          isAuthenticated={isAuthenticated}
          userData={userData}
          onLogout={handleLogout}
          onAuthSuccess={validateAuth}
          isDarkTheme={isDarkTheme}
          toggleTheme={toggleTheme}
        />
        <Sidebar 
          toggleTheme={toggleTheme} 
          isDarkTheme={isDarkTheme} 
          isAuthenticated={isAuthenticated}
          userData={userData}
        />
        <main className="main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<About />} />
            <Route path="/services" element={<ServicesPage userData={userData} />} />
            <Route path="/doctors" element={<DoctorsPage />} />
            <Route path="/doctors/:id" element={<DoctorProfilePage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/admin" element={<AdminPanelPage />} />
            <Route path="/doctor-application" element={<DoctorApplicationPage />} />
            <Route path="/consultations" element={<ConsultationsPage />} />
            <Route path="/consultations/:consultationId" element={<ChatPage />} />
            <Route path="/ai-diagnosis" element={<AIDiagnosisPage />} />
          </Routes>
        </main>
        <Footer />
        <MobileNav 
          currentPage={currentPage}
          setCurrentPage={setCurrentPage}
          isAuthenticated={isAuthenticated}
          userData={userData}
          isDarkTheme={isDarkTheme}
          toggleTheme={toggleTheme}
        />
      </div>
    </Router>
  );
}

export default App;



