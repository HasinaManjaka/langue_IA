"""Route authentifiée du chatbot : relais vers le service IA sans exposer ce dernier."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, UtilisateurConnecte
from app.models import Parcours, Role
from app.schemas.chatbot import (
    ContexteChatbotIA,
    EntreeChatbotIA,
    MessageChatbotCreate,
    ReponseChatbot,
    RequeteChatbotIA,
)
from app.services.ia import ErreurServiceIA, envoyer_message_chatbot
from app.services.parcours import parcours_en_cours

router = APIRouter(tags=["chatbot"])

LANGUES_IA = frozenset({"fr", "en", "zh", "it", "de"})
NIVEAUX_CECRL = ("A1", "A2", "B1", "B2", "C1", "C2")
NIVEAUX_HSK = ("HSK 1", "HSK 2", "HSK 3", "HSK 4", "HSK 5", "HSK 6")

_ERREURS_HTTP = {
    "non_configure": (status.HTTP_503_SERVICE_UNAVAILABLE, "Le professeur IA est indisponible."),
    "timeout": (status.HTTP_504_GATEWAY_TIMEOUT, "Le professeur IA n'a pas répondu à temps."),
    "indisponible": (status.HTTP_502_BAD_GATEWAY, "Le professeur IA est momentanément indisponible."),
    "reponse_invalide": (status.HTTP_502_BAD_GATEWAY, "Le professeur IA a renvoyé une réponse inexploitable."),
}


def _niveau_ia(parcours: Parcours | None, referentiel: str) -> str:
    """Choisir un niveau valide pour le référentiel, sans jamais transmettre une valeur hors contrat."""
    niveaux = NIVEAUX_HSK if referentiel == "HSK" else NIVEAUX_CECRL
    if parcours is None:
        return niveaux[0]

    test = parcours.test_diagnostic
    niveau = test.niveau_final.code if test is not None and test.niveau_final is not None else parcours.niveau_vise.code
    return niveau if niveau in niveaux else niveaux[0]


def _erreur_http(code: str) -> HTTPException:
    """Traduire un échec technique en statut public, sans exposer la réponse du fournisseur."""
    if code in _ERREURS_HTTP:
        statut, detail = _ERREURS_HTTP[code]
        return HTTPException(statut, detail)
    if code.startswith("http_"):
        statut_ia = int(code.removeprefix("http_"))
        if statut_ia == status.HTTP_429_TOO_MANY_REQUESTS:
            return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de messages envoyés au professeur IA.")
        if 400 <= statut_ia < 500:
            return HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "La demande envoyée au professeur IA a été refusée."
            )
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "Le professeur IA est momentanément indisponible.")


@router.post("/chatbot/message", response_model=ReponseChatbot)
def envoyer_message(
    donnees: MessageChatbotCreate,
    db: DbSession,
    utilisateur: UtilisateurConnecte,
) -> ReponseChatbot:
    """Renvoyer la réponse de l'assistant après validation du contrat côté backend."""
    if utilisateur.role != Role.APPRENANT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Droits insuffisants.")

    parcours = parcours_en_cours(db, utilisateur.id_user)
    code_langue = parcours.langue.code if parcours is not None else "en"
    if code_langue not in LANGUES_IA:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Langue non prise en charge par le professeur IA.")
    referentiel = "HSK" if code_langue == "zh" else "CECRL"

    requete = RequeteChatbotIA(
        request_id=uuid4(),
        contexte=ContexteChatbotIA(
            code_langue=code_langue,
            referentiel=referentiel,
            niveau_preliminaire=_niveau_ia(parcours, referentiel),
        ),
        entree=EntreeChatbotIA(message=donnees.message, historique=donnees.historique),
    )

    try:
        reponse_ia = envoyer_message_chatbot(requete)
    except ErreurServiceIA as erreur:
        raise _erreur_http(erreur.code) from None
    return ReponseChatbot(reponse=reponse_ia.resultat.reponse)
