# Previsão do Tempo por Tendências (Flask)

## Rodar
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    python app.py
Abra http://127.0.0.1:5000

## Estrutura
- `app.py` – rotas Flask (`/`, `/api/places`, `/api/forecast`)
- `data_sources.py` – dados reais gratuitos (Open-Meteo), com cache de 30 min
- `model.py` – modelo estatístico (climatologia + anomalia recente + tendência)
- `templates/index.html` – interface com gráfico
