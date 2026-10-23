import type { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';

export interface DetailItem {
  label: string;
  value: ReactNode;
}

// PUBLIC_INTERFACE
export default function DetailList({ items }: { items: DetailItem[] }) {
  /** Responsive two-column definition list. */
  return (
    <Box
      component="dl"
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', sm: 'minmax(140px, 220px) 1fr' },
        columnGap: 2,
        rowGap: 1,
        m: 0,
      }}
    >
      {items.map((item) => (
        <Box key={item.label} sx={{ display: 'contents' }}>
          <Typography component="dt" variant="body2" color="text.secondary">
            {item.label}
          </Typography>
          <Typography component="dd" variant="body2" sx={{ m: 0, wordBreak: 'break-word' }}>
            {item.value ?? '—'}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
