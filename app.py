import re
import json
import logging
import statistics
import unicodedata
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("pipeline")


# ---------- LIMPIEZA ----------
def limpiar_texto(texto):
    """Normaliza acentos, elimina caracteres especiales y espacios extra."""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9\s\-]", "", texto)
    return re.sub(r"\s+", " ", texto).strip().lower()


def a_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def limpiar_lote(registros):
    """Normaliza texto, convierte tipos e imputa faltantes con la mediana del lote."""
    campos = ["price", "change_24h", "volume", "market_cap"]
    limpios = []
    for r in registros:
        limpios.append({
            "name": limpiar_texto(r.get("name", "desconocido")),
            "symbol": limpiar_texto(r.get("symbol", "n/a")).upper(),
            "price": a_float(r.get("price")),
            "change_24h": a_float(r.get("change_24h")),
            "volume": a_float(r.get("volume")),
            "market_cap": a_float(r.get("market_cap")),
            "imputados": [],
        })

    medianas = {}
    for c in campos:
        valores = [x[c] for x in limpios if x[c] is not None]
        medianas[c] = statistics.median(valores) if valores else 0.0

    for x in limpios:
        for c in campos:
            if x[c] is None:
                x[c] = medianas[c]
                x["imputados"].append(c)
    return limpios


# ---------- MINERÍA / CLASIFICACIÓN ----------
def clasificar(x):
    cambio = x["change_24h"]
    ratio = x["volume"] / x["market_cap"] if x["market_cap"] else 0

    # Regla 1: tendencia
    if cambio >= 3:
        tendencia = "alcista"
    elif cambio <= -3:
        tendencia = "bajista"
    else:
        tendencia = "lateral"

    # Regla 2: volatilidad
    if abs(cambio) >= 8:
        volatilidad = "alta"
    elif abs(cambio) >= 3:
        volatilidad = "media"
    else:
        volatilidad = "baja"

    # Scoring de riesgo (0-100): variación absoluta + rotación de volumen
    score = min(100, round(abs(cambio) * 6 + ratio * 200, 2))
    riesgo = "ALTO" if score >= 60 else "MEDIO" if score >= 30 else "BAJO"

    return {"tendencia": tendencia, "volatilidad": volatilidad,
            "score_riesgo": score, "nivel_riesgo": riesgo,
            "ratio_volumen_mcap": round(ratio, 4)}


# ---------- ENDPOINTS ----------
@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/procesar")
def procesar():
    payload = request.get_json(silent=True)
    if not payload or "data" not in payload:
        return jsonify({"error": "Payload invalido, se espera {'data': [...]}"}), 400

    limpios = limpiar_lote(payload["data"])
    resultados = [{**x, "clasificacion": clasificar(x)} for x in limpios]

    conteo = {}
    for r in resultados:
        n = r["clasificacion"]["nivel_riesgo"]
        conteo[n] = conteo.get(n, 0) + 1

    respuesta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fuente": payload.get("source", "desconocida"),
        "registros_recibidos": len(payload["data"]),
        "registros_procesados": len(resultados),
        "resumen_riesgo": conteo,
        "resultados": resultados,
    }
    log.info(json.dumps(respuesta, ensure_ascii=False))  # log consolidado
    return jsonify(respuesta)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)