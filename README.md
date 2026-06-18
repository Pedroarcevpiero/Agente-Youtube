# Agente-Youtube

Dado el link de un vídeo de YouTube, genera un archivo `.md` con su transcripción.

No usa ningún LLM para transcribir: lee los subtítulos que YouTube ya genera
(manuales o automáticos), por lo que el coste en tokens es **cero**. Ver
[`PLAN-transcripcion.md`](./PLAN-transcripcion.md) para el detalle de la
investigación y las decisiones de diseño.

## Instalación

```bash
pip install -r requirements.txt
```

También necesitas `ffmpeg` instalado en el sistema (lo usa `yt-dlp` como
respaldo cuando no hay subtítulos directos).

## Uso

```bash
python src/transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Esto genera `output/<titulo-del-video>.md` con la transcripción.

### Elegir idioma

Por defecto se intenta español y luego inglés. Puedes especificar otros:

```bash
python src/transcribe.py "https://youtu.be/VIDEO_ID" --lang en --lang fr
```

## Cómo funciona

1. Extrae el `video_id` de la URL.
2. Intenta obtener los subtítulos con `youtube-transcript-api`.
3. Si el vídeo no tiene subtítulos accesibles por esa vía, usa `yt-dlp` como
   respaldo para descargar los subtítulos automáticos.
4. Limpia el texto (quita timestamps, etiquetas y líneas duplicadas).
5. Guarda el resultado como `.md` en `output/`.
