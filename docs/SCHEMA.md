# `analysis.json` schema (schema_version 2)

All values are **measured** unless marked otherwise. Times are seconds; timecodes are
`HH:MM:SS:FF` (non-drop-frame) at the analyzed video's fps. Paths are relative to the run folder.

```text
schema_version            int      bump = breaking change; `revideo report` refuses other versions
kind                      "video" | "image" | "audio"   (photo and audio layouts at the end)
tool                      {name, version, elapsed_sec,
                           detector: {engine, threshold, min_shot_len_frames, decoded_frames,
                                      flash_rejected_cuts, container_reported_frames?}}
source
  input                   str      URL or file given to `analyze`
  platform                {...}    yt-dlp metadata: title, uploader, upload_date, view_count, like_count,
                                   comment_count, tags, track, artist, description, webpage_url…
  video                   {path, fps, frame_count (decoded), width, height, duration_sec, aspect_ratio}
fingerprint
  duration_sec, shot_count, cuts_per_minute, asl_sec, median_shot_sec, shot_len_std_sec,
  shortest_longest_sec [min, max]
  pacing_window_sec       1 (≤20 s), 5 (≤3 min) or 10
  pacing_curve            [cuts per window]
  hook                    {first_shot_sec, cuts_in_first_3s, first_cut_tc}
  delivery_aspect_ratio, active_picture_aspect_ratio, active_picture_format_guess (inferred label)
  camera_moves            {type: count}
  shot_sizes_from_faces   {size: count}     inferred from face height; "no_face_detected" otherwise
  transitions             {hard_cut | fade_through_black | flash_white: count}
  global_palette          [{hex, share, lab[L,a,b]}]   k-means in CIE Lab, sorted by share
  global_grade            see "grade" below
  tempo_bpm_estimate, cuts_on_beat_ratio
shots[]
  index, start_frame, end_frame (exclusive), start_sec, end_sec, duration_sec, start_tc, end_tc
  transition_in           how this shot is entered
  keyframes               {in, mid, out: jpg path}      at 10 % / 50 % / 90 % of the shot
  keyframe_frames         {in, mid, out: frame index}
  palette                 [{hex, share, lab}]
  grade
    luma_mean, luma_p5_p50_p95, contrast_std, dynamic_range_p95_p5   (L* 0–100)
    crushed_blacks_pct, clipped_whites_pct, black_point_L, saturation_mean (0–1)
    white_balance_ab [a*, b*], shadows_tint_ab, highlights_tint_ab, shadows_hue, highlights_hue
    look_labels           inferred labels derived from the numbers
  framing
    visual_center_norm [x, y], dist_to_thirds_point, dist_to_center, framing_guess (inferred),
    symmetry, edge_density, negative_space,
    faces                 null | {count, largest_box_norm, largest_center_norm, headroom_norm, shot_size_estimate}
  active_area             {box [x0,y0,x1,y1], aspect_ratio, letterboxed}
  optics                  see "optics" below (measured on the mid keyframe)
  camera                  {type, pan_pct_w_per_s, tilt_pct_w_per_s, zoom_pct_per_s, roll_deg_per_s,
                           jitter, subject_motion_px, track_inlier_ratio, note}
  interpretation          {shot_size, angle, lens_mm_estimate, lighting, subject_action, on_screen_text,
                           function_in_story, cinematic_reference, prompt_image, prompt_video}
                          null until the agent fills them (observed / inferred)
  reference_match         null | verified film match (see below), written by `match-ref`
transcript                [{start, end, text}]     platform subtitles or faster-whisper
audio                     {duration_sec, loudness_mean_dbfs, loudness_peak_dbfs, silence_pct,
                           tempo_bpm_estimate, beat_times[], onset_times[], cuts_on_beat_ratio,
                           cuts_on_onset_ratio, loudness_curve_1s_db[], note,
                           key_estimate {key, confidence_r, runner_up, note},
                           spectral {energy_share_pct {band: %}, spectral_centroid_hz, brightness_guess,
                                     crest_factor_db}} | {error}
forensics                 see "forensics" below
artifacts                 {keyframes_dir, contact_sheet}
evidence_legend           which fields carry which evidence level
```

## `reference_matches.json` / `shots[].reference_match`

```text
shot, index (file), film {title, year, director, director_of_photography}
match                     true only if hash_distance ≤ max_distance AND correlation ≥ min_correlation
evidence                  "verified" | "unknown"
# when match = true
film_frame, film_seconds, film_timecode       exact frame in the reference file
correlation, hash_distance, coarse_hash_distance
crop                      "full" | "9:16@left|center|right" | "4:5@…" | "1:1@…"
mirrored                  bool
query_keyframe, query_frame, query_timecode   which frame of the analyzed video matched
film_shot_start_estimate  {seconds, timecode, assumes: "1x playback speed"}
# when match = false
closest                   {hash_distance, correlation} | null   — no film timecode is emitted
```

Timecodes refer to the **indexed file**. Editions (theatrical/extended), frame rates (24 vs 25 fps
PAL speed-up) and trims shift them — record which file you indexed.

## Shared blocks

```text
optics
  sharp_area_share         share of 8×8 cells with ≥35 % of the sharpest cell's detail
  focus_center_norm        [x, y] centre of the sharp cells
  depth_of_field_guess     shallow | medium | deep | undetermined (too little texture)   (inferred)
  vignette_corner_to_center, vignette_guess
  grain_noise_std, grain_guess                                   residual σ in the flattest 30 %
  clipped_highlights_pct, crushed_shadows_pct

forensics                  everything read from the file itself (measured; can be stripped/rewritten)
  kind, file {name, bytes}
  container                {format {tag: value}, streams [{type, desc, tags, codec, width, height, fps,
                            hdr (smpte2084 | arib-std-b67 | null), dolby_vision, bitrate_kbps}]}
  xmp                      {CreatorTool, Software, DigitalSourceType, CreateDate, ModifyDate,
                            history_agents[], camera_raw_settings {Exposure2012, Contrast2012, …}}
  exif                     (photos) {Make, Model, LensModel, FocalLength, FocalLengthIn35mmFilm, FNumber,
                            ExposureTime, ShutterSpeed, ISO, Software, DateTimeOriginal, …}
  png_text                 (PNG) {parameters (Automatic1111), prompt / workflow (ComfyUI JSON), Software, …}
  c2pa_manifest_present    byte signature only (not a validated manifest)
  tool_fingerprints        [{tool, category, means, evidence, level: "measured"}]
  tools_mentioned_in_post  [{…, level: "creator_mention"}]   from the post title/description/tags
  metadata_stripped_likely bool
```

## Photo (`kind: "image"`)

```text
source {input, platform, file} · image {width, height, aspect_ratio, format_guess}
forensics · camera_and_lens {Make, Model, LensModel, FocalLength…, field_of_view_class}
palette · grade · framing · active_area · optics · artifacts {preview}
```

## Audio (`kind: "audio"`)

```text
source {input, platform, file} · forensics · audio (as above, cuts_* = null) · transcript
```

Every run folder also gets `replication_plan.md` (see `revideo plan`).
