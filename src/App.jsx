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
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userData, setUserData] = useState(null);

  // Centralized authentication check
  const checkAuth = async () => {
    try {
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        // Verify with server
        const response = await fetch('http://localhost:8000/api/auth/profile/', {
          credentials: 'include'
        });
        
        if (response.ok) {
          const serverUser = await response.json();
          setIsAuthenticated(true);
          setUserData(serverUser);
        } else {
          // Server says user is not authenticated, clear local storage
          localStorage.removeItem('user');
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setIsAuthenticated(false);
          setUserData(null);
        }
      } else {
        setIsAuthenticated(false);
        setUserData(null);
      }
    } catch (err) {
      // Network error or server down, keep local state if exists
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        setIsAuthenticated(true);
        setUserData(JSON.parse(storedUser));
      } else {
        setIsAuthenticated(false);
        setUserData(null);
      }
    }
  };

  // Handle authentication success
  const handleAuthSuccess = (user) => {
    setIsAuthenticated(true);
    setUserData(user);
    // Force page refresh for full synchronization
    setTimeout(() => {
      window.location.reload();
    }, 100);
  };

  // Handle logout
  const handleLogout = async () => {
    try {
      // Call server logout
      await fetch('http://localhost:8000/api/auth/logout/', {
        method: 'POST',
        credentials: 'include'
      });
    } catch (err) {
      // Continue with logout even if server call fails
    }
    
    // Clear local storage
    localStorage.removeItem('user');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Update state
    setIsAuthenticated(false);
    setUserData(null);
    
    // Force page refresh for full synchronization
    window.location.reload();
  };

  // Check authentication on app load
  useEffect(() => {
    checkAuth();
  }, []);

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
              // Update central state and force reload
              handleAuthSuccess(data.user);
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
      <Header 
        onPageChange={setCurrentPage} 
        isAuthenticated={isAuthenticated}
        userData={userData}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
      />
      <Sidebar 
        toggleTheme={toggleTheme} 
        isDarkTheme={isDarkTheme} 
        onPageChange={setCurrentPage} 
        currentPage={currentPage}
        isAuthenticated={isAuthenticated}
        userData={userData}
      />
      <main className="main">
        {renderContent()}
      </main>
      <Footer />
      <MobileNav />
    </div>
  );
}

export default App;
