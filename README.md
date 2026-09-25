# Reverse Engineering Video — Content

[![tests](https://github.com/TimothyArcher90/reverse-engineering-video-content/actions/workflows/tests.yml/badge.svg)](https://github.com/TimothyArcher90/reverse-engineering-video-content/actions/workflows/tests.yml)
[![daily](https://github.com/TimothyArcher90/reverse-engineering-video-content/actions/workflows/daily.yml/badge.svg)](https://github.com/TimothyArcher90/reverse-engineering-video-content/actions/workflows/daily.yml)
![python](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)

**El copycat maestro.** Ingeniería inversa de cualquier **video, foto o sonido**: qué es, cómo se hizo,
con qué herramientas, de qué película viene y cómo replicarlo según tu presupuesto y condiciones.
Funciona como herramienta de línea de comandos y como **skill de Claude** que actúa sin hacer preguntas.

| Le das | Obtienes |
|---|---|
| Video (reel, TikTok, anuncio, videoclip, escena) | Cortes, ritmo, planos, cámara, color, óptica, música (BPM, tonalidad), referencias con fotograma exacto |
| Foto (JPG, PNG, WebP) | Paleta, gradación, profundidad de campo, viñeta, grano, encuadre, cámara y lente (EXIF) |
| Audio (MP3, WAV, M4A…) | BPM, tonalidad, balance espectral, dinámica, transcripción |
| Cualquiera | **Todo lo que el archivo dice de sí mismo**: ajustes de Lightroom, prompt y seed de IA, app de edición, móvil, HDR, declaración de IA, C2PA |
| Cualquiera | **Plan de réplica** por presupuesto (móvil / creador / pro / solo IA) con prompts por plano, y una **nota 0–100** de tu réplica |

Cada afirmación lleva su nivel de evidencia: **[M]** medido · **[O]** observado · **[I]** inferido ·
**[V]** verificado · **[?]** desconocido. Una referencia o herramienta es hipótesis hasta que se verifica.

<p align="center"><img src="docs/img/report-dark.png" width="760"
alt="report.html: stat tiles, edit timeline, pacing chart, palette and a verified Big Buck Bunny frame match"></p>
<p align="center"><sub><code>report.html</code> de un reel derivado de <i>Big Buck Bunny</i> (recorte 9:16, espejado y re-gradado):
el plano 0 se verifica en el fotograma 92 (00:00:03:20). Imagen: © Blender Foundation, CC BY 3.0.</sub></p>

## Arquitectura

```
 video · foto · audio · URL
     │
 L0  ingest ─────── yt-dlp (video + subtítulos + metadatos de la plataforma) o descarga directa
 L1  forense ────── etiquetas del contenedor, EXIF, XMP (ajustes de Lightroom), parámetros de IA en PNG,
                    declaración IPTC de IA, C2PA, HDR → huellas de herramientas con su evidencia
 L2  cortes ─────── detector propio (color + estructura + rechazo de destellos), fundidos, keyframes
 L3  por plano ──── paleta · gradación · encuadre · caras · óptica (profundidad de campo, viñeta, grano)
                    · cámara (pan/tilt/zoom/roll, en mano vs estabilizada)
 L4  sonido ─────── loudness · BPM · beats · tonalidad · espectro · % de cortes sobre el beat
 L5  huella ─────── ASL, cortes/min, curva de ritmo, gancho 0–3 s, look global
     │                         ▲ todo lo anterior es MEDIDO → analysis.json, report.html/.md
 PLAN ───────────── replication_plan.md: EDL, rig por presupuesto, receta de color, óptica, prompts
 L6  agente ─────── skill/SKILL.md: observa, reúne evidencia, propone referencias, adapta el plan
 REF match-ref ──── fotograma exacto en la película → [V]
 QA  compare ────── réplica vs original → 0–100 (video, foto o audio)
 DAILY ──────────── CI diario: dependencias nuevas + tests + enlaces del catálogo + .skill fresco
```

## Instalación

```bash
git clone https://github.com/TimothyArcher90/reverse-engineering-video-content
cd reverse-engineering-video-content
pip install -e ".[full]"          # numpy, opencv, yt-dlp, ffmpeg embebido, pyscenedetect (opcional)
revideo doctor
```
Opcional: `pip install -e ".[whisper]"` para transcribir cuando no hay subtítulos.

### Como skill (sin instalar nada a mano)

El skill trae la herramienta dentro y las dependencias se instalan solas la primera vez.

| Dónde | Cómo |
|---|---|
| claude.ai / app de Claude | Descarga `reverse-engineering-video.skill` de la [última release](https://github.com/TimothyArcher90/reverse-engineering-video-content/releases/latest) (o `python tools/build_skill.py`) y súbelo en la sección de Skills de la configuración |
| Claude Code | `./install_skill.sh` (enlaza `skill/`) o descomprime el `.skill` en `~/.claude/skills/` |

Luego pide *"haz ingeniería inversa de este reel: &lt;link&gt;"*. En claude.ai, las descargas desde URL
dependen de que el entorno de código tenga salida a internet; si no, sube el archivo de video.

## Uso

```bash
# 1. Medir (video, foto o audio; el tipo sale de la extensión)
revideo analyze "https://www.instagram.com/reel/..." -o runs/mi-reel
revideo analyze foto.jpg -o runs/foto          # EXIF, Lightroom, óptica, color
revideo analyze cancion.mp3 -o runs/cancion    # BPM, tonalidad, espectro
#    → analysis.json · report.html · report.md · replication_plan.md (+ dossier, keyframes en video)

# 2. Verificar una referencia (necesitas el archivo de la película, legalmente)
revideo index-ref pelicula.mkv -o refs/pelicula --title "Título" --director "Dir." --dp "DoP" --year 1999
revideo match-ref runs/mi-reel refs/pelicula.npz
#   shot   3 [out 00:00:05:10] → Título @ 01:02:14:07 (frame 89623, r=0.97, dist 4, crop 9:16@center, mirrored)

# 3. Tras hacer tu réplica
revideo analyze replica.mp4 -o runs/mi-reel-replica
revideo compare runs/mi-reel runs/mi-reel-replica      # fidelidad 0–100 por componente

revideo report runs/mi-reel                            # regenerar informes
revideo plan runs/mi-reel                              # regenerar el plan de réplica
revideo tools                                          # catálogo de herramientas por presupuesto
```

| Comando | Qué hace |
|---|---|
| `analyze` | Mide todo (video, foto o audio) y genera informes y plan. `--kind`, `--engine scenedetect`, `--threshold`, `--no-audio`, `--no-motion`, `--whisper small` |
| `index-ref` | Huella perceptual de una película (solo hashes, no imágenes) |
| `match-ref` | Fotograma exacto por plano; se fusiona en `analysis.json` e informes |
| `compare` | Fidelidad 0–100 de una réplica. Video: ritmo 30 %, color 30 %, encuadre 15 %, cámara 15 %, sonido 10 % · foto: color, encuadre, óptica · audio: tempo, tonalidad, espectro, dinámica |
| `plan` | Plan de réplica por presupuesto y condiciones |
| `tools` | Catálogo de herramientas (modelo de precio y enlace oficial; precios **no** verificados) |
| `report` | Regenera `report.md` y `report.html` |
| `doctor` | Comprueba dependencias |

## Validación

31 tests con verdad conocida en CI (Linux, macOS, Windows) + pruebas con metraje real
([detalle](docs/VALIDATION.md)):

| Prueba real | Resultado |
|---|---|
| Montaje real de 5 planos (H.264) | 4/4 cortes, error máx. 1 fotograma, 0 falsos positivos |
| Clip de fuegos artificiales (oscuro, destellos) | 1 plano correcto (v0.1 daba 10 planos y 8 fundidos falsos) |
| Reel derivado: recorte 9:16 + espejo + re-gradado + recompresión | Fotograma exacto 92, inicio del plano 2,500 s exacto |
| Foto con EXIF + XMP de Lightroom (sintética) | Cámara, ajustes de Lightroom 1:1, foco en el centro, viñeta |
| PNG con parámetros de Stable Diffusion (sintético) | Prompt, seed y sampler recuperados |
| Acorde de La menor a 120 BPM (sintético) | 120,0 BPM · La menor |

## Límites

| Puede | No puede (o no sin ayuda) |
|---|---|
| Medir cortes, ritmo, color, encuadre, óptica, movimiento y sonido de forma reproducible | Saber qué app se usó si la plataforma borró los metadatos (lo normal en Instagram/TikTok): entonces es inferencia |
| Leer ajustes de Lightroom, prompts de IA, app y móvil **cuando el archivo los conserva** | Dar precios actuales sin verificar: el catálogo trae el modelo de precio y el enlace oficial |
| Encontrar el fotograma exacto de una película **si tienes el archivo** | Identificar una película "de memoria" con certeza: el agente propone candidatos [I] |
| Detectar recortes 9:16/4:5/1:1 (izq./centro/der.) y espejado | Recortes con zoom o posición arbitraria, cambios de velocidad (menor recall) |
| Puntuar la fidelidad estructural de una réplica | Distinguir zoom de dolly solo con flujo 2D · derechos de uso (ver `docs/LEGAL.md`) |

## Documentación
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — estándares de ingeniería inversa y límites de cada métrica
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — todos los campos de `analysis.json` y de las coincidencias
- [`docs/VALIDATION.md`](docs/VALIDATION.md) — qué se probó, cómo y con qué resultado
- [`skill/SKILL.md`](skill/SKILL.md) — flujo del agente (7 fases) · [`skill/references/`](skill/references)
- [`src/revideo/data/tools.json`](src/revideo/data/tools.json) — catálogo de herramientas (edítalo para añadir las tuyas)
- [`docs/LEGAL.md`](docs/LEGAL.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CHANGELOG.md`](CHANGELOG.md) · [`CREDITS.md`](CREDITS.md)

Licencia MIT.
