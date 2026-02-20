# ORACLE — Local Market Intelligence Chatbot

A locally-hosted AI assistant with real-time awareness of **Polymarket**, **Kalshi**, and live news. Runs entirely on your machine via [Ollama](https://ollama.com).

![ORACLE UI](https://img.shields.io/badge/UI-Bloomberg%20Terminal%20aesthetic-00d4aa?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

## Features

- **Polymarket + Kalshi** — live odds, probability bars, 24h volume
- **Streaming AI responses** — tokens appear in real time, no waiting
- **Price alerts** — set threshold alerts on any market outcome; get browser notifications when triggered
- **Auto-refresh** — data refreshes in the background every 5 minutes
- **Dark / light mode** — toggle in the top bar
- **Persistent memory** — conversation history saved locally across sessions
- **NewsAPI integration** — top headlines + topic search injected into AI context
- **Fully local** — no cloud AI, no data leaves your machine

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- A free [NewsAPI](https://newsapi.org/register) key

## Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/oracle.git
cd oracle

# 2. Install deps
pip install -r requirements.txt

# 3. Pull a model
ollama pull llama3.1:8b

# 4. Configure
cp .env.example .env
# Edit .env and add your NEWS_API_KEY

# 5. Run
python app.py
```

Then open **http://localhost:5000**

## Configuration (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `NEWS_API_KEY` | ✅ | — | From [newsapi.org](https://newsapi.org/register) (free) |
| `KALSHI_API_KEY` | ❌ | — | Kalshi API key (public markets work without one) |
| `OLLAMA_MODEL` | ❌ | `llama3.1:8b` | Any model you've pulled via Ollama |
| `AUTO_REFRESH_SEC` | ❌ | `300` | Background data refresh interval in seconds |

## Model Recommendations

| RAM | Model | Notes |
|---|---|---|
| 8GB | `llama3.2:3b` or `phi3:mini` | Good, fast |
| 16GB | `llama3.1:8b` | Recommended |
| 32GB+ | `llama3.1:70b` | Excellent |

## Alerts

Set price alerts in the **ALERTS** tab:
- Enter a market slug/keyword (e.g. `trump`, `fed`)
- Enter the outcome label (e.g. `Yes`)
- Set a % threshold and direction (`above` / `below`)
- Enable browser notifications when prompted

Alerts are checked on every data refresh.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/init` | Initialize — returns markets, news, history |
| POST | `/api/refresh` | Force data refresh |
| POST | `/api/chat` | Chat (supports `"stream": true`) |
| GET | `/api/markets?source=poly\|kalshi&q=query` | Search markets |
| GET | `/api/news?q=query` | Search news |
| GET | `/api/alerts` | List alerts |
| POST | `/api/alerts` | Create alert |
| DELETE | `/api/alerts/:id` | Delete alert |
| POST | `/api/clear` | Clear chat history |

## License

MIT
