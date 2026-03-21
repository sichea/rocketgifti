export default async function handler(req, res) {
  const { id } = req.query;

  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    // Vercel 환경 내에서 동일 호스트의 FastAPI 엔드포인트 호출
    const protocol = req.headers['x-forwarded-proto'] || 'http';
    const host = req.headers.host;
    const internalUrl = `${protocol}://${host}/api/internal/draw?event_id=${id}`;

    const response = await fetch(internalUrl, {
      method: 'POST',
    });

    const data = await response.json();
    
    if (data.ok) {
      res.status(200).json(data);
    } else {
      res.status(400).json({ message: data.message });
    }
  } catch (error) {
    res.status(500).json({ message: '추첨 엔진 호출 중 서버 에러가 발생했습니다.' });
  }
}
