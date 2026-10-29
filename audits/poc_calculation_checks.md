# Proof-of-concept calculation checks

All 15 rows independently recomputed from exported adjusted prices using Decimal arithmetic. Day-0 ETF returns, benchmark returns, return differences, and three-session sums agree to within 1e-9 percentage points. This checks arithmetic and window selection, not independent vendor accuracy.

Five XLK examples for manual inspection; values below are rounded only for display.

| Meeting | Previous adjusted close | Event adjusted close | ETF return (%) | SPY return (%) | Difference (pp) |
|---|---:|---:|---:|---:|---:|
| 2024-06-12 | 108.44655609 | 110.84531403 | 2.211926 | 0.821314 | 1.390612 |
| 2024-07-31 | 103.57428741 | 107.96080017 | 4.235137 | 1.625453 | 2.609684 |
| 2024-09-18 | 108.14337921 | 107.15653992 | -0.912529 | -0.296585 | -0.615944 |
| 2024-11-07 | 115.34692383 | 117.35876465 | 1.744165 | 0.773225 | 0.970941 |
| 2024-12-18 | 118.62419891 | 114.79824829 | -3.225270 | -2.980359 | -0.244911 |
