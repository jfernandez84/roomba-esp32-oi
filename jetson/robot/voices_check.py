#!/usr/bin/env python3
"""Lista las voces de síntesis de voz de Mistral: idiomas disponibles y voces en español."""
from mistral_client import list_voices

data = list_voices()
voices = data.get("items") or data.get("data") or data.get("voices") or [] if isinstance(data, dict) else data

languages = {}
for voice in voices:
    for lang in voice.get("languages") or ["(sin idioma)"]:
        languages[lang] = languages.get(lang, 0) + 1

print("Total de voces: %d" % len(voices))
print("Idiomas (cantidad de voces): " + ", ".join("%s=%d" % kv for kv in sorted(languages.items())))
print()
print("Voces en español:")
found = False
for voice in voices:
    if any(lang.lower().startswith("es") for lang in (voice.get("languages") or [])):
        found = True
        print("  %s | %s | %s | %s | id=%s" % (
            voice.get("name"), ",".join(voice.get("languages") or []), voice.get("gender"),
            ",".join(voice.get("tags") or []), voice.get("id")))
if not found:
    print("  (ninguna)")
