import type { AppProps } from 'next/app';
import { globalCss } from '../../stitches.config';

const globalStyles = globalCss({
  '*': { margin: 0, padding: 0, boxSizing: 'border-box' },
  body: {
    fontFamily: '$sans',
    backgroundColor: '$bgBase',
    color: '$textBase',
    WebkitFontSmoothing: 'antialiased',
  },
  a: { textDecoration: 'none', color: 'inherit' },
});

export default function App({ Component, pageProps }: AppProps) {
  globalStyles();
  return <Component {...pageProps} />;
}
