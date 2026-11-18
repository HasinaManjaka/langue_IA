"""Tests unitaires des règles de correction et de progression du parcours."""

import json

from sqlalchemy import select

from app.models import (
    CorrigeExercice,
    Exercice,
    Langue,
    Lecon,
    Niveau,
    Parcours,
    ParcoursExercice,
    StatutDiagnostic,
    StatutParcours,
    TypeExercice,
)
from app.models import (
    TestDiagnostic as ModeleTestDiagnostic,
)
from app.services.parcours import corriger_exercice
from tests.conftest import creer_utilisateur


def _parcours(
    db,
    lecons: dict[int, int],
    reponse_attendue: str = "a",
    with_corrige: bool = True,
    statut: StatutParcours = StatutParcours.EN_COURS,
) -> Parcours:
    apprenant = creer_utilisateur(db, email="apprenant-service@exemple.com")
    langue = db.scalar(select(Langue).where(Langue.code == "en"))
    niveau = db.scalar(select(Niveau).where(Niveau.code == "A1"))
    assert langue is not None and niveau is not None

    test = ModeleTestDiagnostic(
        apprenant=apprenant.apprenant,
        langue=langue,
        niveau=niveau,
        id_niveau_final=niveau.id_niveau,
        statut=StatutDiagnostic.TERMINE,
    )
    db.add(test)
    db.flush()
    parcours = Parcours(
        test_diagnostic=test,
        langue=langue,
        niveau_vise=niveau,
        statut=statut,
        lecon_atteinte=min(lecons),
    )
    db.add(parcours)
    db.flush()

    for numero, quantite in lecons.items():
        db.add(
            Lecon(
                parcours=parcours,
                numero_lecon=numero,
                titre=f"Leçon {numero}",
                texte_original="Original text.",
                niveau=niveau,
            )
        )
        for rang in range(quantite):
            exercice = Exercice(
                type=TypeExercice.GRAMMAIRE,
                contenu=json.dumps(
                    {"format": "choix", "consigne": "Choose.", "enonce": "Q ?", "choix": [reponse_attendue, "b"]}
                ),
                intitule=f"E{numero}-{rang}",
                difficulte=1,
                langue=langue,
                niveau=niveau,
            )
            db.add(exercice)
            db.flush()
            if with_corrige:
                db.add(
                    CorrigeExercice(
                        id_exercice=exercice.id_exercice,
                        reponse_attendue=reponse_attendue,
                        explication="Explication.",
                        mots_cles=[],
                        exemple_reponse=reponse_attendue,
                    )
                )
            db.flush()
            db.add(
                ParcoursExercice(
                    id_parcours=parcours.id_parcours,
                    id_exercice=exercice.id_exercice,
                    numero_lecon=numero,
                )
            )
    db.commit()
    db.refresh(parcours)
    return parcours


def _ligne(db, parcours: Parcours, numero_lecon: int) -> ParcoursExercice:
    ligne = db.scalar(
        select(ParcoursExercice).where(
            ParcoursExercice.id_parcours == parcours.id_parcours,
            ParcoursExercice.numero_lecon == numero_lecon,
        )
    )
    assert ligne is not None
    return ligne


def test_la_progression_attend_un_score_suffisant_et_saute_a_la_lecon_existante(db) -> None:
    parcours = _parcours(db, {1: 1, 5: 1})
    ligne = _ligne(db, parcours, 1)

    faux = corriger_exercice(db, parcours, ligne, "choix", "b")
    db.refresh(parcours)
    assert faux.score_obtenu == 0
    assert parcours.lecon_atteinte == 1

    juste = corriger_exercice(db, parcours, ligne, "choix", "a")
    db.refresh(parcours)
    assert juste.score_obtenu == 100
    assert parcours.lecon_atteinte == 5


def test_repondre_a_une_ancienne_lecon_ne_reculle_ni_n_avance_le_parcours(db) -> None:
    parcours = _parcours(db, {1: 1, 5: 1})
    parcours.lecon_atteinte = 5
    db.commit()
    ligne = _ligne(db, parcours, 1)

    correction = corriger_exercice(db, parcours, ligne, "choix", "a")
    db.refresh(parcours)

    assert correction.score_obtenu == 100
    assert parcours.lecon_atteinte == 5


def test_normalisation_unicode_distinguie_les_reponses_chinoises(db) -> None:
    parcours = _parcours(db, {1: 1}, reponse_attendue="北京")
    ligne = _ligne(db, parcours, 1)

    faux = corriger_exercice(db, parcours, ligne, "choix", "上海")
    juste = corriger_exercice(db, parcours, ligne, "choix", "北京")

    assert faux.score_obtenu == 0
    assert juste.score_obtenu == 100


def test_chaine_vide_ou_ponctuation_ne_vaut_pas_bonne_reponse(db) -> None:
    parcours = _parcours(db, {1: 1})
    ligne = _ligne(db, parcours, 1)

    correction = corriger_exercice(db, parcours, ligne, "choix", "???")

    assert correction.score_obtenu == 0
    assert correction.reponse_attendue == "a"


def test_exercice_sans_corrige_est_franchement_indisponible(db) -> None:
    parcours = _parcours(db, {1: 1}, with_corrige=False)
    ligne = _ligne(db, parcours, 1)

    correction = corriger_exercice(db, parcours, ligne, "choix", "???")

    assert correction.score_obtenu == 0
    assert correction.statut == "A_REVOIR"
    assert "indisponible" in correction.commentaire.lower()
