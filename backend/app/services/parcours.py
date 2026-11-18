"""Services du parcours personnalisé : lecture du contrat et correction déterministe."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Apprenant,
    CorrigeExercice,
    Parcours,
    ParcoursExercice,
    StatutParcours,
    TestDiagnostic,
)
from app.schemas.parcours import (
    CorrectionExerciceOut,
    ErreurReleveeOut,
    ExerciceLeconOut,
    ExerciceParcoursOut,
    LeconParcoursOut,
    ModuleParcoursOut,
    ParcoursEnCoursOut,
)
from app.services.phase_parcours import est_lecon_de_revision as est_revision
from app.services.scoring import cadre_de_langue

NIVEAUX_CECRL = ("A1", "A2", "B1", "B2", "C1", "C2")
NIVEAUX_HSK = ("HSK 1", "HSK 2", "HSK 3", "HSK 4", "HSK 5", "HSK 6")
LECONS_PAR_MODULE = 7
NOMS_MODULES = (
    "Premiers contacts",
    "Routines et habitudes",
    "En ville",
    "Voyages et découvertes",
    "Opinions et projets",
    "Culture et actualités",
    "Échanges professionnels",
    "Vers l'autonomie",
)


def _normaliser(texte: str) -> str:
    """Normalise sans détruire les langues non latines (chinois, cyrillique…)."""
    stable = unicodedata.normalize("NFKC", texte).casefold()
    return " ".join(re.findall(r"\w+", stable, flags=re.UNICODE))


def _statut_exercice(score: int | None) -> str:
    if score is None:
        return "A_FAIRE"
    return "REUSSI" if score >= 50 else "A_REVOIR"


def parcours_pour_utilisateur(db: Session, id_user: int, id_parcours: int) -> Parcours | None:
    """Retourne le parcours seulement s'il appartient à l'apprenant connecté."""
    return db.scalar(
        select(Parcours)
        .join(TestDiagnostic, Parcours.id_test == TestDiagnostic.id_test)
        .join(Apprenant, Apprenant.id_user == TestDiagnostic.id_apprenant)
        .where(
            Apprenant.id_user == id_user,
            Parcours.id_parcours == id_parcours,
        )
    )


def parcours_en_cours(db: Session, id_user: int) -> Parcours | None:
    """Dernier parcours en cours de l'apprenant connecté."""
    return db.scalar(
        select(Parcours)
        .join(TestDiagnostic, Parcours.id_test == TestDiagnostic.id_test)
        .where(
            TestDiagnostic.id_apprenant == id_user,
            Parcours.statut == StatutParcours.EN_COURS,
        )
        .order_by(Parcours.id_parcours.desc())
    )


def exercices_du_parcours(db: Session, parcours: Parcours, numero_lecon: int | None = None) -> list[ParcoursExercice]:
    requete = select(ParcoursExercice).where(
        ParcoursExercice.id_parcours == parcours.id_parcours,
        ParcoursExercice.numero_lecon <= parcours.lecon_atteinte,
    )
    if numero_lecon is not None:
        requete = requete.where(ParcoursExercice.numero_lecon == numero_lecon)
    return list(db.scalars(requete.order_by(ParcoursExercice.numero_lecon, ParcoursExercice.id_parcours_exercice)))


def _modules() -> list[ModuleParcoursOut]:
    return [
        ModuleParcoursOut(
            numero=index + 1,
            titre=NOMS_MODULES[index],
            description=f"Leçons {index * LECONS_PAR_MODULE + 1} à {(index + 1) * LECONS_PAR_MODULE}.",
            premiere_lecon=index * LECONS_PAR_MODULE + 1,
            derniere_lecon=(index + 1) * LECONS_PAR_MODULE,
        )
        for index in range(8)
    ]


def construire_parcours_out(parcours: Parcours) -> ParcoursEnCoursOut:
    """Convertit un parcours en DTO conforme au mapper frontend."""
    code_langue = parcours.langue.code
    cadre = cadre_de_langue(code_langue)
    ordre = NIVEAUX_HSK if cadre.value == "HSK" else NIVEAUX_CECRL
    niveauxouverts = {niveau.code for niveau in parcours.langue.niveaux}
    test = parcours.test_diagnostic

    return ParcoursEnCoursOut(
        id_parcours=parcours.id_parcours,
        statut=parcours.statut.value,
        date_creation=parcours.date_creation.isoformat(),
        code_langue=code_langue,
        libelle_langue=parcours.langue.libelle,
        cadre=cadre.value,
        niveaux_cadre=[code for code in ordre if code in niveauxouverts],
        niveau_depart=test.niveau_final.code if test.niveau_final is not None else None,
        niveau_vise=parcours.niveau_vise.code,
        lecon_atteinte=parcours.lecon_atteinte,
        phase=parcours.phase.value,
        est_lecon_de_revision=parcours.est_lecon_de_revision,
        modules=_modules(),
    )


def construire_exercice_out(ligne: ParcoursExercice) -> ExerciceParcoursOut:
    return ExerciceParcoursOut(
        id_parcours_exercice=ligne.id_parcours_exercice,
        id_exercice=ligne.id_exercice,
        numero_lecon=ligne.numero_lecon,
        type=ligne.exercice.type.value,
        difficulte=ligne.exercice.difficulte,
        intitule=ligne.exercice.intitule,
        statut=_statut_exercice(ligne.score_obtenu),
        score_obtenu=ligne.score_obtenu,
    )


def construire_lecon_out(parcours: Parcours, lecon, exercices: list[ParcoursExercice]) -> LeconParcoursOut:
    return LeconParcoursOut(
        numero_lecon=lecon.numero_lecon,
        titre=lecon.titre,
        texte_original=lecon.texte_original,
        est_lecon_de_revision=est_revision(lecon.numero_lecon),
        code_langue=parcours.langue.code,
        exercices=[
            ExerciceLeconOut(**construire_exercice_out(ligne).model_dump(), contenu=ligne.exercice.contenu)
            for ligne in exercices
        ],
    )


def corriger_exercice(
    db: Session, parcours: Parcours, ligne: ParcoursExercice, format_reponse: str, reponse: str
) -> CorrectionExerciceOut:
    """Corrige contre le corrigé privé et persiste le score, sans appel au service IA."""
    corrige = db.scalar(select(CorrigeExercice).where(CorrigeExercice.id_exercice == ligne.id_exercice))
    if corrige is None:
        ligne.score_obtenu = 0
        db.commit()
        return CorrectionExerciceOut(
            statut="A_REVOIR",
            score_obtenu=0,
            commentaire="Corrigé indisponible.",
            explication="Cet exercice ne peut pas être corrigé pour le moment.",
        )

    if format_reponse == "choix":
        normee = _normaliser(reponse)
        attendue = _normaliser(corrige.reponse_attendue)
        juste = bool(normee) and bool(attendue) and normee == attendue
        score = 100 if juste else 0
        commentaire = "Bonne réponse." if juste else "Réponse incorrecte."
        reponse_attendue = None if juste else corrige.reponse_attendue
        points_forts: list[str] = []
        erreurs: list[ErreurReleveeOut] = []
    else:
        tokens = set(_normaliser(reponse).split())
        mots_cles = corrige.mots_cles or []
        trouves = [mot for mot in mots_cles if all(token in tokens for token in _normaliser(mot).split())]
        manquants = [mot for mot in mots_cles if mot not in trouves]
        score = round(100 * len(trouves) / len(mots_cles)) if mots_cles else 0
        commentaire = f"{len(trouves)} élément(s) attendu(s) retrouvé(s) sur {len(mots_cles)} dans votre réponse."
        reponse_attendue = corrige.exemple_reponse
        points_forts = [f"Élément utilisé : {mot}." for mot in trouves]
        erreurs = [
            ErreurReleveeOut(
                extrait="Élément attendu",
                correction=mot,
                explication="Cet élément n'apparaît pas dans la réponse.",
            )
            for mot in manquants
        ]

    ligne.score_obtenu = score

    exercices_lecon = exercices_du_parcours(db, parcours, ligne.numero_lecon)
    lecon_terminee = bool(exercices_lecon) and all(
        item.score_obtenu is not None and item.score_obtenu >= 50 for item in exercices_lecon
    )
    if lecon_terminee:
        lecon_suivante = db.scalar(
            select(ParcoursExercice.numero_lecon)
            .where(
                ParcoursExercice.id_parcours == parcours.id_parcours,
                ParcoursExercice.numero_lecon > parcours.lecon_atteinte,
            )
            .order_by(ParcoursExercice.numero_lecon)
            .limit(1)
        )
        if lecon_suivante is not None:
            parcours.lecon_atteinte = lecon_suivante

    db.commit()
    return CorrectionExerciceOut(
        statut="REUSSI" if score >= 50 else "A_REVOIR",
        score_obtenu=score,
        commentaire=commentaire,
        reponse_attendue=reponse_attendue,
        explication=corrige.explication,
        points_forts=points_forts,
        erreurs=erreurs,
        conseil=corrige.conseil,
    )
