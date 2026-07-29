"""
Creativo (Creative) Agent Tasks.
"""
import logging
from datetime import datetime
from uuid import uuid4

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="services.agents.creativo.tasks.run_creative_ideas")
def run_creative_ideas(self, task_data: dict = None) -> dict:
    """
    Generate creative design ideas based on market analysis and Pinterest trends.
    """

    correlation_id = uuid4()
    logger.info(f"Starting creative ideas generation [{correlation_id}]")

    datetime.utcnow()

    try:
        # Get inputs
        market_analysis = task_data.get("market_analysis", {}) if task_data else {}
        pinterest_trends = task_data.get("pinterest_trends", {}) if task_data else {}

        # Generate creative ideas
        logger.info("Generating creative ideas with Groq...")
        ideas = generate_creative_ideas(market_analysis, pinterest_trends)

        # Generate expansions
        logger.info("Generating expansion recommendations...")
        expansions = generate_expansions()

        # Build report
        report = {
            "date": datetime.utcnow().isoformat(),
            "ideas": ideas,
            "expansions": expansions,
        }

        result = {
            "task_id": str(uuid4()),
            "agent_type": "creativo",
            "status": "completed",
            "result": report,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

        logger.info("Creative ideas completed")
        return result

    except Exception as e:
        logger.exception(f"Creative ideas failed: {e}")
        return {
            "task_id": str(uuid4()),
            "agent_type": "creativo",
            "status": "failed",
            "error": str(e),
        }


def generate_creative_ideas(market_analysis: dict, pinterest_trends: dict) -> list:
    """Generate 5 creative design ideas."""
    import os

    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    market_analysis.get("analysis", "")[:2000] if market_analysis else ""
    str(pinterest_trends)[:2000] if pinterest_trends else ""

    prompt = f"""Eres el director creativo de una tienda de ropa con diseños gráficos en Etsy.
Vende poleras y hoodies con diseños de parques nacionales de USA,
y trucker hats con banderas y escudos de los 50 estados de USA.
Producción via Printful, envío global.

PERFIL DE LA TIENDA:
- Estilo: Ilustración digital, estilo vintage/retro, paleta natural/terra
- Temas: Parques nacionales USA, banderas/escudos de estados USA
- Público: Amantes de naturaleza, viajeros, orgullo estatal, regalos
- Productos: Poleras, hoodies, trucker hats

DATOS DE MERCADO:
{market_analysis}

TENDENCIAS PINTEREST:
{pinterest_trends}

Genera exactamente 5 propuestas de diseños nuevos. Para cada uno:

---
DISEÑO [N]: [NOMBRE EN MAYÚSCULAS]

CONCEPTO:
[Qué muestra exactamente. Descripción visual detallada.]

ESTILO Y TÉCNICA:
[Cómo se ve. Paleta, líneas, composición, referencias estéticas.]

PRODUCTO PRINCIPAL:
[Polera / Hoodie / Sombrero — cuál encaja mejor y por qué]

PRODUCTOS ADICIONALES:
[En qué otros productos funcionaría bien este diseño]

POR QUÉ FUNCIONARÁ:
[Conexión entre la tendencia actual, el estilo de la marca y el cliente ideal. Sé específico.]

PROMPT PARA AI DE IMÁGENES:
[Instrucción en INGLÉS, detallada y lista para copiar en Midjourney, Stable Diffusion o DALL-E. Incluye estilo, técnica, composición, colores, iluminación y calidad.]
---

Respeta siempre el estilo descrito en el perfil.
No sugieras nada que contradiga los temas prohibidos.
Responde en español (excepto el prompt de AI que va en inglés)."""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=2500,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq creative failed: {e}")
        return f"Error generando ideas: {e}"


def generate_expansions() -> str:
    """Generate expansion recommendations."""
    import os

    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    prompt = """Eres un estratega de producto para tiendas Etsy de ropa con diseños gráficos.
Vende poleras y hoodies con diseños de parques nacionales de USA,
y trucker hats con banderas y escudos de los 50 estados de USA.
Producción via Printful, envío global.

Basándote solo en la información del perfil, recomienda:

## EXPANSIONES DE PRODUCTO
¿Cuáles de los diseños existentes deberían aplicarse a más tipos de producto?
(ej: un diseño de polera → también en hoodie y sombrero)
Sé específico: menciona el diseño por nombre y el producto sugerido.

## VARIACIONES ESTRATÉGICAS
¿Qué variaciones de los diseños más exitosos podrían generar nuevas ventas?
(variaciones de color, inversión de paleta, versión minimalista, etc.)

## COLECCIÓN TEMÁTICA
¿Hay diseños existentes que podrían agruparse bajo un nombre de colección coherente?
¿Cómo llamarías esa colección?

## PRÓXIMO PRODUCTO A LANZAR
De todas las expansiones sugeridas, ¿cuál tiene más potencial comercial inmediato y por qué?

Sé concreto. Menciona diseños por nombre cuando sea posible."""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq expansions failed: {e}")
        return f"Error generando expansiones: {e}"


if __name__ == "__main__":
    result = run_creative_ideas({})
