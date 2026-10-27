from app.intents import detect_intent


def test_greeting_is_detected():
    result = detect_intent("Hola")
    assert result["intent"] == "saludo"
    assert "SismoWatch" in result["answer"]


def test_greeting_with_question_is_detected():
    result = detect_intent("Hola, como estas?")
    assert result["intent"] == "saludo"


def test_thanks_and_goodbye_are_detected():
    assert detect_intent("Muchas gracias")["intent"] == "agradecimiento"
    assert detect_intent("Hasta luego")["intent"] == "despedida"


def test_capabilities_and_identity_are_detected():
    assert detect_intent("Que puedes hacer?")["intent"] == "capacidades"
    assert detect_intent("Quien eres?")["intent"] == "identidad"


def test_profanity_gets_a_polite_response():
    result = detect_intent("eres un idiota")
    assert result["intent"] == "respeto"
    assert "respetuoso" in result["answer"]


def test_data_question_is_not_an_intent():
    assert detect_intent("Cuantos sismos hubo en las ultimas 24 horas?") is None
    assert detect_intent("Donde ocurrio el ultimo sismo?") is None


def test_unknown_short_message_is_not_sent_to_sql():
    result = detect_intent("capital de Francia")
    assert result["intent"] == "desconocido"


def test_greeting_with_short_context_is_detected():
    assert detect_intent("Hola amigo")["intent"] == "saludo"
    assert detect_intent("Hola, cuantos sismos hubo?") is None
