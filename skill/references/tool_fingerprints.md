# Tool & workflow fingerprints

Heuristics to infer *how* something was produced. Every entry is a **tell-tale sign → hypothesis**.
All conclusions are **[I]** unless the creator states the tool or file metadata proves it.
Tools change their defaults often — treat this list as a starting point and keep it updated.

## 0. Read the file first (strongest evidence)
`analysis.json → forensics` holds what the file says about itself [M]. Rank evidence:
1. **Embedded recipes**: `xmp.camera_raw_settings` (Lightroom/ACR sliders, copy 1:1), `png_text.parameters`
   (Automatic1111: prompt, seed, sampler, CFG), `png_text.prompt`/`workflow` (ComfyUI graph).
2. **Tool strings**: `tool_fingerprints` (CreatorTool, encoder, handler names, QuickTime make/model/software).
3. **Declarations**: IPTC `DigitalSourceType` = `trainedAlgorithmicMedia` (AI-generated) or
   `compositeWithTrainedAlgorithmicMedia` (AI-edited); `c2pa_manifest_present` (validate before trusting).
4. **Creator mentions**: `tools_mentioned_in_post` = the post's own text. It is a claim, not proof: tag [O].
5. Pixels (tables below): always [I].

`metadata_stripped_likely: true` is normal for anything downloaded from Instagram/TikTok/YouTube: the
platform re-encodes. Then only 4 and 5 remain; say so instead of guessing a tool.

| Container sign [M] | Hypothesis |
|---|---|
| `encoder: Lavf…` only | muxed with FFmpeg libraries: a platform re-encode or many apps; not a specific editor |
| `handler_name: Core Media Video`, `com.apple.quicktime.*` | Apple device/framework; `model`/`software` give the iPhone and iOS |
| `com.android.version` | recorded on Android |
| `smpte2084` / `arib-std-b67` in the video stream | HDR (PQ / HLG): recent phone or HDR camera workflow |
| `major_brand: isom` + `Google` strings | YouTube/Google processing |

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
