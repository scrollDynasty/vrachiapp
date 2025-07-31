import React, { useState, useEffect } from 'react';
import Header from './components/Header/Header';
import Sidebar from './components/Sidebar/Sidebar';
import Hero from './components/Hero/Hero';
import Services from './components/Services/Services';
import Profile from './components/Profile/Profile';
import Footer from './components/Footer/Footer';
import MobileNav from './components/MobileNav/MobileNav';
import './App.scss';

function App() {
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    const saved = localStorage.getItem('darkTheme');
    return saved ? JSON.parse(saved) : false;
  });
  
  const [currentPage, setCurrentPage] = useState('home');

  useEffect(() => {
    localStorage.setItem('darkTheme', JSON.stringify(isDarkTheme));
    if (isDarkTheme) {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
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
            const response = await fetch('http://localhost:8000/api/auth/google-auth/', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              credentials: 'include',
              body: JSON.stringify({ access_token: accessToken })
            });

            const data = await response.json();

            if (response.ok) {
              localStorage.setItem('user', JSON.stringify(data.user));
              // Очищаем URL
              window.history.replaceState({}, document.title, window.location.pathname);
              // Перезагружаем страницу для обновления состояния
              window.location.reload();
            } else {
              console.error('Ошибка Google OAuth:', data.error);
              window.history.replaceState({}, document.title, window.location.pathname);
            }
          } catch (err) {
            console.error('Ошибка соединения с сервером:', err);
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        }
      }
    };

    handleGoogleAuthReturn();
  }, []);

  const toggleTheme = () => {
    setIsDarkTheme(!isDarkTheme);
  };

  const renderContent = () => {
    switch (currentPage) {
      case 'profile':
        return <Profile />;
      case 'home':
      default:
        return (
          <>
            <Hero />
            <Services />
          </>
        );
    }
  };

  return (
    <div className="app">
      <Header />
      <Sidebar toggleTheme={toggleTheme} isDarkTheme={isDarkTheme} onPageChange={setCurrentPage} />
      <main className="main">
        {renderContent()}
      </main>
      <Footer />
      <MobileNav />
    </div>
  );
}

export default App;
