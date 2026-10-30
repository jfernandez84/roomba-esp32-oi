#!/usr/bin/env python3
"""Comprueba la clave de Mistral: lista los modelos útiles y hace una pregunta corta."""
from mistral_client import chat, list_models

print("Modelos disponibles (small, ministral, medium, voxtral):")
for model in list_models():
    if any(word in model for word in ("small", "ministral", "medium", "voxtral")):
        print("  " + model)

print("\nPrueba de conversación:")
print(chat([
    {"role": "system", "content": "Eres un robot amable. Responde en español latino, en una frase corta."},
    {"role": "user", "content": "Hola, ¿quién eres?"},
]))
