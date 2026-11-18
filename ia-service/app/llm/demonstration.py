"""Réponses de démonstration du fournisseur ``factice`` (tâche I-01).

Sans clé LLM, ``LLM_FOURNISSEUR=factice`` échouait à chaque appel (aucun scénario) : la démonstration
retombait toujours en résultat partiel ou en erreur de configuration. Avec
``LLM_FACTICE_SCENARIO=demonstration``, le faux client répond aux prompts d'évaluation diagnostic et de conversation
par un résultat **valide au sens du schéma**, **déterministe** (mêmes entrées, même sortie) et **sans appel réseau**.

Le résultat ne prétend pas être une analyse ni une réponse de modèle : il annonce la démonstration, à confirmer avec
un vrai fournisseur. Le factice reste interdit en production (``ConfigLLM``).
"""

import json
from collections.abc import Sequence

from pydantic import BaseModel

from app.llm.base import MessageLLM
from app.schemas.chatbot import ResultatChatbot
from app.schemas.diagnostic import (
    PhaseAssimil,
    PointFaible,
    PreuveReponse,
    ResultatDiagnostic,
    calculer_ecart,
    preuve_directe,
)
from app.schemas.regles import niveaux_du_referentiel

BALISE_OUVRANTE = "<donnees_diagnostic_non_fiables>"
BALISE_FERMANTE = "</donnees_diagnostic_non_fiables>"
BALISE_CONVERSATION_OUVRANTE = "<donnees_conversation_non_fiables>"
BALISE_CONVERSATION_FERMANTE = "</donnees_conversation_non_fiables>"

REPONSES_CHATBOT_DEMONSTRATION = {
    "en": "Demo answer: I can help you practise English. Ask me a short question.",
    "fr": "Réponse de démonstration : je peux vous aider à pratiquer le français. Posez une courte question.",
    "it": "Risposta di dimostrazione: posso aiutarti a praticare l'italiano. Fai una breve domanda.",
    "de": "Demonstrationsantwort: Ich kann dir beim Deutschüben helfen. Stelle eine kurze Frage.",
    "zh": "演示回答：我可以帮助你练习中文。请问一个简短问题。",
}
REPONSE_CHATBOT_DEMONSTRATION = (
    "Réponse de démonstration : je peux vous aider à pratiquer une langue. Posez-moi une courte question."
)

SCORE_NIVEAU_SUPERIEUR = 85.0
SCORE_NIVEAU_INFERIEUR = 30.0
SCORE_ACTIVATION = 60.0
SCORE_CONFIANCE = 0.5
POINTS_FAIBLES_MAX = 2

# Domaine de faiblesse observable sur une production libre, selon la compétence de la question.
_DOMAINE_PAR_COMPETENCE = {
    "ecrit": "expression_ecrite",
    "oral": "expression_orale",
    "lecture": "comprehension_ecrite",
    "ecoute": "comprehension_orale",
    "grammaire": "grammaire",
}

OBSERVATION = "Production libre retenue pour la démonstration (question {id_question})."
JUSTIFICATION = (
    "Analyse de démonstration sans modèle de langue (fournisseur factice) : "
    "ce point est à confirmer avec un vrai fournisseur LLM."
)


def _donnees_balisees(messages: Sequence[MessageLLM], balise_ouvrante: str, balise_fermante: str) -> dict | None:
    """Relire un bloc JSON balisé dans le message utilisateur, ou ``None`` s'il est absent ou invalide."""
    for message in messages:
        if message.role != "user":
            continue
        debut = message.contenu.find(balise_ouvrante)
        fin = message.contenu.find(balise_fermante)
        if debut == -1 or fin == -1:
            continue
        try:
            donnees = json.loads(message.contenu[debut + len(balise_ouvrante) : fin])
        except ValueError:
            return None
        return donnees if isinstance(donnees, dict) else None
    return None


def _donnees_diagnostic(messages: Sequence[MessageLLM]) -> dict | None:
    return _donnees_balisees(messages, BALISE_OUVRANTE, BALISE_FERMANTE)


def _niveau_estime(referentiel: str, niveau_preliminaire: str, score: float) -> str:
    """Un niveau au-dessus pour un score très haut, un niveau en dessous pour un score très bas, sinon le même."""
    niveaux = niveaux_du_referentiel(referentiel)
    position = niveaux.index(niveau_preliminaire)
    if score >= SCORE_NIVEAU_SUPERIEUR and position + 1 < len(niveaux):
        return niveaux[position + 1]
    if score < SCORE_NIVEAU_INFERIEUR and position > 0:
        return niveaux[position - 1]
    return niveau_preliminaire


def _points_faibles(preuves: list[PreuveReponse]) -> list[PointFaible]:
    """Au plus deux domaines distincts, chacun cité sur une réponse qui en est une preuve directe."""
    points: list[PointFaible] = []
    for preuve in preuves:
        domaine = _DOMAINE_PAR_COMPETENCE.get(preuve.competence)
        if domaine is None or not preuve_directe(domaine, preuve) or any(p.domaine == domaine for p in points):
            continue
        points.append(
            PointFaible(
                domaine=domaine,
                id_question=preuve.id_question,
                observation=OBSERVATION.format(id_question=preuve.id_question),
                justification=JUSTIFICATION,
            )
        )
        if len(points) == POINTS_FAIBLES_MAX:
            break
    return points


def resultat_diagnostic_demonstration(messages: Sequence[MessageLLM]) -> ResultatDiagnostic | None:
    """Construire le résultat de démonstration à partir du prompt, ou ``None`` s'il ne s'agit pas d'un diagnostic."""
    donnees = _donnees_diagnostic(messages)
    if donnees is None:
        return None
    contexte = donnees["contexte_apprenant"]
    referentiel = contexte["referentiel"]
    niveau_preliminaire = contexte["niveau_preliminaire"]
    score = float(donnees["score_preliminaire"])
    preuves = [
        PreuveReponse(id_question=r["id_question"], competence=r["competence"], type_reponse=r["type_reponse"])
        for r in donnees["reponses"]
    ]
    production = any(preuve.type_reponse in ("texte", "audio") for preuve in preuves)
    niveau_estime = _niveau_estime(referentiel, niveau_preliminaire, score)
    # Comme le schéma l'exige, l'activation suppose au moins une production libre
    phase = PhaseAssimil.ACTIVATION if production and score >= SCORE_ACTIVATION else PhaseAssimil.IMPREGNATION

    return ResultatDiagnostic(
        code_langue=contexte["code_langue"],
        referentiel=referentiel,
        niveau_estime=niveau_estime,
        phase_assimil=phase,
        points_faibles=_points_faibles(preuves),
        score_confiance=SCORE_CONFIANCE,
        niveau_preliminaire=niveau_preliminaire,
        ecart_avec_niveau_preliminaire=calculer_ecart(referentiel, niveau_preliminaire, niveau_estime),
    )


def resultat_chatbot_demonstration(messages: Sequence[MessageLLM]) -> ResultatChatbot | None:
    """Construire une réponse de démonstration à partir du bloc JSON du prompt de conversation."""
    donnees = _donnees_balisees(messages, BALISE_CONVERSATION_OUVRANTE, BALISE_CONVERSATION_FERMANTE)
    if donnees is None or not isinstance(donnees.get("message"), str) or not donnees["message"].strip():
        return None
    contexte = donnees.get("contexte_apprenant")
    code_langue = contexte.get("code_langue") if isinstance(contexte, dict) else None
    reponse = REPONSES_CHATBOT_DEMONSTRATION.get(code_langue, REPONSE_CHATBOT_DEMONSTRATION)
    return ResultatChatbot(reponse=reponse)


def repondre_demonstration(messages: Sequence[MessageLLM], schema: type[BaseModel]) -> BaseModel | None:
    """Répondeur du faux client : les schémas diagnostic et chatbot ont une réponse de démonstration."""
    if schema is ResultatDiagnostic:
        return resultat_diagnostic_demonstration(messages)
    if schema is ResultatChatbot:
        return resultat_chatbot_demonstration(messages)
    return None
