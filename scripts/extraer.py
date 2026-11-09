#!/usr/bin/env python3
"""Lee las facturas en PDF de una ubicación y genera data/<ubicacion>.json.

Uso:  python3 scripts/extraer.py Fiumana
Requiere pdftotext (paquete poppler-utils).

Estructura esperada:
  <Ubicacion>/Servizi/Hera/*.pdf   facturas mensuales Hera (agua, gas, luz)
  <Ubicacion>/Servizi/Alea/*.pdf   facturas anuales Alea Ambiente (residuos / TARI)
"""
import glob, json, os, re, subprocess, sys

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


def main(ubic):
    base = os.path.join(ROOT, ubic, "Servizi")
    facturas = [f for f in (hera(p) for p in sorted(glob.glob(os.path.join(base, "Hera", "*.pdf")))) if f]
    facturas.sort(key=lambda f: f["desde"] or "")
    lecturas = {}
    for f in facturas:
        for l in f.pop("agua_lecturas"):
            lecturas[l["desde"]] = l
    residuos = sorted((alea(p) for p in glob.glob(os.path.join(base, "Alea", "*.pdf"))), key=lambda a: a["anio"] or 0)
    out = {
        "ubicacion": ubic,
        "personas": next((r["componentes"] for r in residuos if r.get("componentes")), 2),
        "facturas_hera": facturas,
        "agua_lecturas": sorted(lecturas.values(), key=lambda l: l["desde"]),
        "residuos": residuos,
    }
    dest = os.path.join(ROOT, "data", ubic.lower() + ".json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{dest}: {len(facturas)} facturas Hera, {len(residuos)} Alea, {len(lecturas)} lecturas de agua")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Fiumana")
