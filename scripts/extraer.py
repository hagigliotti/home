#!/usr/bin/env python3
"""Lee las facturas en PDF de una ubicación y genera data/<ubicacion>.json.

Uso:  python3 scripts/extraer.py            (todas las ubicaciones)
      python3 scripts/extraer.py Fiumana    (solo una)
Requiere pdftotext (paquete poppler-utils).

Estructura esperada:
  <Ubicacion>/Servizi/Hera/*.pdf   facturas mensuales Hera (agua, gas, luz)
  <Ubicacion>/Servizi/Alea/*.pdf   facturas anuales Alea Ambiente (residuos / TARI)
  <Ubicacion>/Servizi/<Otro>/*.pdf recibos de impuestos u otros pagos (p. ej. Sorit);
                                   el nombre de la carpeta es el nombre del pago
"""
import datetime, glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def texto(pdf):
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    return re.sub(r"[ \t]+", " ", out)


def num(s):
    return float(s.replace(".", "").replace(",", "."))


def iso(d):
    dd, mm, yy = d.split(".")
    return f"{yy}-{mm}-{dd}"


def busca(pat, t, conv=num, default=None):
    m = re.search(pat, t)
    return conv(m.group(1)) if m else default


def hera(pdf):
    t = texto(pdf)
    if not re.search(r"Consumo effettivo dal \S+ al \S+ \(\d+ giorni\) [\d.,]+ Smc", t):
        return None  # p. ej. invoices.pdf (documento de otro tipo, sin consumos)
    head = t[:30000]
    r = {"archivo": os.path.basename(pdf)}
    r["emision"] = busca(r"Data emissione (\d\d\.\d\d\.\d{4})", t, iso)
    for k, lab in [("agua", "Acqua"), ("gas", "Gas"), ("luz", "Energia Elettrica"), ("otros", "Altri servizi")]:
        r[k] = busca(r"\n ?" + lab + r" (-?[\d.]+,\d\d) €", head, default=0.0)
    r["total"] = busca(r"Totale da pagare:? (-?[\d.]+,\d\d) €", head)

    g = re.search(r"Consumo effettivo dal (\S+) al (\S+) \((\d+) giorni\) ([\d.,]+) Smc", t)
    r["desde"], r["hasta"] = (iso(g.group(1)), iso(g.group(2))) if g else (None, None)
    r["smc"] = round(num(g.group(4)), 2) if g else None

    e = re.search(r"Consumo effettivo dal \S+ al \S+ \(\d+ giorni\) ([\d.,]+) ([\d.,]+) ([\d.,]+) kWh", t)
    if e:
        r["kwh"] = num(e.group(3))
    else:
        q = [num(x) for x in re.findall(r"Importo dal \S+ al \S+ €/kWh 0,0\d{6} ([\d.,]+) kWh", t)]
        q = [x for x in q if x == int(x)]
        r["kwh"] = max(q) if q else None

    r["bono_luz"] = busca(r"Bonus sociale energia (-[\d,]+) €", t, default=0.0)
    m = re.search(r"Contributo Straordinario D\.L\. ?19/25 (-[\d,]+) €", t)
    r["bono_extra"] = num(m.group(1)) if m else 0.0
    r["bono_gas"] = busca(r"Detrazione Bonus sociale gas (-[\d,]+) €", t, default=0.0)
    rates = dict(re.findall(r"CANONE TV - Rata (\w+ \d{4})(?: 1)? ([\d,]+)", t))
    r["canone_tv"] = round(sum(num(v) for v in rates.values()), 2)
    r["kit_led"] = busca(r"Hera Led 1 Kit rata \d+ ([\d,]+) €", t, default=0.0)
    r["kit_led_cuota"] = busca(r"Hera Led 1 Kit rata (\d+)", t, int)

    # separar lo que no es energía (canon TV, kit LED, altas) del importe de la luz
    tv_en_luz = r["canone_tv"] if r["otros"] == 0 else 0.0
    r["luz_energia"] = round(r["luz"] - r["kit_led"] - tv_en_luz, 2)
    r["extras"] = round(r["otros"] + r["kit_led"] + tv_en_luz, 2)

    # precios de la oferta
    r["luz_precio"] = busca(r"Prezzo Netto ore piene \(F1\) \+(\d,\d+)", t) or busca(r"ore piene \(F1\) €/kWh (\d,\d+)", t)
    r["gas_precio"] = busca(r"\nPrezzo Netto \+(\d,\d+)", t) or busca(r"Prezzo Netto \+(\d,\d+)", t)
    if r["gas_precio"] is None:
        r["gas_precio"] = busca(r"Importo dal \S+ al \S+ €/Smc (0,\d+) [\d.,]+ Smc", t)
    fijas = re.findall(r"Quota fissa \(([\d,]+) €\)", t)
    if len(fijas) >= 2:
        r["gas_fijo_mes"], r["luz_fijo_mes"] = num(fijas[0]), num(fijas[1])
    else:
        r["gas_fijo_mes"] = busca(r"€/puntoriconsegn (\d+,\d+) 1,0+ mese", t, default=4.0)
        r["luz_fijo_mes"] = busca(r"€/cliente/mese (\d,\d+) [\d,]+ mese", t, default=4.0)

    # lecturas reales del medidor de agua
    r["agua_lecturas"] = [
        {"desde": iso(a), "hasta": iso(b), "dias": int(d), "m3": num(v)}
        for a, b, d, v in re.findall(r"Consumo rilevato dal (\S+) al (\S+) \((\d+) giorni\) ([\d.,]+) mc", t)
    ]
    return r


def alea(pdf):
    t = texto(pdf)
    anio = busca(r"fattura per l'anno (\d{4})", t, int)
    return {
        "archivo": os.path.basename(pdf),
        "anio": anio,
        "total": busca(r"TOTALE FATTURA ([\d.,]+) €", t),
        "imponible_anio": busca(r"Imponibile Anno \d{4} \(A\) ([\d.,]+) €", t),
        "imponible_ajuste_anterior": busca(r"Imponibile Conguaglio \d{4} \(B\) ([\d.,]+) €", t, default=0.0),
        "componentes": busca(r"nucleo familiare di (\d+) componenti", t, int),
        "pagos": [num(x) for x in re.findall(r"\n Importo\n+ ?([\d.,]+) €", t)],
    }


MESES_IT = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
ESPECIALES = {"hera", "alea"}


def recibo(pdf, servicio):
    """Recibo de pago genérico (pagoPA u otro): fecha, importe, comisión y concepto."""
    t = texto(pdf)
    r = {"servicio": servicio, "archivo": os.path.basename(pdf), "fecha": None,
         "importe": None, "comision": 0.0, "concepto": None, "vencimiento": None}
    m = re.search(r"(\d{1,2}) (" + "|".join(MESES_IT) + r") (\d{4})", t)
    if m:
        r["fecha"] = f"{m.group(3)}-{MESES_IT[m.group(2)]:02d}-{int(m.group(1)):02d}"
    r["importe"] = busca(r"Importo\n+ ?([\d.,]+) €", t) or busca(r"Importo[^\n]*?([\d.,]+) €", t)
    r["comision"] = busca(r"Commissione[^\n]*?([\d.,]+) €", t, default=0.0)
    m = re.search(r"\n ?((?:AVVISO|POSIZIONE|PAGAMENTO|TRIBUTO|IMU|TARI)[^\n]{5,120})", t)
    if m:
        r["concepto"] = m.group(1).strip()
    r["vencimiento"] = busca(r"SCADENZA (\d\d/\d\d/\d{4})", t, lambda x: "-".join(reversed(x.split("/"))))
    if not r["fecha"] and r["vencimiento"]:
        r["fecha"] = r["vencimiento"]
    return r


def slug(nombre):
    import unicodedata
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def procesar(ubic):
    base = os.path.join(ROOT, ubic, "Servizi")
    facturas = [f for f in (hera(p) for p in sorted(glob.glob(os.path.join(base, "Hera", "*.pdf")))) if f]
    facturas.sort(key=lambda f: f["desde"] or "")
    lecturas = {}
    for f in facturas:
        for l in f.pop("agua_lecturas"):
            lecturas[l["desde"]] = l
    residuos = sorted((alea(p) for p in glob.glob(os.path.join(base, "Alea", "*.pdf"))), key=lambda a: a["anio"] or 0)
    # cualquier otra carpeta dentro de Servizi = impuestos u otros pagos (recibos)
    pagos = []
    for carpeta in sorted(glob.glob(os.path.join(base, "*"))):
        nombre = os.path.basename(carpeta)
        if not os.path.isdir(carpeta) or nombre.lower() in ESPECIALES:
            continue
        pagos += [recibo(p, nombre) for p in sorted(glob.glob(os.path.join(carpeta, "*.pdf")))]
    pagos.sort(key=lambda r: r["fecha"] or "")
    # factura del kit LED de Hera (se paga en cuotas dentro de la luz)
    kit_led_total = None
    for p in glob.glob(os.path.join(base, "Hera", "*.pdf")):
        t = texto(p)
        if "LED" in t and "LA FATTURA NON DEVE ESSERE PAGATA" in t:
            kit_led_total = busca(r"Totale Fattura ([\d.,]+) €", t)
    out = {
        "ubicacion": ubic,
        "generado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "personas": next((r["componentes"] for r in residuos if r.get("componentes")), 2),
        "facturas_hera": facturas,
        "agua_lecturas": sorted(lecturas.values(), key=lambda l: l["desde"]),
        "residuos": residuos,
        "pagos": pagos,
        "kit_led_total": kit_led_total,
    }
    dest = os.path.join(ROOT, "data", slug(ubic) + ".json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{dest}: {len(facturas)} facturas Hera, {len(residuos)} Alea, {len(pagos)} otros pagos, {len(lecturas)} lecturas de agua")
    return slug(ubic)


def main(nombres):
    """Sin argumentos procesa todas las carpetas del repo que tengan Servizi/ y actualiza data/ubicaciones.json."""
    todas = sorted(d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d, "Servizi")))
    nombres = nombres or todas
    for n in nombres:
        procesar(n)
    # ubicaciones: conserva lo escrito a mano (detalle) y agrega las carpetas nuevas
    ruta = os.path.join(ROOT, "data", "ubicaciones.json")
    try:
        actuales = json.load(open(ruta, encoding="utf-8"))
    except FileNotFoundError:
        actuales = []
    ids = {u["id"] for u in actuales}
    for n in todas:
        if slug(n) not in ids:
            actuales.append({"id": slug(n), "nombre": n, "detalle": n, "archivo": f"data/{slug(n)}.json"})
    actuales = [u for u in actuales if os.path.exists(os.path.join(ROOT, u["archivo"]))]
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(actuales, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
