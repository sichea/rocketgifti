import React from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { styled, keyframes } from '../../../stitches.config';

const Container = styled('div', {
  padding: '$4',
  maxWidth: '800px',
  margin: '0 auto',
  minHeight: '100vh',
  backgroundColor: '$bgSurface',
});

const Card = styled('div', {
  backgroundColor: 'white',
  borderRadius: '$lg',
  padding: '$4',
  boxShadow: '$md',
  marginBottom: '$4',
});

const Title = styled('h1', {
  fontSize: '1.25rem',
  fontWeight: '700',
  marginBottom: '$2',
});

const StatusBadge = styled('span', {
  padding: '$1 $2',
  borderRadius: '$md',
  fontSize: '0.75rem',
  fontWeight: '600',
  textTransform: 'uppercase',
  variants: {
    status: {
      OPEN: { backgroundColor: '$success', color: 'white' },
      CLOSED: { backgroundColor: '$gray200', color: '$textMuted' },
    },
  },
});

const ParticipantList = styled('div', {
  display: 'flex',
  flexDirection: 'column',
  gap: '$2',
  marginTop: '$4',
});

const ParticipantItem = styled('div', {
  display: 'flex',
  justifyContent: 'space-between',
  padding: '$2 $3',
  backgroundColor: '$gray100',
  borderRadius: '$md',
});

const DrawAnimation = keyframes({
  '0%': { transform: 'scale(1)', opacity: 1 },
  '50%': { transform: 'scale(1.1)', opacity: 0.8 },
  '100%': { transform: 'scale(1)', opacity: 1 },
});

const DrawButton = styled('button', {
  width: '100%',
  padding: '$4',
  backgroundColor: '$primary',
  color: 'white',
  border: 'none',
  borderRadius: '$md',
  fontSize: '1.125rem',
  fontWeight: '700',
  cursor: 'pointer',
  marginTop: '$6',
  boxShadow: '$lg',
  transition: 'background-color 0.2s',

  '&:hover': {
    backgroundColor: '$primaryHover',
  },

  '&:disabled': {
    backgroundColor: '$gray200',
    cursor: 'not-allowed',
  },

  variants: {
    isDrawing: {
      true: {
        animation: `${DrawAnimation} 1s infinite ease-in-out`,
      },
    },
  },
});

export default function EventDetailPage() {
  const router = useRouter();
  const { id } = router.query;
  const [event, setEvent] = React.useState(null);
  const [participants, setParticipants] = React.useState([]);
  const [isDrawing, setIsDrawing] = React.useState(false);

  React.useEffect(() => {
    if (id) {
      fetch(`/api/events/${id}`)
        .then(res => res.json())
        .then(data => setEvent(data));
      
      fetch(`/api/events/${id}/participants`)
        .then(res => res.json())
        .then(data => setParticipants(data));
    }
  }, [id]);

  const handleDraw = async () => {
    if (!confirm('정말로 추첨을 시작하고 기프티콘을 발송하시겠습니까?')) return;
    
    setIsDrawing(true);
    try {
      const res = await fetch(`/api/events/${id}/draw`, { method: 'POST' });
      const result = await res.json();
      if (res.ok) {
        alert(`추첨 완료! ${result.successCount}명에게 발송되었습니다.`);
        router.reload();
      } else {
        alert(`에러 발생: ${result.message}`);
      }
    } catch (err) {
      alert('네트워크 에러가 발생했습니다.');
    } finally {
      setIsDrawing(false);
    }
  };

  if (!event) return <Container>로딩 중...</Container>;

  return (
    <Container>
      <Head>
        <title>이벤트 관리 - {event.title}</title>
      </Head>
      
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title>{event.title}</Title>
          <StatusBadge status={event.status}>{event.status}</StatusBadge>
        </div>
        <div style={{ color: '$textMuted', fontSize: '0.875rem' }}>
          상품코드: {event.goods_code} | 당첨인원: {event.winner_count}명
        </div>
      </Card>

      <Card>
        <Title>👥 참여자 현황 ({participants.length}명)</Title>
        <ParticipantList>
          {participants.map((p, idx) => (
            <ParticipantItem key={idx}>
              <span>@{p.username}</span>
              <span style={{ fontSize: '0.75rem', color: '$textMuted' }}>
                {new Date(p.joined_at).toLocaleString()}
              </span>
            </ParticipantItem>
          ))}
          {participants.length === 0 && (
            <div style={{ textAlign: 'center', padding: '$4', color: '$textMuted' }}>
              아직 참여자가 없습니다.
            </div>
          )}
        </ParticipantList>
      </Card>

      {event.status === 'OPEN' && (
        <DrawButton 
          onClick={handleDraw} 
          disabled={isDrawing || participants.length === 0}
          isDrawing={isDrawing}
        >
          {isDrawing ? '🎰 추첨 및 발송 중...' : '🎯 추첨 및 텔레그램 발송 시작'}
        </DrawButton>
      )}
    </Container>
  );
}
