const API_URL = 'http://localhost:8000/api';
const API_TIMEOUT_MS = 330_000;

export async function transcribeAudio(audioBlob, filename = 'recording.wav') {
  const formData = new FormData();
  formData.append('file', audioBlob, filename);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${API_URL}/transcribe`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('음성 처리 시간이 초과되었습니다. 다시 시도해주세요.');
    }
    throw new Error('서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.');
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '음성 변환에 실패했습니다.');
  }

  return response.json();
}
