import json
import time
import requests

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
SERVICE_URL = "https://TU-SERVICIO.onrender.com/procesar"  # <-- cámbialo
ITERACIONES = 3
INTERVALO_SEG = 60


def extraer():
    params = {"vs_currency": "usd", "order": "market_cap_desc",
              "per_page": 10, "page": 1, "price_change_percentage": "24h"}
    r = requests.get(COINGECKO_URL, params=params, timeout=30)
    r.raise_for_status()
    return [{
        "name": c.get("name"),
        "symbol": c.get("symbol"),
        "price": c.get("current_price"),
        "change_24h": c.get("price_change_percentage_24h"),
        "volume": c.get("total_volume"),
        "market_cap": c.get("market_cap"),
    } for c in r.json()]


def main():
    for i in range(1, ITERACIONES + 1):
        print(f"\n--- Iteración {i}/{ITERACIONES} ---")
        datos = extraer()
        print(f"Extraídos {len(datos)} registros de CoinGecko")

        resp = requests.post(SERVICE_URL,
                             json={"source": "coingecko", "data": datos},
                             timeout=90)  # 90s por el arranque en frío de Render
        resp.raise_for_status()
        resultado = resp.json()

        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        with open("resultados.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

        if i < ITERACIONES:
            time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()