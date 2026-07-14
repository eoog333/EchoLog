import { useState } from 'react';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import { transcribeAudio } from './services/api';
import './App.css';

function App() {
  const { recordingTime, startRecording, stopRecording } = useAudioRecorder();
  
  // 상태: idle -> recording -> processing -> done
  const [appState, setAppState] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [showRaw, setShowRaw] = useState(false);

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const handleStart = async () => {
    setError('');
    await startRecording();
    setAppState('recording');
  };

  const handleStop = async () => {
    setAppState('processing');
    try {
      const audioBlob = await stopRecording();
      if (!audioBlob) {
        throw new Error('녹음된 오디오가 없습니다.');
      }
      
      const response = await transcribeAudio(audioBlob);
      setResult(response);
      setAppState('done');
    } catch (err) {
      console.error(err);
      setError(err.message || '오류가 발생했습니다.');
      setAppState('idle');
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) {
      return;
    }

    setError('');
    setAppState('processing');

    try {
      const response = await transcribeAudio(file, file.name);
      setResult(response);
      setAppState('done');
    } catch (err) {
      console.error(err);
      setError(err.message || '오류가 발생했습니다.');
      setAppState('idle');
    }
  };

  const handleReset = () => {
    setResult(null);
    setAppState('idle');
    setShowRaw(false);
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>EchoLog</h1>
        <p>Speak naturally. Reflect clearly.</p>
      </header>

      <main className="main-content">
        {error && <div className="error-message">{error}</div>}

        {appState === 'idle' && (
          <div className="view-idle">
            <h2>오늘 하루는 어땠나요?</h2>
            <button className="btn-record start" onClick={handleStart}>
              🎤 녹음 시작
            </button>
            <div className="upload-section">
              <span className="upload-divider">또는</span>
              <label className="btn-upload">
                음성 파일 올리기
                <input
                  type="file"
                  accept="audio/wav,audio/mpeg,audio/mp4,audio/x-m4a,audio/flac,audio/amr,.wav,.mp3,.m4a,.mp4,.flac,.amr"
                  onChange={handleFileUpload}
                />
              </label>
            </div>
          </div>
        )}

        {appState === 'recording' && (
          <div className="view-recording">
            <div className="recording-indicator">
              <span className="pulse-dot"></span>
              <span className="time-display">{formatTime(recordingTime)}</span>
            </div>
            <button className="btn-record stop" onClick={handleStop}>
              ⏹ 녹음 완료
            </button>
          </div>
        )}

        {appState === 'processing' && (
          <div className="view-processing">
            <div className="spinner"></div>
            <p>기록을 다듬고 있습니다... 잠시만 기다려주세요.</p>
          </div>
        )}

        {appState === 'done' && result && (
          <div className="view-result">
            <div className="result-card reflection">
              <h3>✨ Today's Reflection</h3>
              <div className="content-text">
                {result.reflection.split('\n').map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
              </div>
            </div>

            <div className="result-actions">
              <button 
                className="btn-toggle" 
                onClick={() => setShowRaw(!showRaw)}
              >
                {showRaw ? '원본 전사 숨기기' : '원본 전사 보기'}
              </button>
              <button className="btn-reset" onClick={handleReset}>
                새로 기록하기
              </button>
            </div>

            {showRaw && (
              <div className="result-card raw">
                <h3>📝 RTZR STT 원본</h3>
                <p className="content-text raw-text">{result.raw_transcript}</p>
                
                <h4 style={{marginTop: '20px'}}>시간별 그룹핑</h4>
                <ul className="timeline-list">
                  {result.paragraphs.map((p, i) => (
                    <li key={i}>
                      <span className="time-badge">{formatTime(Math.floor(p.start_at))}</span>
                      {p.text}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
