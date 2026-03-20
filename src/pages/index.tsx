import { styled } from '../../stitches.config';
import Head from 'next/head';

const Container = styled('div', {
  minHeight: '100vh',
  backgroundColor: '$bgSurface',
});

const Navbar = styled('nav', {
  backgroundColor: '$bgBase',
  borderBottom: '1px solid $gray200',
  padding: '$3 $5',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
});

const Logo = styled('h1', {
  fontSize: '20px',
  fontWeight: '700',
  color: '$primary',
  letterSpacing: '-0.5px',
});

const Main = styled('main', {
  maxWidth: '1200px',
  margin: '0 auto',
  padding: '$6 $5',
});

const Header = styled('div', {
  marginBottom: '$5',
});

const Title = styled('h2', {
  fontSize: '28px',
  fontWeight: '700',
  color: '$textBase',
  letterSpacing: '-1px',
});

const Subtitle = styled('p', {
  color: '$textMuted',
  marginTop: '$1',
  fontSize: '16px',
});

const Grid = styled('div', {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
  gap: '$4',
  marginTop: '$4',
});

const Card = styled('div', {
  backgroundColor: '$bgBase',
  borderRadius: '$lg',
  padding: '$4',
  boxShadow: '$sm',
  border: '1px solid $gray200',
  transition: 'transform 0.2s, box-shadow 0.2s',
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: '$md',
  },
});

const CardTitle = styled('h3', {
  fontSize: '14px',
  color: '$textMuted',
  fontWeight: '500',
  textTransform: 'uppercase',
  letterSpacing: '1px',
});

const CardValue = styled('p', {
  fontSize: '36px',
  fontWeight: '700',
  color: '$primaryHover',
  marginTop: '$2',
  letterSpacing: '-1px',
});

// 하단 공간 - 향후 표(Table)나 그래프를 추가할 공간
const BlankState = styled('div', {
  marginTop: '$6',
  padding: '$6',
  borderRadius: '$lg',
  border: '2px dashed $gray200',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  color: '$textMuted',
  fontSize: '18px',
});

export default function Home() {
  return (
    <Container>
      <Head>
        <title>RocketGifti | Admin Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <Navbar>
        <Logo>RocketGifti 🚀</Logo>
      </Navbar>
      <Main>
        <Header>
          <Title>대시보드 개요</Title>
          <Subtitle>성공적인 실시간 기프티콘 발송 로봇 현황</Subtitle>
        </Header>
        <Grid>
          <Card>
            <CardTitle>오늘 발송 완료</CardTitle>
            <CardValue>1,234 건</CardValue>
          </Card>
          <Card>
            <CardTitle>미처리 발송 대기</CardTitle>
            <CardValue>5 건</CardValue>
          </Card>
          <Card>
            <CardTitle>활성 상품 목록 (동기화 됨)</CardTitle>
            <CardValue>51 개</CardValue>
          </Card>
        </Grid>
        
        <BlankState>
          이곳에 주문내역 목록과 자세한 통계 그래프가 연동될 예정입니다.
        </BlankState>
      </Main>
    </Container>
  );
}
