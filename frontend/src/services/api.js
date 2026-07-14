const API_URL = 'http://localhost:8000/api';

export async function transcribeAudio(audioBlob, filename = 'recording.wav') {
  const formData = new FormData();
  formData.append('file', audioBlob, filename);

  const response = await fetch(`${API_URL}/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '음성 변환에 실패했습니다.');
  }

  return response.json();
}
