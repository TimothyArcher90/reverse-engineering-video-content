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

## Photo
1. **Capture or build**: `optics.focus_falloff_guess` decides the method. *Gradual*: shoot it with a fast
   lens, following the DOF advice. *Abrupt*: composite it, with a sharp subject layer over a blurred
   plate; no lens reproduces that edge.
2. **Subject**: position from `subject.box_px`, colors from `subject.palette` (the global palette is
   mostly background).
3. **Develop**: embedded Lightroom values 1:1 when present, then check them against the pixels (see
   the ⚠ lines in the plan). Otherwise build the recipe from `grade`, and add vignette and grain to
   match `optics`.
4. **AI path**: one image prompt. Put the subject palette first and use the aspect ratio from
   `image.format_guess`. The negative prompt has no motion terms.
5. **Validate**: `$RV compare runs/x runs/x-replica` gives the color, framing and optics scores.

## Audio
Tempo, key and energy per band come from `audio` [M]. Look for music with those values, or generate
it with a text-to-music model. Then match the level: crest factor and mean dBFS.

## D. Validate
`$RV analyze replica.mp4 -o runs/x-replica && $RV compare runs/x runs/x-replica`
Iterate on the lowest component score.
