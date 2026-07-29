"""
Estrategia Agent Tasks.
"""
import logging
from celery import shared_task
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="services.agents.estrategia.tasks.run_estrategia")
def run_estrategia(self, task_data: dict = None) -> dict:
    """
    Generate strategy report based on all agent outputs.
    """
    from uuid import uuid4
    from datetime import datetime
    
    correlation_id = uuid4()
    logger.info(f"Starting Estrategia agent [{correlation_id}]")
    
    started_at = datetime.utcnow()
    
    try:
        logger.info("Reading agent reports...")
        mercado = read_latest_report("mercado")
        creativo = read_latest_report("creativo")
        pinterest = read_latest_report("pinterest")
        tienda = read_latest_report("tienda")
        
        logger.info("Generating strategy with Groq...")
        estrategia = generate_strategy(mercado, creativo, pinterest, tienda)
        
        report = {
            "date": datetime.utcnow().isoformat(),
            "mercado_summary": mercado.get("analysis", "")[:500] if mercado else "",
            "creativo_summary": creativo.get("analysis", "")[:500] if creativo else "",
            "pinterest_summary": pinterest.get("analysis", "")[:500] if pinterest else "",
            "tienda_summary": tienda.get("plan", "")[:500] if tienda else "",
            "estrategia": estrategia,
        }
        
        return {
            "task_id": str(uuid4()),
            "agent_type": "estrategia",
            "status": "completed",
            "result": report,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"Estrategia agent failed: {e}")
        return {
            "task_id": str(uuid4()),
            "agent_type": "estrategia",
            "status": "failed",
            "error": str(e),
        }


def read_latest_report(prefix: str) -> dict:
    """Read the latest report file for a given prefix."""
    import json
    from pathlib import Path
    
    reportes_dir = Path("/Users/javiermaldonadocorreaair/agente-etsy/reportes")
    if not reportes_dir.exists():
        return {}
    
    files = sorted(reportes_dir.glob(f"{prefix}_*.txt"), reverse=True)
    if not files:
        return {}
    
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            content = f.read()
        return {"analysis": content, "file": files[0].name}
    except Exception as e:
        logger.warning(f"Could not read {prefix} report: {e}")
        return {}


def generate_strategy(mercado: dict, creativo: dict, pinterest: dict, tienda: dict) -> str:
    """Generate strategy report with Groq."""
    from groq import Groq
    import os
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    mercado_text = mercado.get("analysis", "")[:2000] if mercado else "No disponible"
    creativo_text = creativo.get("analysis", "")[:2000] if creativo else "No disponible"
    pinterest_text = pinterest.get("analysis", "")[:2000] if pinterest else "No disponible"
    tienda_text = tienda.get("plan", "")[:2000] if tienda else "No disponible"
    
    prompt = f"""Eres el estratega senior de FunStuffBarn, tienda Etsy en fase de lanzamiento.
Vende poleras y hoodies con diseños de parques nacionales de USA,
y trucker hats con banderas y escudos de los 50 estados de USA.
Producción via Printful, envío global.

REGLAS DE ETSY QUE DEBES SEGUIR SIEMPRE:
- Tags son frases simples SIN hashtags ni símbolo #
- Correcto: "national park shirt", "yellowstone tee", "hiking gift"
- Incorrecto: #NationalPark, #Yellowstone
- Cada tag máximo 20 caracteres
- Títulos máximo 140 caracteres
- Precios de mercado: poleras $28-45, hoodies $55-75, trucker hats $25-40

ANÁLISIS DE MERCADO:
{mercado_text}

IDEAS CREATIVAS:
{creativo_text}

TENDENCIAS PINTEREST:
{pinterest_text}

PLAN DE TIENDA:
{tienda_text}

Entrega en español:

## DIAGNOSTICO DEL MERCADO
Como está el mercado para parques nacionales y estados de USA en Etsy?

## ESTADO DE MI TIENDA
Basado en mis listings actuales (activos y borradores), que falta?

## ESTRATEGIA DE LANZAMIENTO
Los primeros 5 productos a publicar (o los siguientes 5, si ya hay productos). Para cada uno:
- Nombre exacto del producto
- Precio (dentro del rango correcto)
- Título para Etsy (máximo 140 caracteres)
- 5 tags SIN hashtag

## TOP 5 ACCIONES ESTA SEMANA
En orden de impacto con tiempo estimado.

## ACCION INMEDIATA
Una sola cosa concreta para hacer hoy en menos de 15 minutos."""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq strategy failed: {e}")
        return f"Error generando estrategia: {e}"


if __name__ == "__main__":
    result = run_estrategia({})
    print(result)