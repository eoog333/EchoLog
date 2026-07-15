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
  const [keywords, setKeywords] = useState('');

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const handleStart = async () => {
    setError('');
    try {
      await startRecording();
      setAppState('recording');
    } catch (err) {
      console.error(err);
      setError(err.message || '마이크를 시작할 수 없습니다.');
      setAppState('idle');
    }
  };

  const handleStop = async () => {
    setAppState('processing');
    try {
      const audioBlob = await stopRecording();
      if (!audioBlob) {
        throw new Error('녹음된 오디오가 없습니다.');
      }
      
      const response = await transcribeAudio(audioBlob, 'recording.webm', keywords);
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
      const response = await transcribeAudio(file, file.name, keywords);
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
    setKeywords('');
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>EchoLog</h1>
        <p>대화하듯 편하게, 하루를 기록하세요.</p>
      </header>

      <main className="main-content">
        {error && <div className="error-message">{error}</div>}

        {appState === 'idle' && (
          <div className="view-idle">
            <h2>오늘 하루는 어땠나요?</h2>
            <label className="keyword-input">
              <span>오늘의 주제 <em>선택</em></span>
              <input
                type="text"
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder="예: 면접 준비, 친구와의 만남, 운동"
                maxLength="100"
              />
              <small>쉼표로 최대 5개까지 입력할 수 있어요.</small>
            </label>
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
            <section className="result-card summary-card">
              <h3>오늘 하루 요약</h3>
              <p className="summary-placeholder">
                요약 기능은 곧 추가될 예정이에요.
              </p>
            </section>

            <section className="result-card flow-card">
              <h3>오늘 하루 흐름</h3>
              <div className="timeline-record">
                {(result.timeline ?? result.paragraphs).map((section, index) => (
                  <article className="timeline-section" key={index}>
                    <span className="timeline-label">
                      {section.label ?? formatTime(Math.floor(section.start_at))}
                    </span>
                    <p>{section.text}</p>
                  </article>
                ))}
              </div>
            </section>

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
                <p className="content-text raw-text">{result.raw_transcript}</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
