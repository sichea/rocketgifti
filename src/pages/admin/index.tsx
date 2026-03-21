import React from 'react';
import Head from 'next/head';
import { styled, keyframes } from '../../stitches.config';

const Container = styled('div', {
  padding: '$4',
  maxWidth: '800px',
  margin: '0 auto',
  minHeight: '100vh',
  backgroundColor: '$bgSurface',
});

const Title = styled('h1', {
  fontSize: '1.5rem',
  fontWeight: '700',
  marginBottom: '$4',
  color: '$textPrimary',
});

const Grid = styled('div', {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
  gap: '$4',
});

const ProductCard = styled('div', {
  backgroundColor: 'white',
  borderRadius: '$md',
  padding: '$3',
  boxShadow: '$sm',
  cursor: 'pointer',
  transition: 'transform 0.2s, box-shadow 0.2s',
  border: '2px solid transparent',

  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: '$md',
  },

  variants: {
    selected: {
      true: {
        borderColor: '$primary',
        backgroundColor: '$primaryLight',
      },
    },
  },
});

const ProductImage = styled('img', {
  width: '100%',
  aspectRatio: '1/1',
  objectFit: 'cover',
  borderRadius: '$sm',
  marginBottom: '$2',
});

const ProductName = styled('div', {
  fontSize: '0.875rem',
  fontWeight: '500',
  color: '$textPrimary',
  marginBottom: '$1',
});

const ProductPrice = styled('div', {
  fontSize: '0.75rem',
  color: '$textSecondary',
});

const FloatingButton = styled('button', {
  position: 'fixed',
  bottom: '$6',
  right: '$6',
  backgroundColor: '$primary',
  color: 'white',
  padding: '$3 $6',
  borderRadius: '$full',
  fontSize: '1rem',
  fontWeight: '600',
  border: 'none',
  boxShadow: '$lg',
  cursor: 'pointer',
  transition: 'transform 0.2s, backgroundColor 0.2s',

  '&:hover': {
    backgroundColor: '$primaryHover',
    transform: 'scale(1.05)',
  },

  '&:disabled': {
    backgroundColor: '$gray200',
    cursor: 'not-allowed',
  },
});

export default function AdminPage() {
  const [products, setProducts] = React.useState([]);
  const [selectedProduct, setSelectedProduct] = React.useState(null);

  React.useEffect(() => {
    // 상품 목록 가져오기 로직 (실제로는 Supabase 연동)
    fetch('/api/products')
      .then(res => res.json())
      .then(data => setProducts(data))
      .catch(err => console.error(err));
  }, []);

  const handleCreateEvent = async (product) => {
    const title = `${product.name} 이벤트`;
    const winnerCount = prompt('당첨 인원을 입력해주세요 (숫자)', '1');
    if (!winnerCount) return;

    try {
      const res = await fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goods_code: product.goods_code,
          title,
          winner_count: parseInt(winnerCount),
          admin_id: 0, // 나중에 텔레그램 연동 시 실제 ID 사용
        }),
      });
      const newEvent = await res.json();
      if (res.ok) {
        window.location.href = `/admin/event/${newEvent.event_id}`;
      } else {
        alert('이벤트 생성 실패');
      }
    } catch (err) {
      alert('네트워크 오류');
    }
  };

  return (
    <Container>
      <Head>
        <title>로켓기프티 - 어드민</title>
      </Head>
      <Title>🎁 상품 선택하기</Title>
      
      <Grid>
        {products.map((product) => (
          <ProductCard 
            key={product.goods_code}
            selected={selectedProduct?.goods_code === product.goods_code}
            onClick={() => handleCreateEvent(product)}
          >
            <ProductImage src={product.image_url} alt={product.name} />
            <ProductName>{product.name}</ProductName>
            <ProductPrice>{product.price.toLocaleString()}원</ProductPrice>
          </ProductCard>
        ))}
      </Grid>
    </Container>
  );
}
