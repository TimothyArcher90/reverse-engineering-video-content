# Tool & workflow fingerprints

Heuristics to infer *how* something was produced. Every entry is a **tell-tale sign → hypothesis**.
All conclusions are **[I]** unless the creator states the tool or file metadata proves it.
Tools change their defaults often — treat this list as a starting point and keep it updated.

## Capture
| Sign | Hypothesis |
|---|---|
| Smartphone-typical wide lens distortion, deep focus at close range, HDR tone-mapped skies | Phone camera |
| Shallow DOF with optical bokeh, smooth focus pulls | Interchangeable-lens camera, fast lens |
| Synthetic/uneven background blur edges around hair | Phone "cinematic/portrait" mode |
| Horizontal flares + oval bokeh + 2.39 AR | Anamorphic lens (or anamorphic emulation filter if flare is uniform) |
| Floating, horizon-locked motion, `jitter` low with steady translation [M] | Gimbal / Steadicam |
| High `jitter` [M] | Handheld |
| High altitude, smooth arcs, top-down | Drone |
| Rolling-shutter skew on fast pans | CMOS sensor phone/mirrorless |

## Edit
| Sign | Hypothesis |
|---|---|
| Word-by-word pop-up captions, bold sans with stroke, auto emoji | Auto-caption feature of mobile editors (e.g. CapCut) or dedicated caption apps |
| Template-synchronized cuts: `cuts_on_beat_ratio` very high [M] + stock transitions | Beat-sync template |
| Speed ramps with optical-flow smear | Velocity/speed-curve edit |
| J/L cuts, audio leading picture | NLE editing (Premiere, Resolve, Final Cut) |
| Complex tracked graphics, kinetic type, 3D camera on text | After Effects / motion-graphics tool |

## Color
| Sign | Hypothesis |
|---|---|
| Lifted black point [M] + low contrast + grain | Film-emulation LUT/plugin |
| Teal shadows / orange highlights [M] | Blockbuster "teal-orange" grade |
| Clipped highlights + crushed blacks [M] + saturated | Phone auto-HDR off / aggressive preset |

## Generative AI (video/image)
| Sign | Hypothesis |
|---|---|
| Morphing hands/text, objects appearing/disappearing between frames, inconsistent reflections | AI video generation |
| Shots of 4–10 s with one continuous camera move and no cuts inside | Typical clip length of text/image-to-video models |
| Perfectly consistent lighting on a face across impossible moves | AI avatar / lip-sync |
| Lip-sync with slight mouth-region blur | Talking-avatar or dubbing tool |
| Visible C2PA/Content Credentials, platform "AI-generated" label | Declared AI (can become **[V]**) |

## Metadata that can upgrade to [V]
- Platform metadata in `source.platform` (music `track`/`artist`, description credits, tags).
- Creator's caption/comments naming tools.
- Container metadata (encoder string) — only when the file is original, not re-encoded by a platform.
