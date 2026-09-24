# Reverse Engineering Video — Content

**Ingeniería inversa total de contenido audiovisual.** Le das un video (reel, TikTok, Short, anuncio,
videoclip, escena de película) y obtienes:

1. **Qué es y cómo está hecho**: cortes, ritmo, planos, movimiento de cámara, encuadre, luz, paleta y
   gradación de color, sonido, tipografía.
2. **De dónde viene**: referencias cinematográficas (película, año, director, director de fotografía)
   con **fotograma y timecode exactos** cuando se puede verificar.
3. **Con qué herramientas y qué flujo de trabajo** se produjo probablemente (cámara, editor, IA,
   plantillas), siempre con la señal que lo delata.
4. **Cómo replicarlo**: plan con IA, plan con rodaje real, postproducción y un pack de prompts por plano.
5. **Qué tan fiel quedó tu réplica**: puntuación 0–100 comparando original y réplica.

Cada afirmación lleva una etiqueta de evidencia: **[M]** medido · **[O]** observado · **[I]** inferido ·
**[V]** verificado · **[?]** desconocido. Nada se inventa: una referencia es hipótesis hasta que se verifica.

## Cómo funciona

```
 video / URL
     │
 L0  ingest ─────── yt-dlp: video + subtítulos + metadatos de la plataforma
 L1  shots ──────── cortes (PySceneDetect o detector propio) · transiciones · keyframes · contact sheet
 L2  por plano ──── paleta Lab · gradación (key, contraste, punto de negro, WB, split-tone)
                    encuadre (área activa/letterbox, tercios, simetría, caras → tamaño de plano)
                    cámara (pan/tilt/zoom/roll por segundo, cámara en mano vs estabilizada)
 L3  sonido ─────── loudness · onsets · BPM · beats · % de cortes sobre el beat
 L4  huella ─────── ASL, cortes/min, curva de ritmo, gancho 0–3 s, paleta y look globales
     │                                   ▲ todo lo anterior es MEDIDO
 L5  agente ─────── skill/SKILL.md: observa keyframes, propone referencias, infiere stack,
                    escribe el dossier (16 secciones), plan de réplica y prompts
     │
 REF match-ref ──── fotograma exacto de la película (pHash multi-recorte 9:16/4:5/1:1, espejo) → [V]
 QA  compare ────── réplica vs original → fidelidad 0–100
```

## Instalación

```bash
git clone https://github.com/TimothyArcher90/reverse-engineering-video-content
cd reverse-engineering-video-content
pip install -e ".[full]"          # numpy, opencv, pyscenedetect, yt-dlp, ffmpeg embebido
revideo doctor
```
Opcional: `pip install -e ".[whisper]"` para transcribir cuando no hay subtítulos.

### Como skill de Claude Code
```bash
./install_skill.sh                # enlaza skill/ en ~/.claude/skills/reverse-engineering-video
```
Luego en Claude Code: *"haz ingeniería inversa de este reel: <link>"*.

## Uso

```bash
# 1. Medir
revideo analyze "https://www.instagram.com/reel/..." -o runs/mi-reel

# 2. Verificar una referencia de película (necesitas el archivo de la película, legalmente)
revideo index-ref pelicula.mkv -o refs/pelicula.npz --title "Título" --director "Director" --year 1999
revideo match-ref runs/mi-reel refs/pelicula.npz
#   shot   3 → Título @ 01:02:14:07 (frame 89623, dist 4, crop 9:16, mirrored)

# 3. Tras hacer tu réplica
revideo analyze replica.mp4 -o runs/mi-reel-replica
revideo compare runs/mi-reel runs/mi-reel-replica
```

Salida en `runs/<nombre>/`: `analysis.json` (todo lo medido), `report.md`, `dossier.md` (plantilla que
completa el agente), `contact_sheet.jpg`, `keyframes/`, `audio.wav`, `reference_matches.json`.

## Qué puede y qué no puede hacer

| Puede | No puede (o no sin ayuda) |
|---|---|
| Medir cortes, ritmo, color, encuadre, movimiento y sonido de forma reproducible | Saber con certeza qué app o cámara se usó: eso es inferencia salvo que el autor lo diga |
| Encontrar el fotograma exacto de una película **si tienes el archivo** | Identificar una película "de memoria" con certeza: el agente propone candidatos [I] |
| Detectar recortes 9:16/4:5/1:1 y espejado respecto a la película | Distinguir zoom de dolly solo con flujo 2D |
| Puntuar la fidelidad estructural de una réplica | Garantizar derechos: reutilizar metraje, música o caras ajenas requiere permiso (ver `docs/LEGAL.md`) |

## Documentación
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — estándares de ingeniería inversa aplicados y límites de cada métrica.
- [`skill/SKILL.md`](skill/SKILL.md) — flujo del agente (7 fases).
- [`skill/references/`](skill/references) — protocolo de referencias cinematográficas, huellas de herramientas, recetas de color, glosario ES/EN, plantilla de réplica.
- [`docs/LEGAL.md`](docs/LEGAL.md) — uso responsable.
- [`CREDITS.md`](CREDITS.md) — proyectos que inspiraron el diseño.

## Estado
v0.1 — funcional y con tests sobre videos sintéticos. Aún no validado a escala con contenido real;
los umbrales (cortes, looks, fidelidad) son puntos de partida. Contribuciones bienvenidas.

Licencia MIT.
