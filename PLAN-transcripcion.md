# Plan: Transcripción de vídeos de YouTube minimizando tokens

> Objetivo: pasar un **link de YouTube** y obtener un **archivo `.md` con la transcripción**, gastando la **menor cantidad de tokens posible**.

---

## 1. Idea clave (lo más importante)

**La transcripción NO necesita un LLM.** YouTube ya genera y almacena
subtítulos (manuales o automáticos) para casi todos los vídeos. Descargar esos
subtítulos cuesta **0 tokens** porque no pasa por ningún modelo de lenguaje.

Por tanto, la estrategia óptima en coste es:

1. **Intentar bajar los subtítulos existentes** del vídeo → coste de tokens = **0**.
2. **Solo si el vídeo no tiene subtítulos**, recurrir a transcripción por audio
   (ASR tipo Whisper). Esto tampoco gasta tokens de un LLM si se hace en local.
3. **Opcional y aparte**: usar el LLM *únicamente* para tareas de valor añadido
   (resumir, limpiar, traducir). Eso sí gasta tokens, así que se deja como paso
   opt-in, no por defecto.

Conclusión: para el caso "dame la transcripción", el flujo recomendado gasta
**cero tokens de LLM**.

---

## 2. Comparativa de opciones investigadas

| Opción | Tokens LLM | Requiere API key | Coste $ | Fiabilidad | Notas |
|---|---|---|---|---|---|
| **`youtube-transcript-api`** (Python) | 0 | No | Gratis | Media-alta | Lee subtítulos directamente. v1.2.4 (ene 2026), soporta Python 3.8–3.14. Puede romperse si YouTube cambia internals. |
| **`yt-dlp` `--write-auto-subs`** | 0 | No | Gratis | Alta | Descarga `.vtt`/`.srt`; muy mantenido. Hay que limpiar timestamps. Mejor para fallback y robustez. |
| **API gestionada** (Supadata, TranscriptAPI, Apify…) | 0 | Sí | De pago | Alta | Maneja proxies/bloqueos de YouTube. Útil en producción o a escala. |
| **Whisper / faster-whisper (local)** | 0 | No | Gratis (CPU/GPU local) | Alta | Fallback cuando NO hay subtítulos. Transcribe desde el audio. |
| **OpenAI Whisper API / Deepgram** | 0 LLM (se paga por minuto de audio) | Sí | De pago | Alta | Fallback en la nube si no hay GPU local. |
| **Pasar el audio/vídeo a un LLM multimodal** | MUCHOS | Sí | Caro | Alta | ❌ Lo contrario del objetivo. Descartado. |

> Nota de tokens: solo el LLM consume "tokens". Whisper y las APIs de ASR cobran
> por minuto/segundo de audio, no por tokens. Por eso siguen siendo "0 tokens".

---

## 3. Arquitectura recomendada

```
        link de YouTube
              │
              ▼
   ┌──────────────────────┐
   │ 1. Extraer video_id  │
   └──────────┬───────────┘
              ▼
   ┌──────────────────────────────┐
   │ 2. ¿Tiene subtítulos?         │
   │   a) youtube-transcript-api   │  ← intento principal (0 tokens)
   │   b) yt-dlp --write-auto-subs │  ← fallback robusto (0 tokens)
   └──────────┬───────────────────┘
       sí ┌───┴───┐ no
          ▼       ▼
   ┌──────────┐  ┌─────────────────────────────┐
   │ usar     │  │ 3. Fallback ASR:            │
   │ subtítulos│  │   yt-dlp baja solo audio →  │  ← solo si hace falta
   └────┬─────┘  │   faster-whisper transcribe │     (0 tokens LLM)
        │        └──────────────┬──────────────┘
        └────────────┬──────────┘
                     ▼
   ┌────────────────────────────────────┐
   │ 4. Limpiar (quitar timestamps,      │
   │    duplicados de subtítulos auto)   │
   └────────────────┬───────────────────┘
                    ▼
   ┌────────────────────────────────────┐
   │ 5. Generar archivo .md              │
   │   (título, URL, fecha + texto)      │
   └────────────────┬───────────────────┘
                    ▼
   (opcional) 6. LLM: resumen/limpieza  ← único paso que gasta tokens
```

---

## 4. Stack propuesto

- **Lenguaje:** Python 3.11+
- **Dependencias mínimas:**
  - `youtube-transcript-api` — intento principal de subtítulos.
  - `yt-dlp` — fallback de subtítulos y descarga de audio.
  - `faster-whisper` — ASR local (solo si no hay subtítulos).
- **Sin API key obligatoria** para el camino feliz.

---

## 5. Pasos de implementación

1. **Setup del repo**
   - `requirements.txt` con las dependencias.
   - Estructura: `src/transcribe.py`, `output/` para los `.md`.

2. **Parseo del link** → extraer `video_id` (soportar `youtu.be/`,
   `watch?v=`, `shorts/`, `embed/`).

3. **Obtener subtítulos (camino feliz, 0 tokens)**
   - Intentar `youtube-transcript-api` (preferir manual > auto; idioma
     configurable, p. ej. `es` y `en`).
   - Si falla, `yt-dlp --write-auto-subs --skip-download --sub-format vtt`.

4. **Fallback ASR (solo si no hay subtítulos)**
   - `yt-dlp -f bestaudio -x --audio-format mp3` para bajar solo el audio.
   - Transcribir con `faster-whisper` (modelo `small`/`medium` según CPU/GPU).

5. **Limpieza del texto**
   - Quitar timestamps y líneas duplicadas (típico en subtítulos auto/VTT).
   - Unir en párrafos legibles.

6. **Generar el `.md`**
   - Cabecera con: título del vídeo, URL, duración, fecha, idioma, método usado.
   - Cuerpo con la transcripción.
   - Guardar como `output/<titulo-o-id>.md`.

7. **(Opcional) Capa LLM opt-in**
   - Flag `--resumen` / `--limpiar` que envía el texto a un LLM **solo si el
     usuario lo pide**. Por defecto desactivado para gastar 0 tokens.

8. **Interfaz**
   - CLI: `python src/transcribe.py <URL> [--lang es] [--resumen]`.

---

## 6. Decisiones que conviene confirmar antes de codificar

1. **Idioma preferido** de los subtítulos (¿`es`, `en`, o el original del vídeo?).
2. **¿Mantener timestamps** en el `.md` o solo texto limpio?
3. **Fallback ASR**: ¿lo incluimos ahora o lo dejamos para una segunda fase?
   (Añade dependencias pesadas como `faster-whisper`/ffmpeg.)
4. **Capa LLM opcional**: ¿interesa el flag de resumen/traducción o lo omitimos
   para mantenerlo 100% sin tokens?
5. **Entorno de ejecución**: ¿este script correrá en local, en este entorno
   remoto, o como bot/servicio?

---

## 7. Recomendación final

- **Para gastar 0 tokens:** usar `youtube-transcript-api` como principal y
  `yt-dlp` como fallback. Generar el `.md` directamente desde los subtítulos.
- **Whisper local** solo como red de seguridad para vídeos sin subtítulos.
- **Reservar el LLM** exclusivamente para resumen/traducción opcional.

Con esto, el caso de uso "dame un `.md` con la transcripción de este link"
se resuelve **sin consumir tokens de modelo**.

---

## Fuentes

- [youtube-transcript-api · PyPI](https://pypi.org/project/youtube-transcript-api/)
- [jdepoix/youtube-transcript-api · GitHub](https://github.com/jdepoix/youtube-transcript-api)
- [yt-dlp · GitHub](https://github.com/yt-dlp/yt-dlp)
- [Extract YouTube Subtitles with yt-dlp: CLI Guide (2026) · SkipTheWatch](https://skipthewatch.com/blog/yt-dlp-youtube-subtitles)
- [YouTube Transcript API 2026: Free Python Library · NoteLM.ai](https://www.notelm.ai/blog/youtube-transcript-api)
- [Top YouTube Transcript APIs in 2026 · API.market](https://api.market/blog/magicapi/youtube-transcript/top-youtube-transcript-apis)
