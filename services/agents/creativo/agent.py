"""
Creative Agent - Generates design ideas based on market analysis and Pinterest trends.
"""
import logging
from datetime import datetime
from typing import Any

from groq import Groq

from services.agents.base import BaseAgent
from services.shared.config import get_settings
from services.shared.resilience import circuit_breaker_registry, retry_with_policy

logger = logging.getLogger(__name__)

settings = get_settings()

groq_breaker = circuit_breaker_registry.get_or_create("groq")


class CreativoAgent(BaseAgent):
    """Creative Agent - Generates design ideas based on market analysis and Pinterest trends."""

    agent_name = "creativo"

    def __init__(self, settings_override=None):
        super().__init__("creativo", get_settings())
        self.groq_client = Groq(api_key=self.settings.GROQ_API_KEY)

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Generate creative design ideas based on market analysis and Pinterest trends.
        
        Args:
            payload: Contains market_analysis and pinterest_trends
            
        Returns:
            Creative ideas report
        """
        market_analysis = payload.get("market_analysis", {}) if payload else {}
        pinterest_trends = payload.get("pinterest_trends", {}) if payload else {}

        logger.info("Generating creative design ideas...")

        # Generate ideas with Groq
        ideas = await self._generate_ideas_with_groq(market_analysis, pinterest_trends)

        # Generate expansions
        expansions = await self._generate_expansions_with_groq()

        report = {
            "date": datetime.utcnow().isoformat(),
            "ideas": ideas,
            "expansions": expansions,
        }

        return report

    async def _generate_ideas_with_groq(self, market: dict, pinterest: dict) -> str:
        """Generate creative ideas with Groq."""

        @retry_with_policy(policy=GROQ_POLICY)
        async def _call_groq():
            groq_client = Groq(api_key=self.settings.GROQ_API_KEY)

            prompt = f"""Eres el director creativo de una tienda de ropa con diseños gráficos en Etsy.
Vende poleras y hoodies con diseños de parques nacionales de USA,
y trucker hats con banderas y escudos de los 50 estados de USA.
Producción via Printful, envío global.

PERFIL COMPLETO DE LA MARCA:
{self.settings}

ANÁLISIS DE MERCADO HOY:
{market.get('analysis', '')[:3000] if market else 'No disponible'}

TENDENCIAS PINTEREST:
{pinterest.get('analysis', '')[:2000] if pinterest else 'No disponible'}

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

        return await self._call_groq(prompt, max_tokens=2500, temperature=0.8)

    async def _generate_expansions_with_groq(self) -> str:
        """Generate expansion recommendations."""

        @retry_with_policy(policy=GROQ_POLICY)
        async def _call_groq():
            groq_client = Groq(api_key=self.settings.GROQ_API_KEY)

            prompt = f"""Eres un estratega de producto para tiendas Etsy de ropa gráfica.

PERFIL Y DISEÑOS EXISTENTES:
{self.settings}

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

        return await self._call_groq(prompt, max_tokens=1200, temperature=0.7)

    async def _call_groq(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        @retry_with_policy(policy=GROQ_POLICY)
        async def _call():
            groq_client = Groq(api_key=self.settings.GROQ_API_KEY)
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        return await groq_breaker.call(_call_groq)

    async def _generate_ideas_with_groq(self, market: dict, pinterest: dict) -> str:
        """Generate creative ideas with Groq."""
        return await self._generate_ideas_with_groq(market, pinterest)

    async def _generate_expansions_with_groq(self) -> str:
        """Generate expansion recommendations."""
        return await self._generate_expansions_with_groq()


if __name__ == "__main__":
    import asyncio

    async def test():
        agent = CreativoAgent()
        result = await agent.execute({})
        print(result)

    asyncio.run(test())
