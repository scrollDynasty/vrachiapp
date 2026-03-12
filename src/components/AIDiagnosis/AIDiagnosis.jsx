import React, { useState, useRef, useEffect } from 'react';
import './AIDiagnosis.scss';
import { useTranslation } from 'react-i18next';

const AIDiagnosis = () => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'ai',
       content: t('ai.welcome', 'Привет! 😊 Я Healzy AI - ваша медицинская помощница! Я женщина-врач с естественным голосом. Можете спросить меня о здоровье, симптомах или медицинских вопросах. Говорите голосом или пишите текст - я всегда рада помочь! ✨'),
      timestamp: new Date()
    }
  ]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false); // Голосовое прослушивание
  const [isSpeaking, setIsSpeaking] = useState(false); // AI говорит
  const [speechRecognition, setSpeechRecognition] = useState(null); // Распознавание речи
  const [isSupported, setIsSupported] = useState(false); // Поддержка Speech API
  // Удалено: availableVoices и currentVoiceIndex больше не нужны
  
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Автопрокрутка к последнему сообщению
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Инициализация Speech Recognition API
  useEffect(() => {
    // Проверяем поддержку Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (SpeechRecognition) {
      setIsSupported(true);
      
      const recognition = new SpeechRecognition();
      
      // Улучшенные настройки распознавания для лучшей точности
      recognition.continuous = false; // Разовое распознавание для лучшей точности
      recognition.interimResults = true; // Промежуточные результаты
      const lng = (localStorage.getItem('i18nextLng') || 'ru').startsWith('uz') ? 'uz-UZ' : 'ru-RU';
      recognition.lang = lng; // Четкий язык распознавания
      recognition.maxAlternatives = 3; // Больше альтернатив для лучшего распознавания
      
      setSpeechRecognition(recognition);
      
      // Удалено: предзагрузка голосов больше не нужна
      
      // Обработчики событий
      recognition.onstart = () => {
        setIsListening(true);
      };
      
      recognition.onresult = (event) => {
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          }
        }
        
        if (finalTranscript.trim()) {
          handleVoiceInput(finalTranscript.trim());
        }
      };
      
      recognition.onerror = (event) => {
        setIsListening(false);
        
        if (event.error === 'not-allowed') {
          alert(t('ai.allowMic', 'Разрешите доступ к микрофону в настройках браузера'));
        }
        // Остальные ошибки игнорируем для плавной работы
      };
      
      recognition.onend = () => {
        setIsListening(false);
      };
      
    } else {
      setIsSupported(false);
    }
    
  }, []);

  // Новая система: Speech Recognition API (как в ChatGPT Voice)
  const startSmartListening = () => {
    if (!isSupported) {
      alert(t('ai.noSpeech', 'Speech Recognition не поддерживается в этом браузере. Попробуйте Chrome.'));
      return;
    }
    
    if (isListening) {
      speechRecognition.stop();
      setIsListening(false);
      return;
    }

    
      try {
      speechRecognition.start();
    } catch (error) {
      // Игнорируем ошибки запуска - пользователь может попробовать снова
    }
  };

  // Обработка голосового ввода от Speech Recognition
  const handleVoiceInput = async (transcript) => {
    
    // Добавляем голосовое сообщение пользователя в чат (показываем как аудио)
    const userMessage = {
      id: Date.now(),
      type: 'user', 
      content: transcript, // Сохраняем текст, но не показываем
      isVoiceMessage: true,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/ai/diagnosis/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({
          message: transcript,
          type: 'text'
        })
      });

      if (response.ok) {
        const data = await response.json();
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: data.response,
          isVoiceResponse: data.has_voice,
          audioUrl: data.audio_url,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, aiMessage]);
        
        // Автоматически воспроизводим голосовой ответ
        if (data.has_voice && data.audio_url) {
          setTimeout(() => playAudioResponse(data.audio_url, data.response), 300); // Небольшая задержка для лучшего UX
        } else {
          // Fallback к встроенному TTS
          setTimeout(() => speakText(data.response), 300);
        }
        
      } else {
        throw new Error('server');
      }
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Извините, не удалось обработать голосовое сообщение. Попробуйте ещё раз.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Убрал сложную систему анализа аудио - теперь все через Speech Recognition API

  // Функция для очистки текста от всех нежелательных символов
  const cleanTextForSpeech = (text) => {
    let cleanText = text;
    
    // Убираем эмодзи
    cleanText = cleanText.replace(/[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '');
    
    // Убираем специальные символы и знаки препинания которые плохо произносятся
    cleanText = cleanText.replace(/[*#@$%^&()[\]{}|\\<>+=_~`]/g, ' ');
    
    // Убираем множественные пробелы
    cleanText = cleanText.replace(/\s+/g, ' ');
    
    // Заменяем некоторые символы на слова для лучшего произношения
    cleanText = cleanText.replace(/\b\d+\.\s/g, '. '); // "1. текст" -> ". текст"
    cleanText = cleanText.replace(/\bвр\./gi, 'врач'); 
    cleanText = cleanText.replace(/\bдр\./gi, 'доктор');
    cleanText = cleanText.replace(/\bмин\./gi, 'минут');
    cleanText = cleanText.replace(/\bчас\./gi, 'часов');
    
    // Убираем лишние знаки препинания
    cleanText = cleanText.replace(/[,.!?;:]{2,}/g, '. ');
    
    return cleanText.trim();
  };

  // Оптимизированное воспроизведение аудио
  const playAudioResponse = (audioUrl, fallbackText = null) => {
    if (!audioUrl || !fallbackText) {
      return;
    }

    // Останавливаем текущую речь
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    
    // Сохраняем состояние прослушивания
    const wasListening = isListening;
    if (wasListening && speechRecognition) {
      speechRecognition.stop();
    }

    const audio = new Audio();
    audio.preload = 'auto';
    audio.src = audioUrl;
    
    setIsSpeaking(true);
    
    const cleanup = () => {
      setIsSpeaking(false);
      if (wasListening && speechRecognition) {
        setTimeout(() => speechRecognition.start(), 300);
      }
    };

    const fallbackToTTS = () => {
      cleanup();
      speakText(fallbackText);
    };

    audio.onended = cleanup;
    audio.onerror = fallbackToTTS;
    audio.onabort = fallbackToTTS;
    
    audio.play().catch(() => fallbackToTTS());
  };

  // Простая и надежная озвучка
  const speakText = (text) => {
    if (!window.speechSynthesis || !text?.trim()) return;

    const cleanText = cleanTextForSpeech(text);
    if (!cleanText.trim()) return;

    window.speechSynthesis.cancel();
    
    const wasListening = isListening;
    if (wasListening && speechRecognition) {
      speechRecognition.stop();
    }

    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    // Оптимальные настройки для женского голоса
    utterance.rate = 0.85;
    utterance.pitch = 1.3;
    utterance.volume = 0.9;
    utterance.lang = 'ru-RU';
    
    // Ищем лучший русский голос
    const voices = window.speechSynthesis.getVoices();
    const russianVoice = voices.find(v => v.lang.startsWith('ru') && v.name.toLowerCase().includes('female')) ||
                        voices.find(v => v.lang.startsWith('ru')) ||
                        null;
    
    if (russianVoice) {
      utterance.voice = russianVoice;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => {
      setIsSpeaking(false);
      if (wasListening && speechRecognition) {
        setTimeout(() => speechRecognition.start(), 300);
      }
    };
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  // Удалено: функции анализа голосов больше не нужны



  // Отправка текстового сообщения
  const handleSendMessage = async () => {
    if (!currentMessage.trim()) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: currentMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsLoading(true);

    try {
      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/ai/diagnosis/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)')||[]).pop() || ''
        },
        credentials: 'include',
        body: JSON.stringify({
          message: currentMessage,
          type: 'text'
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: data.response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, aiMessage]);
        
        // Если есть голосовой ответ, воспроизводим его, или если активно прослушивание
        if (data.has_voice && data.audio_url) {
          playAudioResponse(data.audio_url, data.response);
        } else if (isListening) {
          speakText(data.response);
        }
        
      } else {
        throw new Error(data.error || 'server');
      }
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Извините, произошла ошибка. Попробуйте еще раз.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Обработка загрузки файла
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Проверяем тип файла
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    
    if (!isImage && !isVideo) {
      alert(t('ai.uploadImageOrVideo', 'Пожалуйста, загрузите изображение или видео'));
      return;
    }

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: isImage ? '📷 Изображение загружено' : '🎥 Видео загружено',
      file: file,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', isImage ? 'image' : 'video');

      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/ai/diagnosis/', {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      
      if (response.ok) {
        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: data.response,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, aiMessage]);
      } else {
        throw new Error(data.error || 'server');
      }
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Извините, не удалось проанализировать файл. Попробуйте еще раз.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Запись голоса
  const startVoiceRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          setRecordedChunks(prev => [...prev, event.data]);
        }
      };

      recorder.onstop = () => {
        stream.getTracks().forEach(track => track.stop());
      };

      setMediaRecorder(recorder);
      recorder.start();
      setIsRecording(true);
    } catch (error) {
      // Игнорируем ошибки доступа к микрофону
    }
  };

  const stopVoiceRecording = async () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      
      // Обработка записанного аудио
      setTimeout(async () => {
        if (recordedChunks.length > 0) {
          const audioBlob = new Blob(recordedChunks, { type: 'audio/wav' });
          await sendAudioMessage(audioBlob);
          setRecordedChunks([]);
        }
      }, 100);
    }
  };

  const sendAudioMessage = async (audioBlob) => {
    // Добавляем голосовое сообщение пользователя (показываем как аудио)
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: 'Голосовое сообщение',
      isVoiceMessage: true,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('file', audioBlob, 'voice.wav');
      formData.append('type', 'audio');

      const response = await fetch('https://vrachiapp-production.up.railway.app/api/auth/ai/diagnosis/', {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      
      if (response.ok) {
        // Обновляем пользовательское сообщение с расшифровкой, если она есть
        if (data.transcription) {
          setMessages(prev => prev.map(msg => 
            msg.id === userMessage.id 
              ? { ...msg, content: data.transcription }
              : msg
          ));
        }

        const aiMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: data.response,
          isVoiceResponse: data.has_voice,
          audioUrl: data.audio_url,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, aiMessage]);
        
        // Автоматически воспроизводим голосовой ответ
        if (data.has_voice && data.audio_url) {
          setTimeout(() => playAudioResponse(data.audio_url, data.response), 300);
        } else {
          setTimeout(() => speakText(data.response), 300);
        }
        
      } else {
        throw new Error(data.error || 'server');
      }
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Извините, не удалось обработать голосовое сообщение. Попробуйте еще раз.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Форматирование времени
  const formatTime = (date) => {
    const lng = (localStorage.getItem('i18nextLng') || 'ru').startsWith('uz') ? 'uz-UZ' : (localStorage.getItem('i18nextLng') || 'ru');
    return date.toLocaleTimeString(lng, { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className="ai-diagnosis">
      <div className="ai-diagnosis__container">
        <div className="ai-diagnosis__header">
          <div className="ai-diagnosis__title">
            <div className="ai-diagnosis__icon">
              🤖
            </div>
            <div>
              <h1>{t('ai.title', 'Healzy AI Диагностика')}</h1>
              <p>{t('ai.subtitle', 'Персональный медицинский ассистент')}</p>
            </div>
          </div>
          <div className="ai-diagnosis__status">
            <span className="ai-diagnosis__status-indicator"></span>
            {t('ai.online', 'Онлайн')}
          </div>
        </div>

        <div className="ai-diagnosis__messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`ai-diagnosis__message ai-diagnosis__message--${message.type}`}
            >
              <div className="ai-diagnosis__message-avatar">
                {message.type === 'ai' ? '🤖' : '👤'}
              </div>
              <div className="ai-diagnosis__message-content">
                {message.isVoiceMessage ? (
                  // Голосовое сообщение пользователя
                  <div className="ai-diagnosis__voice-message">
                    <div className="ai-diagnosis__voice-indicator">
                      🎤 <span className="ai-diagnosis__voice-text">Голосовое сообщение</span>
                      <div className="ai-diagnosis__voice-waves">
                        <span></span><span></span><span></span><span></span>
                      </div>
                    </div>
                  </div>
                ) : message.isVoiceResponse && message.audioUrl ? (
                  // Голосовой ответ AI
                  <div className="ai-diagnosis__voice-response">
                    <div className="ai-diagnosis__voice-indicator ai-diagnosis__voice-indicator--ai">
                      🗣️ <span className="ai-diagnosis__voice-text">Healzy отвечает голосом</span>
                      <div className="ai-diagnosis__voice-waves ai-diagnosis__voice-waves--playing">
                        <span></span><span></span><span></span><span></span>
                      </div>
                    </div>
                    <audio 
                      controls 
                      src={message.audioUrl}
                      className="ai-diagnosis__audio-player"
                      style={{marginTop: '8px', width: '100%', maxWidth: '300px'}}
                    />
                  </div>
                ) : (
                  // Обычное текстовое сообщение
                  <div className="ai-diagnosis__message-text">
                    {message.content}
                  </div>
                )}
                <div className="ai-diagnosis__message-time">
                  {formatTime(message.timestamp)}
                </div>
              </div>
            </div>
          ))}
          
          {(isLoading || isSpeaking) && (
            <div className="ai-diagnosis__message ai-diagnosis__message--ai">
              <div className="ai-diagnosis__message-avatar">🤖</div>
              <div className="ai-diagnosis__message-content">
                {isLoading ? (
                  <div className="ai-diagnosis__loading">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                ) : (
                  <div className="ai-diagnosis__speaking">
                    {t('ai.speaking', '🗣️ Говорю...')}
                  </div>
                )}
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="ai-diagnosis__input">
          <div className="ai-diagnosis__actions">
            <button
              className="ai-diagnosis__action-btn"
              onClick={() => fileInputRef.current?.click()}
              title={t('ai.uploadTitle', 'Загрузить изображение или видео')}
            >
              📷
            </button>
            
            <button
              className={`ai-diagnosis__action-btn ${isListening ? 'ai-diagnosis__action-btn--listening' : ''}`}
              onClick={startSmartListening}
              disabled={!isSupported}
              title={isListening ? t('ai.voiceActive', 'Говорю... (нажмите для остановки)') : t('ai.startVoice', 'Начать голосовой диалог с Healzy AI')}
            >
              {isListening ? '🔴' : '🎤'}
            </button>




          </div>

          <div className="ai-diagnosis__input-container">
            <input
              type="text"
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder={t('ai.placeholder', 'Опишите ваши симптомы или задайте медицинский вопрос...')}
              className="ai-diagnosis__text-input"
              disabled={isLoading}
            />
            
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !currentMessage.trim()}
              className="ai-diagnosis__send-btn"
            >
              ➤
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            onChange={handleFileUpload}
            className="ai-diagnosis__file-input"
            hidden
          />
        </div>

        <div className="ai-diagnosis__disclaimer">
          ⚠️ {t('ai.disclaimer1', 'Внимание: AI диагностика не заменяет консультацию врача.')} 
          {t('ai.disclaimer2', 'При серьезных симптомах обратитесь к специалисту.')}
          
          {isSupported && (
            <>
              <br />
              🎤 Нажмите микрофон для голосового общения с медицинской помощницей
            </>
          )}
          
          {!isSupported && (
            <>
              <br />
              ❌ {t('ai.voiceUnavailable', 'Голосовые функции недоступны в этом браузере. Попробуйте Chrome.')}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIDiagnosis;



