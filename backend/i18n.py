"""Tekstene tjenesten selv viser brukeren, på brukerens språk.

Det meste av grensesnittet oversettes i nettleseren (web/lang/*.json). Men
noen setninger lages her - feilen fra en opplasting, svaret fra en
nokkeltest, meldingen om at koen er full - og de skal ikke komme paa norsk
til en som har valgt engelsk. Spraaket er `settings.ui_language`, satt fra
grensesnittet.

Bare engelsk er komplett av nodvendighet: en nokkel som mangler i et annet
spraak faller tilbake til engelsk, ikke til nokkelnavnet.
"""
from __future__ import annotations

LANGUAGES = ("en", "nb", "sv", "de", "fr", "es")

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "queue_full": "The queue is full - the audio is saved but not transcribed.",
        "transcription_failed": "Transcription failed: {err}",
        "attempt": "[attempt {n}/{max}] {err}",
        "failed": "[error] {err}",
        "bad_token": "Invalid session token",
        "unknown_provider": "Unknown provider",
        "unknown_model": "Unknown model",
        "unknown_segment": "No such segment",
        "audio_gone": "The audio file is gone",
        "nothing_to_change": "Nothing to change",
        "audio_not_ready": "The audio engine is not ready",
        "audio_unavailable": "The audio system is not available: {err}",
        "save_failed": "Could not save the recording: {err}",
        "no_key": "No key saved",
        "unreachable": "Could not reach {provider}: {err}",
        "key_ok": "The key works",
        "key_rejected": "Rejected ({code})",
        "missing_key": "Missing API key for {provider}. Add it under Settings → Cloud.",
        "key_rejected_by": "The API key for {provider} was rejected.",
        "rate_limited": "{provider} has reached its rate limit.",
        "ollama_unreachable": "Could not reach Ollama at {url}: {err}",
        "ollama_no_models": "Ollama responds, but has no models downloaded",
        "ollama_missing_model": "Ollama does not have the model “{model}”. Available: {models}",
        "ollama_ok": "Ollama responds with {n} model(s): {models}",
        "ollama_pull": "Ollama has no models. Download one (e.g. llama3.2) in NOMAD under "
                       "AI Assistant, or with `ollama pull`.",
        "ollama_no_audio": "Ollama cannot transcribe audio. Choose the local engine under "
                           "Text, or Groq/OpenAI under Cloud.",
        "upload_unreadable": "Could not read {name}: {reason}",
        "upload_silent": "The file contains no audio",
        "export_title": "Radio log",
        "export_meta": "Exported {stamp} - {n} transmissions",
        "export_no_speech": "(no speech)",
        "export_note": "Note",
    },
    "nb": {
        "queue_full": "Køen er full - lyden er lagret, men ikke transkribert.",
        "transcription_failed": "Transkribering feilet: {err}",
        "attempt": "[forsøk {n}/{max}] {err}",
        "failed": "[feil] {err}",
        "bad_token": "Ugyldig øktnøkkel",
        "unknown_provider": "Ukjent leverandør",
        "unknown_model": "Ukjent modell",
        "unknown_segment": "Segmentet finnes ikke",
        "audio_gone": "Lydfila er borte",
        "nothing_to_change": "Ingenting å endre",
        "audio_not_ready": "Lydmotoren er ikke klar",
        "audio_unavailable": "Lydsystemet er ikke tilgjengelig: {err}",
        "save_failed": "Kunne ikke lagre opptaket: {err}",
        "no_key": "Ingen nøkkel lagret",
        "unreachable": "Nådde ikke {provider}: {err}",
        "key_ok": "Nøkkelen virker",
        "key_rejected": "Avvist ({code})",
        "missing_key": "Mangler API-nøkkel for {provider}. Legg den inn under Innstillinger → Sky.",
        "key_rejected_by": "API-nøkkelen for {provider} ble avvist.",
        "rate_limited": "{provider} har nådd kvotegrensa.",
        "ollama_unreachable": "Nådde ikke Ollama på {url}: {err}",
        "ollama_no_models": "Ollama svarer, men har ingen modeller lastet ned",
        "ollama_missing_model": "Ollama har ikke modellen «{model}». Finnes: {models}",
        "ollama_ok": "Ollama svarer med {n} modell(er): {models}",
        "ollama_pull": "Ollama har ingen modeller. Last ned en (f.eks. llama3.2) i NOMAD under "
                       "AI Assistant, eller med `ollama pull`.",
        "ollama_no_audio": "Ollama kan ikke transkribere lyd. Velg lokal motor under Tekst, "
                           "eller Groq/OpenAI under Sky.",
        "upload_unreadable": "Kunne ikke lese {name}: {reason}",
        "upload_silent": "Fila inneholder ingen lyd",
        "export_title": "Sambandslogg",
        "export_meta": "Eksportert {stamp} - {n} transmisjoner",
        "export_no_speech": "(ingen tale)",
        "export_note": "Notat",
    },
    "sv": {
        "queue_full": "Kön är full - ljudet är sparat men inte transkriberat.",
        "transcription_failed": "Transkriberingen misslyckades: {err}",
        "attempt": "[försök {n}/{max}] {err}",
        "failed": "[fel] {err}",
        "bad_token": "Ogiltig sessionsnyckel",
        "unknown_provider": "Okänd leverantör",
        "unknown_model": "Okänd modell",
        "unknown_segment": "Segmentet finns inte",
        "audio_gone": "Ljudfilen är borta",
        "nothing_to_change": "Inget att ändra",
        "audio_not_ready": "Ljudmotorn är inte redo",
        "audio_unavailable": "Ljudsystemet är inte tillgängligt: {err}",
        "save_failed": "Kunde inte spara inspelningen: {err}",
        "no_key": "Ingen nyckel sparad",
        "unreachable": "Nådde inte {provider}: {err}",
        "key_ok": "Nyckeln fungerar",
        "key_rejected": "Avvisad ({code})",
        "missing_key": "API-nyckel för {provider} saknas. Lägg in den under Inställningar → Moln.",
        "key_rejected_by": "API-nyckeln för {provider} avvisades.",
        "rate_limited": "{provider} har nått sin kvotgräns.",
        "ollama_unreachable": "Nådde inte Ollama på {url}: {err}",
        "ollama_no_models": "Ollama svarar, men har inga nedladdade modeller",
        "ollama_missing_model": "Ollama har inte modellen ”{model}”. Finns: {models}",
        "ollama_ok": "Ollama svarar med {n} modell(er): {models}",
        "ollama_pull": "Ollama har inga modeller. Ladda ned en (t.ex. llama3.2) i NOMAD under "
                       "AI Assistant, eller med `ollama pull`.",
        "ollama_no_audio": "Ollama kan inte transkribera ljud. Välj lokal motor under Text, "
                           "eller Groq/OpenAI under Moln.",
        "upload_unreadable": "Kunde inte läsa {name}: {reason}",
        "upload_silent": "Filen innehåller inget ljud",
        "export_title": "Radiologg",
        "export_meta": "Exporterad {stamp} - {n} sändningar",
        "export_no_speech": "(inget tal)",
        "export_note": "Anteckning",
    },
    "de": {
        "queue_full": "Die Warteschlange ist voll - das Audio ist gespeichert, aber nicht transkribiert.",
        "transcription_failed": "Transkription fehlgeschlagen: {err}",
        "attempt": "[Versuch {n}/{max}] {err}",
        "failed": "[Fehler] {err}",
        "bad_token": "Ungültiger Sitzungsschlüssel",
        "unknown_provider": "Unbekannter Anbieter",
        "unknown_model": "Unbekanntes Modell",
        "unknown_segment": "Segment nicht gefunden",
        "audio_gone": "Die Audiodatei ist nicht mehr da",
        "nothing_to_change": "Nichts zu ändern",
        "audio_not_ready": "Die Audio-Engine ist nicht bereit",
        "audio_unavailable": "Das Audiosystem ist nicht verfügbar: {err}",
        "save_failed": "Die Aufnahme konnte nicht gespeichert werden: {err}",
        "no_key": "Kein Schlüssel gespeichert",
        "unreachable": "{provider} nicht erreichbar: {err}",
        "key_ok": "Der Schlüssel funktioniert",
        "key_rejected": "Abgelehnt ({code})",
        "missing_key": "API-Schlüssel für {provider} fehlt. Unter Einstellungen → Cloud eintragen.",
        "key_rejected_by": "Der API-Schlüssel für {provider} wurde abgelehnt.",
        "rate_limited": "{provider} hat sein Kontingent erreicht.",
        "ollama_unreachable": "Ollama unter {url} nicht erreichbar: {err}",
        "ollama_no_models": "Ollama antwortet, hat aber keine Modelle heruntergeladen",
        "ollama_missing_model": "Ollama hat das Modell „{model}“ nicht. Vorhanden: {models}",
        "ollama_ok": "Ollama antwortet mit {n} Modell(en): {models}",
        "ollama_pull": "Ollama hat keine Modelle. Laden Sie eines (z. B. llama3.2) in NOMAD unter "
                       "AI Assistant oder mit `ollama pull` herunter.",
        "ollama_no_audio": "Ollama kann kein Audio transkribieren. Wählen Sie unter Text die lokale "
                           "Engine oder unter Cloud Groq/OpenAI.",
        "upload_unreadable": "{name} konnte nicht gelesen werden: {reason}",
        "upload_silent": "Die Datei enthält kein Audio",
        "export_title": "Funklogbuch",
        "export_meta": "Exportiert {stamp} - {n} Durchsagen",
        "export_no_speech": "(keine Sprache)",
        "export_note": "Notiz",
    },
    "fr": {
        "queue_full": "La file est pleine - l'audio est sauvegardé mais pas transcrit.",
        "transcription_failed": "La transcription a échoué : {err}",
        "attempt": "[essai {n}/{max}] {err}",
        "failed": "[erreur] {err}",
        "bad_token": "Jeton de session invalide",
        "unknown_provider": "Fournisseur inconnu",
        "unknown_model": "Modèle inconnu",
        "unknown_segment": "Segment introuvable",
        "audio_gone": "Le fichier audio a disparu",
        "nothing_to_change": "Rien à modifier",
        "audio_not_ready": "Le moteur audio n'est pas prêt",
        "audio_unavailable": "Le système audio n'est pas disponible : {err}",
        "save_failed": "Impossible d'enregistrer la capture : {err}",
        "no_key": "Aucune clé enregistrée",
        "unreachable": "Impossible de joindre {provider} : {err}",
        "key_ok": "La clé fonctionne",
        "key_rejected": "Refusée ({code})",
        "missing_key": "Clé API manquante pour {provider}. Ajoutez-la sous Réglages → Cloud.",
        "key_rejected_by": "La clé API pour {provider} a été refusée.",
        "rate_limited": "{provider} a atteint sa limite de requêtes.",
        "ollama_unreachable": "Impossible de joindre Ollama à {url} : {err}",
        "ollama_no_models": "Ollama répond, mais n'a aucun modèle téléchargé",
        "ollama_missing_model": "Ollama n'a pas le modèle « {model} ». Disponibles : {models}",
        "ollama_ok": "Ollama répond avec {n} modèle(s) : {models}",
        "ollama_pull": "Ollama n'a aucun modèle. Téléchargez-en un (p. ex. llama3.2) dans NOMAD sous "
                       "AI Assistant, ou avec `ollama pull`.",
        "ollama_no_audio": "Ollama ne transcrit pas l'audio. Choisissez le moteur local sous Texte, "
                           "ou Groq/OpenAI sous Cloud.",
        "upload_unreadable": "Impossible de lire {name} : {reason}",
        "upload_silent": "Le fichier ne contient aucun son",
        "export_title": "Journal radio",
        "export_meta": "Exporté le {stamp} - {n} transmissions",
        "export_no_speech": "(aucune parole)",
        "export_note": "Note",
    },
    "es": {
        "queue_full": "La cola está llena: el audio está guardado, pero no transcrito.",
        "transcription_failed": "La transcripción falló: {err}",
        "attempt": "[intento {n}/{max}] {err}",
        "failed": "[error] {err}",
        "bad_token": "Clave de sesión no válida",
        "unknown_provider": "Proveedor desconocido",
        "unknown_model": "Modelo desconocido",
        "unknown_segment": "El segmento no existe",
        "audio_gone": "El archivo de audio ya no está",
        "nothing_to_change": "Nada que cambiar",
        "audio_not_ready": "El motor de audio no está listo",
        "audio_unavailable": "El sistema de audio no está disponible: {err}",
        "save_failed": "No se pudo guardar la grabación: {err}",
        "no_key": "No hay clave guardada",
        "unreachable": "No se pudo contactar con {provider}: {err}",
        "key_ok": "La clave funciona",
        "key_rejected": "Rechazada ({code})",
        "missing_key": "Falta la clave API de {provider}. Añádala en Ajustes → Nube.",
        "key_rejected_by": "La clave API de {provider} fue rechazada.",
        "rate_limited": "{provider} ha alcanzado su límite de uso.",
        "ollama_unreachable": "No se pudo contactar con Ollama en {url}: {err}",
        "ollama_no_models": "Ollama responde, pero no tiene modelos descargados",
        "ollama_missing_model": "Ollama no tiene el modelo «{model}». Disponibles: {models}",
        "ollama_ok": "Ollama responde con {n} modelo(s): {models}",
        "ollama_pull": "Ollama no tiene modelos. Descargue uno (p. ej. llama3.2) en NOMAD en "
                       "AI Assistant, o con `ollama pull`.",
        "ollama_no_audio": "Ollama no puede transcribir audio. Elija el motor local en Texto, "
                           "o Groq/OpenAI en Nube.",
        "upload_unreadable": "No se pudo leer {name}: {reason}",
        "upload_silent": "El archivo no contiene audio",
        "export_title": "Registro de radio",
        "export_meta": "Exportado {stamp} - {n} transmisiones",
        "export_no_speech": "(sin voz)",
        "export_note": "Nota",
    },
}


def current_language() -> str:
    """Spraaket brukeren har valgt. Lest lat: config importerer ikke oss."""
    try:
        from .config import settings

        lang = settings.ui_language
    except Exception:  # noqa: BLE001 - under oppstart kan config mangle
        lang = "en"
    return lang if lang in MESSAGES else "en"


def t(key: str, **vars) -> str:
    """Setningen for `key` paa brukerens spraak, med {felt} fylt inn."""
    table = MESSAGES.get(current_language(), MESSAGES["en"])
    text = table.get(key) or MESSAGES["en"].get(key) or key
    try:
        return text.format(**vars) if vars else text
    except (KeyError, IndexError):
        return text


__all__ = ["LANGUAGES", "MESSAGES", "t", "current_language"]
