# From measurements to a grade recipe

Map `global_grade` (and per-shot `grade`) values to concrete grading steps. Values are guidelines.

| Measured field | Reading | Recipe step |
|---|---|---|
| `black_point_L` > 6 | lifted/matte blacks | Raise lift / curve toe so black ≈ measured L |
| `crushed_blacks_pct` > 8 | crushed | Pull lift down, add contrast in the toe |
| `clipped_whites_pct` > 5 | blown | Gain up / high-key; accept clipping |
| `contrast_std` < 14 | flat | Low-contrast S-curve or log-like look |
| `contrast_std` > 28 | punchy | Strong S-curve |
| `saturation_mean` < 0.18 | desaturated | Global sat −30 to −60 %, keep skin |
| `white_balance_ab` b > 6 | warm | Shift WB/temperature toward amber |
| `white_balance_ab` b < −4 | cool | Shift toward blue |
| `shadows_hue` / `highlights_hue` differ | split-tone | Tint shadows and highlights with those hues (color wheels: lift / gain) |
| palette hexes | target swatches | Use as reference swatches in the grading tool; check with the vectorscope |

## Recipe format for the dossier
```
Base: Rec.709, contrast S-curve medium (σ target 22 [M])
Black point: L 8 (lifted) [M] · White point: L 94 [M]
WB: warm, b* +9 [M]
Split-tone: shadows teal (a −6, b −8) [M] / highlights orange (a +8, b +18) [M]
Saturation: 0.38 mean [M] → −15 % global, skin protected
Texture: fine grain, slight halation [O]
Closest family: film-emulation LUT [I]
```
