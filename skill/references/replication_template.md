# Replication template

Durations, aspect ratio, palette and camera moves must come from `analysis.json` **[M]**.

## A. AI path (per shot)
```
Shot NN · in TC · duration X.XX s [M] · AR 9:16 [M]
Image prompt:  <subject>, <shot size>, <angle>, <composition>, <lighting>, <palette: #hex #hex #hex>,
               <lens/DOF>, <texture: grain/halation>, <reference style (no film titles if the model refuses)>
Motion prompt: <camera move from `camera.type` [M] + speed>, <subject action>, <duration>
Negative:      <what broke in previous attempts: extra fingers, text artifacts, flicker…>
Model:         <image model> → <video model>   (choose per shot: realism, motion, consistency)
Consistency:   character/style reference used, seed, first/last frame chaining
```

## B. Live-action path
| Shot | Size / angle | Lens (FF eq.) | Rig | Light setup | Blocking | Takes note |
|---|---|---|---|---|---|---|

Gear list · crew · locations · shooting order (group by setup, not by edit order).

## C. Post
1. **Edit list (EDL)**: shot order with exact durations [M]; cut-on-beat targets from `audio.beat_times`.
2. **Grade**: recipe from `color_grade_recipes.md`.
3. **Sound**: tempo [M], genre [I], SFX hits at `onset_times`, VO, mix/ducking.
4. **Graphics/captions**: font (closest match), size, position, animation, timing vs transcript.
5. **Export**: platform specs (resolution, AR, fps, bitrate, safe zones) — verify current platform specs.

## D. Validate
`$RV analyze replica.mp4 -o runs/x-replica && $RV compare runs/x runs/x-replica`
Iterate on the lowest component score.
