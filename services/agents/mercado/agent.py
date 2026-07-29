"""
Mercado Agent - Market Analysis Agent.
Analyzes market trends using Google Trends and Etsy API.
"""
import os
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from groq import Groq
from pytrends.request import TrendReq

from services.agents.base import BaseAgent
from services.shared.config import get_settings
from services.shared.resilience import (
    circuit_breaker_registry,
    retry_with_policy,
    CircuitBreakerConfig,
    GROQ_POLICY,
    ETSY_POLICY,
    TRENDS_POLICY,
)
from services.shared.resilience import circuit_breaker_registry

logger = logging.getLogger(__name__)

settings = get_settings()

# Get circuit breakers
groq_breaker = circuit_breaker_registry.get_or_create("groq")
etsy_breaker = circuit_breaker_registry.get_or_create("etsy")
trends_breaker = circuit_breaker_registry.get_or_create("trends")


class MercadoAgent(BaseAgent):
    """Market Analysis Agent - Analyzes market trends using Google Trends and Etsy API."""
    
    agent_name = "mercado"
    
    def __init__(self, settings_override: Optional[Any] = None):
        super().__init__("mercado", settings_override or get_settings())
        self.groq_client = Groq(api_key=self.settings.GROQ_API_KEY)
        self.trends_client = TrendReq(hl='en-US', tz=360)
    
    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute market analysis.
        
        Args:
            payload: Optional input with keywords, date_range, geo
            
        Returns:
            Market analysis report
        """
        keywords = payload.get("keywords") if payload else [
            "national park shirt",
            "state flag tee",
            "hiking t-shirt",
            "vintage national park",
            "state pride apparel"
        ]
        date_range = payload.get("date_range", "today 3-m") if payload else "today 3-m"
        geo = payload.get("geo", "US") if payload else "US"
        
        logger.info(f"Starting market analysis for keywords: {keywords}")
        
        # Fetch trends
        trends = await self._fetch_trends(keywords, geo=geo)
        
        # Fetch competition
        competition = await self._fetch_competition()
        
        # Analyze with Groq
        analysis = await self._analyze_with_groq(keywords, trends, competition)
        
        # Extract keywords and price ranges
        keywords_extracted = self._extract_keywords(analysis)
        price_ranges = self._extract_price_ranges(competition)
        
        report = {
            "date": datetime.utcnow().isoformat(),
            "trends": trends,
            "competition": competition,
            "analysis": analysis,
            "keywords": keywords_extracted,
            "price_ranges": price_ranges,
        }
        
        return report
    
    async def _fetch_trends(self, keywords: List[str], geo: str = "US") -> List[Dict]:
        """Fetch Google Trends data with circuit breaker and retry."""
        
        @retry_with_policy(policy=trends_breaker.policy)
        async def _fetch():
            # Use pytrends
            pt = TrendReq(hl='en-US', tz=360)
            pt.build_payload(keywords, timeframe='today 3-m', geo=geo)
            data = pt.interest_over_time()
            
            if data.empty:
                return []
            
            # Calculate average interest over last 4 weeks
            recent = data.tail(4)
            results = []
            for kw in keywords:
                if kw in recent.columns:
                    avg = recent[kw].mean()
                    results.append({"keyword": kw, "interest": round(avg, 1)})
            return sorted(results, key=lambda x: x["interest"], reverse=True)
        
        try:
            return await trends_breaker.call(_fetch)
        except Exception as e:
            logger.warning(f"Google Trends failed: {e}")
            return []
    
    async def _fetch_competition(self) -> List[Dict]:
        """Fetch competition data from Etsy API with circuit breaker."""
        
        @retry_with_policy(policy=ETSY_POLICY)
        async def _fetch():
            import requests
            
            headers = {"x-api-key": self.settings.ETSY_API_KEY}
            keywords = ["national park shirt", "state flag tee", "hiking shirt"]
            all_results = []
            
            for kw in keywords:
                params = {"keywords": kw, "limit": 8, "sort_on": "score"}
                r = requests.get(
                    "https://openapi.etsy.com/v3/application/listings/active",
                    headers=headers,
                    params=params,
                    timeout=15
                )
                
                if r.status_code == 200:
                    listings = r.json().get("results", [])
                    for l in listings[:5]:
                        price = l["price"]["amount"] / l["price"]["divisor"]
                        all_results.append({
                            "title": l["title"][:60],
                            "price": price,
                            "favorites": l.get("num_favorers", 0),
                            "url": l.get("url", ""),
                        })
                else:
                    logger.warning(f"Etsy API error for '{kw}': {r.status_code}")
            
            return all_results
        
        try:
            return await etsy_breaker.call(_fetch)
        except Exception as e:
            logger.error(f"Etsy API failed: {e}")
            return []
    
    async def _analyze_with_groq(self, keywords: List[str], trends: List[Dict], competition: List[Dict]) -> str:
        """Analyze market data with Groq AI using circuit breaker and retry."""
        
        @retry_with_policy(policy=GROQ_POLICY)
        async def _analyze():
            groq_client = Groq(api_key=self.settings.GROQ_API_KEY)
            
            prompt = f"""Eres un experto en e-commerce de ropa con diseños gráficos en Etsy.
Tu trabajo es analizar datos de mercado y dar recomendaciones estratégicas.

KEYWORDS ANALIZADAS:
{keywords}

DATOS DE GOOGLE TRENDS (últimas 4 semanas):
{trends}

COMPETENCIA EN ETSY:
{competition}

Con estos datos, entrega un análisis estructurado:

## 1. TENDENCIAS EN ALZA
¿Qué estilos o temas están creciendo que encajen con el perfil de esta tienda?
(máximo 3 tendencias, cada una con explicación breve)

## 2. OPORTUNIDADES DE NICHO
¿Dónde hay menos competencia y esta tienda puede destacar con su estilo único?
(máximo 2 oportunidades)

## 3. ANÁLISIS DE PRECIOS
¿Cómo se compara el rango de precios del perfil con la competencia?
¿Ajustar hacia arriba o hacia abajo?

## 4. TOP 10 TAGS PARA ETSY ESTA SEMANA
Lista los 10 keywords más estratégicos para usar ahora,
basándose en las tendencias y el estilo de la tienda.

Sé directo y específico. Menciona el estilo de la tienda en tus recomendaciones."""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
            )
            return response.choices[0].message.content
        
        return await groq_breaker.call(_analyze)
    
    def _extract_keywords(self, analysis: str) -> List[str]:
        """Extract keywords from analysis text."""
        import re
        keywords = []
        # Look for numbered lists or bullet points
        lines = analysis.split('\n')
        for line in lines:
            if any(line.strip().startswith(prefix) for prefix in ['1.', '2.', '3.', '4.', '- ', '* ']):
                words = re.findall(r'\b[a-zA-Z]{3,}\b', line)
                keywords.extend([w.lower() for w in words if len(w) > 3])
        return list(set(keywords))[:10]
    
    def _extract_price_ranges(self, competition: List[Dict]) -> Dict:
        """Extract price ranges from competition data."""
        if not competition:
            return {}
        
        prices = [c.get("price", 0) for c in competition if c.get("price")]
        if not prices:
            return {}
        
        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "median": sorted(prices)[len(prices)//2],
        }


# For direct execution
if __name__ == "__main__":
    import asyncio
    
    async def test():
        agent = MercadoAgent()
        result = await agent.execute({})
        print(result)
    
    asyncio.run(test())