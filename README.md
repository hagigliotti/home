# Home

Gastos y consumos de la casa por ubicación, con un sitio (`index.html`) que muestra gastos, consumos, comparación con la media y cómo gastar menos.

## Estructura

```
Fiumana/Servizi/Hera/*.pdf   facturas mensuales de agua, gas y luz
Fiumana/Servizi/Alea/*.pdf   facturas anuales de residuos (TARI)
Fiumana/Servizi/Sorit/*.pdf  recibos de impuestos (cualquier carpeta nueva = otro impuesto o pago)
data/fiumana.json            datos extraídos de los PDF (lo genera el script)
data/ubicaciones.json        lista de casas que muestra el sitio
data/referencias.json        medias de referencia y umbrales del semáforo
scripts/extraer.py           lee los PDF y regenera el JSON
index.html                   el sitio
```

## Agregar facturas o impuestos

1. Subí el PDF a la carpeta del servicio desde GitHub (Add file → Upload files). Para un impuesto o pago nuevo, creá una carpeta con su nombre dentro de `Servizi`.
2. Al hacer el commit, GitHub Actions lee los PDF (`scripts/extraer.py`) y publica el sitio en ~1 minuto.
3. En el sitio, tocá **Actualizar**.

Para otra casa (p. ej. Forlì), creá `Forli/Servizi/Hera/` con los PDF: aparece sola como pestaña nueva. Podés editar el nombre y la dirección en `data/ubicaciones.json`.

Para probar en tu compu: `python3 scripts/extraer.py` (necesita `pdftotext`, paquete `poppler-utils`).

## Ver el sitio

- **En línea:** https://hagigliotti.github.io/home/ (lo publica `.github/workflows/pages.yml`; los PDF no se publican). Ojo: la página es pública aunque el repo sea privado.
- **En tu compu:** `python3 -m http.server` en la carpeta del repo y abrí `http://localhost:8000`.
