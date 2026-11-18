"""Tests des routes du parcours de démonstration US156."""

import json

from sqlalchemy import select

from app.models import Exercice, Role, StatutParcours
from app.seed_us156 import charger_contenu_demo_us156
from app.services.parcours import parcours_en_cours
from tests.conftest import creer_utilisateur, entete

BASE = "/api/v1/parcours"


def _installer_demo(db, apprenant_email: str = "apprenant@digitheque.mg"):
    apprenant = creer_utilisateur(db, email=apprenant_email, prenom="Rova", nom="RAKOTO")
    charger_contenu_demo_us156(db)
    parcours = parcours_en_cours(db, apprenant.id_user)
    assert parcours is not None
    db.refresh(parcours)
    return apprenant, parcours, entete(apprenant)


def test_parcours_en_cours_expose_les_modules_et_la_phase(db, client):
    _, parcours, headers = _installer_demo(db)

    reponse = client.get(f"{BASE}/en-cours", headers=headers)

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["id_parcours"] == parcours.id_parcours
    assert donnees["code_langue"] == "en"
    assert donnees["niveau_vise"] == "A2"
    assert donnees["lecon_atteinte"] == 50
    assert donnees["phase"] == "ACTIVE"
    assert len(donnees["modules"]) == 8
    assert donnees["modules"][1]["premiere_lecon"] == 8
    assert donnees["modules"][7]["derniere_lecon"] == 56


def test_lecon_publique_ne_contient_aucun_corrige(db, client):
    _, parcours, headers = _installer_demo(db)

    reponse = client.get(f"{BASE}/{parcours.id_parcours}/lecons/12", headers=headers)

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["titre"] == "At the Language Centre"
    assert "Mina works at a language centre" in donnees["texte_original"]
    assert len(donnees["exercices"]) == 6
    for exercice in donnees["exercices"]:
        contenu = json.loads(exercice["contenu"])
        assert "reponse_attendue" not in contenu
        assert "mots_cles" not in contenu


def test_lecon_non_atteinte_est_refusee(db, client):
    _, parcours, headers = _installer_demo(db)
    parcours.lecon_atteinte = 12
    db.commit()

    reponse = client.get(f"{BASE}/{parcours.id_parcours}/lecons/50", headers=headers)

    assert reponse.status_code == 403


def test_correction_qcm_et_persistance(db, client):
    _, parcours, headers = _installer_demo(db)
    lecon = client.get(f"{BASE}/{parcours.id_parcours}/lecons/12", headers=headers).json()
    qcm = next(e for e in lecon["exercices"] if json.loads(e["contenu"])["format"] == "choix")

    juste = client.post(
        f"{BASE}/{parcours.id_parcours}/exercices/{qcm['id_parcours_exercice']}/reponse",
        json={"format": "choix", "reponse": "At a language centre"},
        headers=headers,
    )
    assert juste.status_code == 200
    assert juste.json()["score_obtenu"] == 100
    assert juste.json()["statut"] == "REUSSI"
    assert juste.json()["reponse_attendue"] is None

    faux = client.post(
        f"{BASE}/{parcours.id_parcours}/exercices/{qcm['id_parcours_exercice']}/reponse",
        json={"format": "choix", "reponse": "At a hospital"},
        headers=headers,
    )
    assert faux.status_code == 200
    assert faux.json()["score_obtenu"] == 0
    assert faux.json()["reponse_attendue"] == "At a language centre"

    apres = client.get(f"{BASE}/{parcours.id_parcours}/exercices", headers=headers).json()
    assert next(e for e in apres if e["id_parcours_exercice"] == qcm["id_parcours_exercice"])["score_obtenu"] == 0


def test_correction_redaction_par_mots_cles(db, client):
    _, parcours, headers = _installer_demo(db)
    lecon = client.get(f"{BASE}/{parcours.id_parcours}/lecons/12", headers=headers).json()
    redaction = next(e for e in lecon["exercices"] if json.loads(e["contenu"])["format"] == "redaction")

    reponse = client.post(
        f"{BASE}/{parcours.id_parcours}/exercices/{redaction['id_parcours_exercice']}/reponse",
        json={
            "format": "redaction",
            "reponse": "I usually read the news in the morning at seven o'clock.",
        },
        headers=headers,
    )

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["mode_correction"] == "AUTOMATIQUE"
    assert donnees["score_obtenu"] == 100
    assert "seven o'clock" in donnees["reponse_attendue"].lower()
    assert not donnees["erreurs"]


def test_parcours_dun_autre_apprenant_est_invisible(db, client):
    _, parcours, _ = _installer_demo(db)
    autre = creer_utilisateur(db, email="autre@exemple.com")
    headers = entete(autre)

    assert client.get(f"{BASE}/en-cours", headers=headers).status_code == 404
    assert client.get(f"{BASE}/{parcours.id_parcours}/exercices", headers=headers).status_code == 404


def test_admin_ne_peut_pas_acceder_aux_parcours(db, client):
    _, parcours, _ = _installer_demo(db)
    admin = creer_utilisateur(db, role=Role.ADMINISTRATEUR, email="admin@exemple.com")
    headers = entete(admin)

    assert client.get(f"{BASE}/en-cours", headers=headers).status_code == 403
    assert client.get(f"{BASE}/{parcours.id_parcours}/exercices", headers=headers).status_code == 403


def _premier_qcm(db, client, parcours, headers):
    lecon = client.get(f"{BASE}/{parcours.id_parcours}/lecons/12", headers=headers).json()
    return next(e for e in lecon["exercices"] if json.loads(e["contenu"])["format"] == "choix")


def test_reponse_refusee_sur_un_parcours_termine(db, client):
    _, parcours, headers = _installer_demo(db)
    parcours.statut = StatutParcours.TERMINE
    db.commit()
    qcm = _premier_qcm(db, client, parcours, headers)

    reponse = client.post(
        f"{BASE}/{parcours.id_parcours}/exercices/{qcm['id_parcours_exercice']}/reponse",
        json={"format": "choix", "reponse": "At a language centre"},
        headers=headers,
    )

    assert reponse.status_code == 409


def test_contenu_json_invalide_donne_422_plutot_qu_une_erreur_500(db, client):
    _, parcours, headers = _installer_demo(db)
    qcm = _premier_qcm(db, client, parcours, headers)
    exercice = db.scalar(select(Exercice).where(Exercice.id_exercice == qcm["id_exercice"]))
    assert exercice is not None
    exercice.contenu = "plain text"
    db.commit()

    reponse = client.post(
        f"{BASE}/{parcours.id_parcours}/exercices/{qcm['id_parcours_exercice']}/reponse",
        json={"format": "choix", "reponse": "At a language centre"},
        headers=headers,
    )

    assert reponse.status_code == 422
