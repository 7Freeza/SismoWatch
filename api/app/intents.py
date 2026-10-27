import re

from app.text_utils import normalize_text

GREETING_PHRASES = {
    "hola",
    "holi",
    "holis",
    "buenas",
    "buen dia",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "hey",
    "saludos",
    "que tal",
    "hola que tal",
    "hola como estas",
    "hola buenas",
    "hola sismowatch",
    "hola amigo",
    "hola equipo",
    "hola asistente",
    "hola buenos dias",
    "hola buenas tardes",
    "hola buenas noches",
    "hello",
    "hi",
}

THANKS_PHRASES = {
    "gracias",
    "muchas gracias",
    "mil gracias",
    "gracias totales",
    "te agradezco",
    "thanks",
}

GOODBYE_PHRASES = {
    "adios",
    "chao",
    "chau",
    "hasta luego",
    "nos vemos",
    "bye",
    "hasta pronto",
}

IDENTITY_PHRASES = {
    "quien eres",
    "quien sos",
    "como te llamas",
    "que eres",
    "quien es sismowatch",
}

CAPABILITY_PHRASES = {
    "que puedes hacer",
    "que sabes hacer",
    "ayuda",
    "help",
    "en que me puedes ayudar",
    "para que sirves",
    "que haces",
}

PROFANITY_WORDS = {
    "puta",
    "puto",
    "mierda",
    "idiota",
    "estupido",
    "estupida",
    "imbecil",
    "tarado",
    "tarada",
    "gonorrea",
    "hijueputa",
    "malparido",
    "malparida",
    "verga",
    "pendejo",
    "pendeja",
    "cabron",
    "cabrona",
    "hp",
}

DATA_TERMS = (
    "sismo",
    "terremoto",
    "magnitud",
    "region",
    "zona",
    "lugar",
    "donde",
    "ubicacion",
    "epicentro",
    "tsunami",
    "profundidad",
    "evento",
    "actividad",
    "cuanto",
    "cuanta",
    "cuantos",
    "cuantas",
    "numero",
    "total",
    "ultimo",
    "ultima",
    "reciente",
    "fecha",
    "hora",
    "dia",
    "dias",
    "significativo",
    "calidad",
    "pipeline",
    "coordenada",
)

ANSWERS = {
    "saludo": (
        "Hola, soy SismoWatch, tu asistente de monitoreo sísmico. Puedo decirte cuántos sismos "
        "hubo, cuál fue el de mayor magnitud, qué regiones están más activas o mostrarte los "
        "eventos recientes."
    ),
    "agradecimiento": "Con gusto. Sigo atento si quieres consultar otra cosa sobre la actividad sísmica.",
    "despedida": "Hasta luego. SismoWatch queda monitoreando la actividad sísmica.",
    "identidad": (
        "Soy SismoWatch, un asistente de datos sísmicos. Consulto únicamente la capa curated y "
        "respondo con cifras reales; no invento eventos."
    ),
    "capacidades": (
        "Puedo responder por conteos, magnitud máxima y promedio, regiones más activas, alertas "
        "de tsunami, profundidad, eventos significativos y eventos recientes. También puedo "
        "mostrarte la tabla y el SQL validado de cada respuesta."
    ),
    "respeto": (
        "Prefiero mantener un lenguaje respetuoso. Igual puedo ayudarte con datos sísmicos: "
        "prueba con un conteo, una magnitud o las regiones con más actividad."
    ),
    "desconocido": (
        "No logré interpretar la consulta. Prueba con algo como: \"¿cuántos sismos hubo en las "
        "últimas 24 horas?\" o \"¿cuál fue el sismo de mayor magnitud en los últimos 7 días?\"."
    ),
}


def _words(value):
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def detect_intent(question):
    normalized = normalize_text(question)
    compact = " ".join(_words(question))
    words = set(_words(question))

    if words & PROFANITY_WORDS:
        return {"intent": "respeto", "answer": ANSWERS["respeto"]}
    if compact in GREETING_PHRASES:
        return {"intent": "saludo", "answer": ANSWERS["saludo"]}
    words_list = _words(question)
    if (
        words_list
        and words_list[0] in {"hola", "holi", "holis", "buenas", "hey", "saludos", "hello", "hi"}
        and not any(term in normalized for term in DATA_TERMS)
        and len(words_list) <= 5
    ):
        return {"intent": "saludo", "answer": ANSWERS["saludo"]}
    if compact in THANKS_PHRASES:
        return {"intent": "agradecimiento", "answer": ANSWERS["agradecimiento"]}
    if compact in GOODBYE_PHRASES:
        return {"intent": "despedida", "answer": ANSWERS["despedida"]}
    if compact in IDENTITY_PHRASES:
        return {"intent": "identidad", "answer": ANSWERS["identidad"]}
    if compact in CAPABILITY_PHRASES:
        return {"intent": "capacidades", "answer": ANSWERS["capacidades"]}
    if not any(term in normalized for term in DATA_TERMS) and len(words) <= 8:
        return {"intent": "desconocido", "answer": ANSWERS["desconocido"]}
    return None
