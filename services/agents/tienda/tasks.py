"""
Tienda Agent Tasks.
"""
import logging
from celery import shared_task
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="services.agents.tienda.tasks.run_tienda")
def run_tienda(self, task_data: dict = None) -> dict:
    """
    Run store management analysis.
    """
    from uuid import uuid4
    from datetime import datetime
    
    correlation_id = uuid4()
    logger.info(f"Starting Tienda agent [{correlation_id}]")
    
    started_at = datetime.utcnow()
    
    try:
        logger.info("Reading Printful products...")
        printful = fetch_printful_products()
        
        logger.info("Reading Etsy listings...")
        etsy_listings = fetch_etsy_listings()
        
        logger.info("Generating store plan with Groq...")
        plan = generate_store_plan(printful, etsy_listings)
        
        report = {
            "date": datetime.utcnow().isoformat(),
            "printful_products": printful,
            "etsy_listings": etsy_listings,
            "plan": plan,
        }
        
        return {
            "task_id": str(uuid4()),
            "agent_type": "tienda",
            "status": "completed",
            "result": report,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"Tienda agent failed: {e}")
        return {
            "task_id": str(uuid4()),
            "agent_type": "tienda",
            "status": "failed",
            "error": str(e),
        }


def fetch_printful_products() -> str:
    """Fetch products from Printful."""
    import requests
    import os
    
    token = os.getenv("PRINTFUL_TOKEN")
    store_id = os.getenv("PRINTFUL_STORE_ID")
    
    if not token or not store_id:
        return "Printful credentials not configured"
    
    try:
        headers = {"Authorization": f"Bearer {token}", "X-PF-Store-Id": store_id}
        response = requests.get(
            "https://api.printful.com/sync/products",
            headers=headers,
            timeout=15,
        )
        
        if response.status_code == 200:
            products = response.json().get("result", [])
            if not products:
                return "No products in Printful yet."
            return "\n".join([f"  - {p['name']}" for p in products[:20]])
        
        return f"Printful API error: {response.status_code}"
    except Exception as e:
        return f"Printful error: {e}"


def fetch_etsy_listings() -> str:
    """Fetch listings from Etsy via OAuth."""
    try:
        from etsy_client import obtener_headers_autenticados, obtener_mis_listings
        
        headers = obtener_headers_autenticados()
        activos = obtener_mis_listings(headers, estado="active")
        borradores = obtener_mis_listings(headers, estado="draft")
        
        return f"LISTINGS ACTIVOS:\n{activos}\n\nLISTINGS EN BORRADOR:\n{borradores}"
    except Exception as e:
        logger.error(f"Error Etsy: {e}")
        return f"Error leyendo Etsy: {e}"


def generate_store_plan(printful: str, etsy_listings: str) -> str:
    """Generate store plan with Groq."""
    from groq import Groq
    import os
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt = f"""Eres el gestor de FunStuffBarn, tienda Etsy en fase de lanzamiento.
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

PRODUCTOS EN PRINTFUL:
{printful}

LISTINGS EN ETSY:
{etsy_listings}

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
        logger.error(f"Groq store plan failed: {e}")
        return f"Error generando plan: {e}"


if __name__ == "__main__":
    result = run_tienda({})
    print(result)