from flask import Flask, jsonify, render_template, request
import requests

import data_sources as ds
from model import forecast

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/places")
def places():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        return jsonify(ds.search_places(q))
    except requests.RequestException:
        return jsonify({"error": "Falha ao buscar cidades."}), 502


@app.get("/api/forecast")
def api_forecast():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "Parâmetros lat e lon são obrigatórios."}), 400
    try:
        recent = ds.fetch_recent(lat, lon)
        history = ds.fetch_history(lat, lon)
        return jsonify(forecast(recent, history))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except requests.RequestException:
        return jsonify({"error": "Falha ao obter dados meteorológicos."}), 502


if __name__ == "__main__":
    app.run(debug=True)
