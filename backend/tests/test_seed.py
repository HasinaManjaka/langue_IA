"""Script de seed (PRE-07) : une base neuve doit permettre de dérouler la chaîne complète en local.

Le seed est relancé à chaque démarrage du conteneur : il doit être idempotent et ne charger les données de
démonstration (comptes, banque de questions) que si SEED_DEMO=true.
"""

import pytest
from sqlalchemy import func, select

from app import seed
from app.models import (
    CorrigeExercice,
    Exercice,
    Formule,
    Langue,
    Lecon,
    Niveau,
    Parcours,
    ParcoursExercice,
    Question,
    StatutDiagnostic,
    Utilisateur,
)
from app.models import (
    TestDiagnostic as ModeleTestDiagnostic,
)
from app.seed_diagnostic import QUESTIONS_DEMO, charger_questions_demo
from app.seed_us156 import EMAIL_APPRENANT_DEMO, EXERCICES, charger_contenu_demo_us156
from tests.conftest import creer_utilisateur


def _compter(db, modele) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modele))


class TestSeed:
    def test_sans_seed_demo_seul_le_referentiel_est_charge(self, db, monkeypatch):
        monkeypatch.setenv("SEED_DEMO", "false")

        seed.main()

        assert _compter(db, Langue) == len(seed.LANGUES)
        assert _compter(db, Formule) == len(seed.FORMULES)
        assert _compter(db, Utilisateur) == 0
        assert _compter(db, Question) == 0

    def test_seed_demo_charge_comptes_et_questions_sans_doublon(self, db, monkeypatch):
        monkeypatch.setenv("SEED_DEMO", "true")

        seed.main()
        premier = (_compter(db, Utilisateur), _compter(db, Question), _compter(db, Niveau))
        seed.main()  # second démarrage du conteneur

        assert premier == (_compter(db, Utilisateur), _compter(db, Question), _compter(db, Niveau))
        assert premier[0] == len(seed.COMPTES_DEMO)
        assert premier[1] == sum(len(questions) for questions in QUESTIONS_DEMO.values())

    def test_une_question_deja_presente_n_est_pas_recreee(self, db):
        assert charger_questions_demo(db) > 0
        assert charger_questions_demo(db) == 0

    def test_contenu_us156_est_rejouable(self, db, monkeypatch):
        monkeypatch.setenv("SEED_DEMO", "true")

        seed.main()
        modeles = (Lecon, Exercice, CorrigeExercice, ParcoursExercice, Parcours, ModeleTestDiagnostic)
        premier = tuple(_compter(db, modele) for modele in modeles)
        seed.main()

        assert premier == tuple(_compter(db, modele) for modele in modeles)
        assert premier[0] == 2
        assert premier[1] == 12
        assert premier[2] == 12

    def test_seed_attache_le_parcours_au_diagnostic_le_plus_recent(self, db):
        apprenant = creer_utilisateur(db, email=EMAIL_APPRENANT_DEMO)
        langue = db.scalar(select(Langue).where(Langue.code == "en"))
        niveau = db.scalar(select(Niveau).where(Niveau.code == "A1"))
        assert langue is not None and niveau is not None
        for _ in range(2):
            db.add(
                ModeleTestDiagnostic(
                    apprenant=apprenant.apprenant,
                    langue=langue,
                    niveau=niveau,
                    id_niveau_final=niveau.id_niveau,
                    statut=StatutDiagnostic.TERMINE,
                )
            )
        db.commit()
        diagnostics = db.scalars(
            select(ModeleTestDiagnostic)
            .where(ModeleTestDiagnostic.id_apprenant == apprenant.id_user)
            .order_by(ModeleTestDiagnostic.id_test)
        ).all()
        recent = diagnostics[-1]

        charger_contenu_demo_us156(db)

        parcours = db.scalar(select(Parcours))
        assert parcours is not None
        assert parcours.id_test == recent.id_test

    def test_seed_met_a_jour_un_exercice_deja_present(self, db, monkeypatch):
        monkeypatch.setenv("SEED_DEMO", "true")
        seed.main()
        exercice = db.scalar(select(Exercice))
        assert exercice is not None
        exercice.intitule = "Ancien intitulé"
        exercice.difficulte = 5
        db.commit()

        seed.main()
        db.refresh(exercice)

        assert exercice.intitule == EXERCICES[0]["intitule"]
        assert exercice.difficulte == EXERCICES[0]["difficulte"]


class TestBanqueDeQuestions:
    @pytest.mark.parametrize("code_langue", sorted(QUESTIONS_DEMO))
    def test_chaque_niveau_cecrl_a_au_moins_deux_questions(self, code_langue):
        niveaux = [question.niveau for question in QUESTIONS_DEMO[code_langue]]

        for code_niveau, _ in seed.CECRL:
            assert niveaux.count(code_niveau) >= 2, f"{code_langue} {code_niveau}"

    @pytest.mark.parametrize("code_langue", sorted(QUESTIONS_DEMO))
    def test_les_questions_sont_corrigeables_par_le_scoring(self, code_langue):
        for question in QUESTIONS_DEMO[code_langue]:
            assert 0 <= question.bonne_reponse < len(question.choix), question.enonce
            assert len(set(question.choix)) == len(question.choix), question.enonce


class TestParcoursDeDemonstration:
    """Ce que fait un membre de l'équipe après `make up` : connexion du compte apprenant puis test complet."""

    def test_l_apprenant_demo_passe_le_diagnostic_d_anglais(self, client, monkeypatch):
        monkeypatch.setenv("SEED_DEMO", "true")
        seed.main()

        connexion = client.post(
            "/api/v1/auth/login",
            json={"email": "apprenant@digitheque.mg", "mot_de_passe": seed.MOT_DE_PASSE_DEMO},
        )
        assert connexion.status_code == 200, connexion.text
        entete = {"Authorization": f"Bearer {connexion.json()['access_token']}"}

        tentative = client.post("/api/v1/diagnostic/tentatives", headers=entete, json={"code_langue": "en"})
        assert tentative.status_code == 201, tentative.text
        tentative = tentative.json()
        questions = client.get(
            "/api/v1/diagnostic/questions",
            headers=entete,
            params={"code_langue": "en", "code_niveau": tentative["code_niveau"]},
        ).json()
        assert questions

        bonnes = {
            demo.enonce: demo.choix[demo.bonne_reponse]
            for demo in QUESTIONS_DEMO["en"]
            if demo.niveau == tentative["code_niveau"]
        }
        for question in questions:
            reponse = client.post(
                "/api/v1/diagnostic/reponse",
                headers=entete,
                json={
                    "id_tentative": tentative["id_tentative"],
                    "id_question": question["id_question"],
                    "reponse_fournie": bonnes[question["enonce"]],
                },
            )
            assert reponse.status_code == 201, reponse.text

        resultat = client.post(f"/api/v1/diagnostic/tentatives/{tentative['id_tentative']}/terminer", headers=entete)
        assert resultat.status_code == 200, resultat.text
        assert resultat.json()["percentage"] == 100
