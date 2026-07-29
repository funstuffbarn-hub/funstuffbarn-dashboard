"""
Pinterest Trends Agent.
"""
import os
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

cliente_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODELO = "llama-3.1-8b-instant"

# Importar sistema de archivado
try:
    from prompt_archive import archivar_prompt, detectar_categoria, sanitizar_nombre_archivo
    ARCHIVO_DISPONIBLE = True
except ImportError:
    ARCHIVO_DISPONIBLE = False
    print("  ⚠️  prompt_archive no disponible, saltando archivado automático")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def ejecutar() -> str:
    perfil = cargar_perfil()
    
    # Ajusta estos keywords a tu nicho
    keywords_pinterest = [
        "graphic tee aesthetic",
        "art hoodie style",
        "illustration shirt outfit",
        "indie fashion graphic"
    ]

    trends_pagina   = leer_pinterest_trends()
    trends_busqueda = buscar_tendencias_pinterest_via_google(keywords_pinterest)
    analisis        = analizar_con_groq(perfil, trends_pagina, trends_busqueda)

    fecha = datetime.now().strftime("%Y-%m-%d")
    with open(f"reportes/pinterest_{fecha}.txt", "w", encoding="utf-8") as f:
        f.write(f"TENDENCIAS PINTEREST — {fecha}\n{'='*50}\n\n")
        f.write(f"DATOS RECOPILADOS:\n{trends_busqueda}\n\n")
        f.write(f"ANÁLISIS:\n{analisis}")

    # Archivar tendencias como prompts visuales
    if ARCHIVO_DISPONIBLE:
        print("  📁 Archivando tendencias Pinterest...")
        archivar_tendencias_pinterest(analisis, fecha)

    return analisis


def cargar_perfil() -> str:
    try:
        with open("perfil_de_marca.txt", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Perfil no encontrado. Completa perfil_de_marca.txt"


def leer_pinterest_trends() -> str:
    """Lee la página de tendencias oficiales de Pinterest."""
    print("  📌 Leyendo Pinterest Trends...")
    try:
        url = "https://trends.pinterest.com"
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        textos = []
        for tag in soup.find_all(["h2", "h3", "p", "span"]):
            t = tag.get_text(strip=True)
            if 20 < len(t) < 200:
                textos.append(t)
        contenido = "\n".join(textos[:30])
        return contenido if contenido else "Página de tendencias no disponible directamente."
    except Exception as e:
        return f"No se pudo acceder a Pinterest Trends: {e}"


def buscar_tendencias_pinterest_via_google(keywords: list) -> str:
    """Busca pins y tendencias de Pinterest usando Google."""
    print("  📌 Buscando tendencias en Pinterest via Google...")
    resultados = []
    for kw in keywords:
        try:
            query = f"site:pinterest.com {kw} 2025 trending"
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            snippets = soup.find_all("div", class_=["BNeawe", "s3v9rd"])
            textos = [s.get_text()[:150] for s in snippets[:3] if s.get_text()]
            if textos:
                resultados.append(f"Pinterest '{kw}':\n" + "\n".join(f"  • {t}" for t in textos))
        except Exception as e:
            resultados.append(f"Pinterest '{kw}': no disponible ({e})")
    return "\n\n".join(resultados) if resultados else "Sin resultados de Pinterest."


def analizar_con_groq(perfil: str, pinterest_trends: str, pinterest_busqueda: str) -> str:
    prompt = f"""Eres un experto en tendencias visuales y e-commerce de ropa en Pinterest y Etsy.

PERFIL DE LA MARCA:
{perfil[:1200]}

DATOS DE PINTEREST TRENDS:
{pinterest_trends[:800]}

BÚSQUEDAS EN PINTEREST:
{pinterest_busqueda[:1200]}

Analiza esta información y entrega:

## TENDENCIAS VISUALES EN PINTEREST
¿Qué estéticas, paletas de color y estilos visuales están dominando
en Pinterest ahora mismo que sean relevantes para esta tienda?
(máximo 4 tendencias, cada una con descripción visual concreta)

## TEMAS EN ALZA PARA DISEÑOS DE ROPA
¿Qué conceptos o temáticas están siendo más guardados/compartidos
en Pinterest que encajen con el estilo de esta marca?

## OPORTUNIDADES ESPECÍFICAS
¿Qué tipo de contenido visual debería crear esta tienda para
capitalizar las tendencias actuales de Pinterest?

## KEYWORDS PARA PINTEREST Y ETSY
10 términos de búsqueda que están en tendencia en Pinterest
y que también funcionarán como tags en Etsy.

Sé específico y visual en tus descripciones. Responde en español."""

    respuesta = cliente_groq.chat.completions.create(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500
    )
    return respuesta.choices[0].message.content


if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  AGENTE PINTEREST — TENDENCIAS VISUALES")
    print(f"{'='*55}\n")
    resultado = ejecutar()
    print(resultado)
    fecha = datetime.now().strftime("%Y-%m-%d")
    print(f"\n✅ Guardado en reportes/pinterest_{fecha}.txt")