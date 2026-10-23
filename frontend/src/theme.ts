import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: { mode: 'light', primary: { main: '#1f4e79' }, secondary: { main: '#00897b' }, background: { default: '#f4f6f9' } },
  shape: { borderRadius: 8 },
  typography: { fontFamily: '"Inter", "Segoe UI", Roboto, Arial, sans-serif', h1: { fontSize: '1.6rem', fontWeight: 600 }, h2: { fontSize: '1.25rem', fontWeight: 600 } },
  components: { MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: 'none' } } } },
});
export default theme;
