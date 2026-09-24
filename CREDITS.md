# Credits

This project's architecture was informed by reviewing these MIT-licensed projects. No code was
copied; ideas and structure were reimplemented.

| Project | What informed this project |
|---|---|
| [keng1304/video-breakdown](https://github.com/keng1304/video-breakdown) | Layered perception → structure → fingerprint → prompt architecture; per-shot quantitative composition/color/camera data; cuts-per-minute style fingerprint. Chosen as the architectural base: it was the most complete of the candidates reviewed. |
| [whaojie797-design/video-reverse-engineering](https://github.com/whaojie797-design/video-reverse-engineering) | Agent-skill workflow; "never describe frames you have not seen"; three deliverables (shot list, prompts, replication guide with AI and live-action paths); rights reminder. |
| [Newuxtreme/watch-video-skill](https://github.com/Newuxtreme/watch-video-skill) | Pattern of yt-dlp + frames + transcript handed to a vision-capable agent. |
| [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Used (optional dependency) for shot boundary detection. |

What this project adds: evidence tagging on every claim, exact film-frame matching through
reel crops and mirroring, a cinematic-reference verification protocol, tool/workflow fingerprints,
cross-platform lightweight dependencies (no torch), and round-trip fidelity scoring.
