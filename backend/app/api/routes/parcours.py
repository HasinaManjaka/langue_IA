"""Routes HTTP du parcours personnalisé (contrat US41-US44, contenu de démo US156)."""

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import select

from app.api.deps import DbSession, UtilisateurConnecte
from app.models import Lecon, ParcoursExercice, Role, StatutParcours
from app.schemas.parcours import (
    CorrectionExerciceOut,
    ExerciceParcoursOut,
    LeconParcoursOut,
    ParcoursEnCoursOut,
    ReponseExerciceCreate,
)
from app.services import parcours as service

router = APIRouter(tags=["parcours"])


def _exiger_apprenant(utilisateur) -> None:
    if utilisateur.role != Role.APPRENANT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Droits insuffisants.")


def _parcours_ou_404(db, utilisateur, id_parcours: int):
    parcours = service.parcours_pour_utilisateur(db, utilisateur.id_user, id_parcours)
    if parcours is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcours introuvable.")
    return parcours


@router.get("/parcours/en-cours", response_model=ParcoursEnCoursOut, response_model_exclude_none=True)
def lire_parcours_en_cours(db: DbSession, utilisateur: UtilisateurConnecte) -> ParcoursEnCoursOut:
    """Parcours en cours de l'apprenant connecté, avec sa grille de modules."""
    _exiger_apprenant(utilisateur)
    parcours = service.parcours_en_cours(db, utilisateur.id_user)
    if parcours is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun parcours en cours.")
    return service.construire_parcours_out(parcours)


@router.get("/parcours/{id_parcours}/exercices", response_model=list[ExerciceParcoursOut])
def lire_exercices(
    id_parcours: Annotated[int, Path(gt=0)],
    db: DbSession,
    utilisateur: UtilisateurConnecte,
) -> list[ExerciceParcoursOut]:
    """Exercices accessibles jusqu'à la leçon atteinte."""
    _exiger_apprenant(utilisateur)
    parcours = _parcours_ou_404(db, utilisateur, id_parcours)
    return [service.construire_exercice_out(ligne) for ligne in service.exercices_du_parcours(db, parcours)]


@router.get("/parcours/{id_parcours}/lecons/{numero_lecon}", response_model=LeconParcoursOut)
def lire_lecon(
    id_parcours: Annotated[int, Path(gt=0)],
    numero_lecon: Annotated[int, Path(gt=0)],
    db: DbSession,
    utilisateur: UtilisateurConnecte,
) -> LeconParcoursOut:
    """Leçon originale et exercices publics ; aucun corrigé n'est exposé."""
    _exiger_apprenant(utilisateur)
    parcours = _parcours_ou_404(db, utilisateur, id_parcours)
    if numero_lecon > parcours.lecon_atteinte:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette leçon n'est pas encore accessible.")

    lecon = db.scalar(
        select(Lecon).where(
            Lecon.id_parcours == parcours.id_parcours,
            Lecon.numero_lecon == numero_lecon,
        )
    )
    if lecon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Leçon introuvable.")

    return service.construire_lecon_out(parcours, lecon, service.exercices_du_parcours(db, parcours, numero_lecon))


@router.post(
    "/parcours/{id_parcours}/exercices/{id_parcours_exercice}/reponse",
    response_model=CorrectionExerciceOut,
)
def soumettre_reponse(
    id_parcours: Annotated[int, Path(gt=0)],
    id_parcours_exercice: Annotated[int, Path(gt=0)],
    donnees: ReponseExerciceCreate,
    db: DbSession,
    utilisateur: UtilisateurConnecte,
) -> CorrectionExerciceOut:
    """Corrige une réponse contre le corrigé privé et met à jour la progression."""
    _exiger_apprenant(utilisateur)
    parcours = _parcours_ou_404(db, utilisateur, id_parcours)
    if parcours.statut != StatutParcours.EN_COURS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce parcours n'est plus en cours.")
    ligne = db.scalar(
        select(ParcoursExercice).where(
            ParcoursExercice.id_parcours == parcours.id_parcours,
            ParcoursExercice.id_parcours_exercice == id_parcours_exercice,
        )
    )
    if ligne is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercice introuvable dans ce parcours.")
    if ligne.numero_lecon > parcours.lecon_atteinte:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cet exercice n'est pas encore accessible.")

    try:
        contenu = json.loads(ligne.exercice.contenu)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Contenu d'exercice invalide.") from exc
    if not isinstance(contenu, dict) or contenu.get("format") != donnees.format:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Format de réponse inattendu.")

    return service.corriger_exercice(db, parcours, ligne, donnees.format, donnees.reponse)
