from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
import sqlite3
import json
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI(title="Plant Guardians API")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização do banco de dados SQLite


def init_db():
    conn = sqlite3.connect('plant_guardians.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            date TEXT,
            image_url TEXT,
            animal_detected TEXT,
            action_taken TEXT,
            confidence REAL
        )
    ''')
    conn.commit()
    conn.close()


# Executar inicialização do banco de dados
init_db()

# Função para conectar ao banco de dados


def get_db():
    conn = sqlite3.connect('plant_guardians.db')
    conn.row_factory = sqlite3.Row
    return conn

# Modelos Pydantic


class Event(BaseModel):
    timestamp: datetime
    image_url: str
    animal_detected: str
    action_taken: str
    confidence: float


class Stats(BaseModel):
    date: str
    total_detections: int
    animals_detected: dict

# Autenticação simplificada - sempre retorna verdadeiro para desenvolvimento local


async def verify_api_key(x_api_key: str = Header(None)):
    # Em desenvolvimento, aceita qualquer chave ou nenhuma
    return x_api_key or "development-key"


@app.get("/")
async def root():
    return {"message": "Plant Guardians API (Local Development)"}


@app.get("/events/latest")
async def get_latest_events(
    limit: int = 20,
    api_key: str = Depends(verify_api_key)
) -> List[Event]:
    """Retorna os eventos mais recentes do banco de dados local."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )

    rows = cursor.fetchall()
    conn.close()

    events = []
    for row in rows:
        # Converter dicionário de linha para objeto Event
        event_dict = dict(row)
        # Converter timestamp de string para datetime
        event_dict["timestamp"] = datetime.fromisoformat(
            event_dict["timestamp"])
        events.append(Event(**event_dict))

    return events


@app.get("/stats/daily")
async def get_daily_stats(
    days: int = 7,
    api_key: str = Depends(verify_api_key)
) -> List[Stats]:
    """Retorna estatísticas diárias dos últimos N dias."""
    stats = []
    today = datetime.now().date()

    conn = get_db()
    cursor = conn.cursor()

    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.isoformat()

        # Consulta eventos do dia
        cursor.execute(
            "SELECT animal_detected FROM events WHERE date = ?",
            (date_str,)
        )

        rows = cursor.fetchall()

        daily_stats = {
            "date": date_str,
            "total_detections": len(rows),
            "animals_detected": {}
        }

        for row in rows:
            animal = row["animal_detected"]
            if animal:
                daily_stats["animals_detected"][animal] = daily_stats["animals_detected"].get(
                    animal, 0) + 1

        stats.append(Stats(**daily_stats))

    conn.close()
    return stats


@app.post("/events")
async def create_event(
    event: Event,
    api_key: str = Depends(verify_api_key)
):
    """Registra um novo evento de detecção."""
    # Converter o evento para dicionário
    event_dict = event.dict()
    # Adicionar a data como string
    event_dict["date"] = event.timestamp.date().isoformat()
    # Converter timestamp para string ISO
    event_dict["timestamp"] = event.timestamp.isoformat()

    # Salvar no SQLite
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO events (timestamp, date, image_url, animal_detected, action_taken, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event_dict["timestamp"],
            event_dict["date"],
            event_dict["image_url"],
            event_dict["animal_detected"],
            event_dict["action_taken"],
            event_dict["confidence"]
        )
    )

    conn.commit()
    conn.close()

    # Simulação de publicação no Pub/Sub (apenas log)
    print(f"[SIMULAÇÃO PUB/SUB] Evento publicado: {json.dumps(event_dict)}")

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
