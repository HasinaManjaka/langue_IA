"""Tests des contraintes PostgreSQL des parcours et exercices."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CorrigeExercice,
    Exercice,
    Langue,
    Lecon,
    Niveau,
    Parcours,
    ParcoursExercice,
    TypeExercice,
)
from app.models import TestDiagnostic as Diagnostic
from tests.conftest import creer_utilisateur


def _creer_parcours_et_exercice(db: Session) -> tuple[Parcours, Exercice]:
    apprenant = creer_utilisateur(db)
    langue = db.scalar(select(Langue).where(Langue.code == "en"))
    niveau = db.scalar(select(Niveau).where(Niveau.code == "A1"))
    assert langue is not None
    assert niveau is not None
    test_diagnostic = Diagnostic(apprenant=apprenant.apprenant, langue=langue, niveau=niveau)
    db.add(test_diagnostic)
    db.flush()
    parcours = Parcours(test_diagnostic=test_diagnostic, langue=langue, niveau_vise=niveau)
    exercice = Exercice(
        type=TypeExercice.GRAMMAIRE,
        contenu="Choose a verb.",
        difficulte=1,
        langue=langue,
        niveau=niveau,
    )
    db.add_all([parcours, exercice])
    db.commit()
    return parcours, exercice


@pytest.mark.parametrize("lecon_atteinte", [0, -1])
def test_refuse_une_lecon_atteinte_inferieure_a_un(db: Session, lecon_atteinte: int) -> None:
    parcours, _ = _creer_parcours_et_exercice(db)
    parcours.lecon_atteinte = lecon_atteinte
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refuse_une_difficulte_superieure_a_cinq(db: Session) -> None:
    _, exercice = _creer_parcours_et_exercice(db)
    exercice.difficulte = 6
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refuse_un_score_superieur_a_cent(db: Session) -> None:
    parcours, exercice = _creer_parcours_et_exercice(db)
    db.add(ParcoursExercice(parcours=parcours, exercice=exercice, numero_lecon=1, score_obtenu=101))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refuse_un_doublon_parcours_lecon_exercice(db: Session) -> None:
    parcours, exercice = _creer_parcours_et_exercice(db)
    db.add_all(
        [
            ParcoursExercice(parcours=parcours, exercice=exercice, numero_lecon=1),
            ParcoursExercice(parcours=parcours, exercice=exercice, numero_lecon=1),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refuse_plusieurs_parcours_pour_un_test_diagnostic(db: Session) -> None:
    parcours, _ = _creer_parcours_et_exercice(db)
    second_parcours = Parcours(
        id_test=parcours.id_test,
        id_langue=parcours.id_langue,
        id_niveau_vise=parcours.id_niveau_vise,
    )
    db.add(second_parcours)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def _creer_lecon(db: Session, parcours: Parcours, numero: int = 12) -> Lecon:
    niveau = db.scalar(select(Niveau).where(Niveau.code == "A1"))
    assert niveau is not None
    lecon = Lecon(
        parcours=parcours,
        numero_lecon=numero,
        titre="At the Language Centre",
        texte_original="Mina works at a language centre.",
        niveau=niveau,
    )
    db.add(lecon)
    db.commit()
    return lecon


def test_refuse_un_numero_de_lecon_nul(db: Session) -> None:
    parcours, _ = _creer_parcours_et_exercice(db)
    lecon = _creer_lecon(db, parcours)
    lecon.numero_lecon = 0
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_refuse_deux_lecons_du_meme_numero_dans_un_parcours(db: Session) -> None:
    parcours, _ = _creer_parcours_et_exercice(db)
    _creer_lecon(db, parcours)
    with pytest.raises(IntegrityError):
        _creer_lecon(db, parcours)
    db.rollback()


def test_refuse_deux_corriges_pour_un_exercice(db: Session) -> None:
    _, exercice = _creer_parcours_et_exercice(db)
    db.add(
        CorrigeExercice(
            exercice=exercice,
            reponse_attendue="studies",
            explication="Present simple with she.",
            mots_cles=[],
            exemple_reponse="studies",
        )
    )
    db.commit()
    db.add(
        CorrigeExercice(
            id_exercice=exercice.id_exercice,
            reponse_attendue="studies",
            explication="Doublon.",
            mots_cles=[],
            exemple_reponse="studies",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
