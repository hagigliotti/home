# Home

Gastos y consumos de la casa por ubicación, con un sitio (`index.html`) que muestra gastos, consumos, comparación con la media y cómo gastar menos.

## Estructura

```
Fiumana/Servizi/Hera/*.pdf   facturas mensuales de agua, gas y luz
Fiumana/Servizi/Alea/*.pdf   facturas anuales de residuos (TARI)
data/fiumana.json            datos extraídos de los PDF (lo genera el script)
data/ubicaciones.json        lista de casas que muestra el sitio
data/referencias.json        medias de referencia y umbrales del semáforo
scripts/extraer.py           lee los PDF y regenera el JSON
index.html                   el sitio
```

## Agregar facturas

1. Subí el PDF a la carpeta del servicio.
2. Ejecutá `python3 scripts/extraer.py Fiumana` (necesita `pdftotext`, paquete `poppler-utils`).
3. Hacé commit de los PDF y de `data/fiumana.json`.

## Nueva ubicación (p. ej. Forlì)

1. Creá `Forli/Servizi/Hera/` (y `Alea/` si corresponde) con los PDF.
2. Ejecutá `python3 scripts/extraer.py Forli` → genera `data/forli.json`.
3. Agregá `{"id": "forli", "nombre": "Forlì", "detalle": "...", "archivo": "data/forli.json"}` en `data/ubicaciones.json`.

## Ver el sitio

- **GitHub Pages:** Settings → Pages → Deploy from branch → `main` / `/ (root)`. Ojo: el sitio publicado es público aunque el repo sea privado.
- **En tu compu:** `python3 -m http.server` en la carpeta del repo y abrí `http://localhost:8000`.
