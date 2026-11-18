"""Contenu de démonstration original (anglais) de l'US156 et son chargement idempotent.

Les textes sont écrits pour le projet : aucune reproduction de support Assimil.
Les corrigés restent privés dans ``corrige_exercice`` et ne sont jamais placés dans
le JSON public de ``exercice.contenu`` (règle US43-BE).
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Apprenant,
    CorrigeExercice,
    Exercice,
    Langue,
    Lecon,
    Niveau,
    Parcours,
    ParcoursExercice,
    StatutDiagnostic,
    StatutParcours,
    TestDiagnostic,
    TypeExercice,
    Utilisateur,
)

EMAIL_APPRENANT_DEMO = "apprenant@digitheque.mg"
CODE_LANGUE = "en"
LECON_ATTEINTE_DEMO = 50

LECONS = [
    {
        "numero": 12,
        "code_niveau": "A1",
        "titre": "At the Language Centre",
        "texte_original": (
            "Mina works at a language centre in the city. She arrives at eight fifteen every morning. "
            "The first class starts at nine o'clock. Five rooms are on the second floor. "
            "Mina studies English every Tuesday because she wants to help new students. "
            "Her friend Rova usually reads the timetable before the lesson. They drink tea after class."
        ),
    },
    {
        "numero": 50,
        "code_niveau": "A2",
        "titre": "A Saturday in the Old Town",
        "texte_original": (
            "Last Saturday, Lina visited the old town with two friends. They went to the market first "
            "and bought some fresh fruit. Lina bought a new notebook before the walk. "
            "In the afternoon, they tried local food near the river. The weather was cold, so they "
            "decided to drink hot chocolate. Next month, they will visit the gallery if it rains. "
            "Lina says that every trip is a good way to practise a language."
        ),
    },
]

EXERCICES = [
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.VOCABULAIRE,
        "difficulte": 1,
        "intitule": "Where does Mina work?",
        "contenu": {
            "format": "choix",
            "consigne": "Read the text and choose the correct answer.",
            "enonce": "Where does Mina work?",
            "choix": ["At a language centre", "At a hospital", "At a railway station"],
        },
        "corrige": {
            "reponse_attendue": "At a language centre",
            "explication": "The first sentence says that Mina works at a language centre.",
            "mots_cles": [],
            "exemple_reponse": "At a language centre",
            "conseil": "Look for the place named in the first sentence.",
        },
    },
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 1,
        "intitule": "The present simple of 'study'",
        "contenu": {
            "format": "choix",
            "consigne": "Choose the correct form of the verb.",
            "enonce": "Mina ___ English every Tuesday.",
            "choix": ["study", "studies", "studying"],
        },
        "corrige": {
            "reponse_attendue": "studies",
            "explication": "With 'she' in the present simple, the verb takes -es after a consonant + y: studies.",
            "mots_cles": [],
            "exemple_reponse": "studies",
            "conseil": "Remember: he, she, it → the verb usually ends in -s.",
        },
    },
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.COMPREHENSION,
        "difficulte": 2,
        "intitule": "The first class",
        "contenu": {
            "format": "choix",
            "consigne": "Read the text and choose the correct answer.",
            "enonce": "What time does the first class start?",
            "choix": ["8:15", "9:00", "10:15"],
        },
        "corrige": {
            "reponse_attendue": "9:00",
            "explication": "The text says: 'The first class starts at nine o'clock.' 8:15 is her arrival time.",
            "mots_cles": [],
            "exemple_reponse": "9:00",
            "conseil": "Do not confuse the arrival time with the class time.",
        },
    },
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 1,
        "intitule": "There is / there are",
        "contenu": {
            "format": "choix",
            "consigne": "Choose the correct form.",
            "enonce": "There ___ five rooms on the second floor.",
            "choix": ["is", "are", "have"],
        },
        "corrige": {
            "reponse_attendue": "are",
            "explication": "'Five rooms' is plural, so the correct form is 'there are'.",
            "mots_cles": [],
            "exemple_reponse": "are",
            "conseil": "Look at the noun after 'there': singular → is, plural → are.",
        },
    },
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 2,
        "intitule": "My morning",
        "contenu": {
            "format": "redaction",
            "consigne": ("Write at least three sentences about your morning. Use 'I usually' and one time expression."),
            "enonce": "What do you usually do in the morning?",
            "mots_minimum": 20,
        },
        "corrige": {
            "reponse_attendue": ("I usually get up at seven o'clock. I drink coffee and read the news before class."),
            "explication": (
                "A good answer uses the present simple with 'I usually' and gives at least one precise time."
            ),
            "mots_cles": ["usually", "morning", "o'clock"],
            "exemple_reponse": (
                "I usually get up at seven o'clock. I drink coffee and read the news before class. "
                "Then I walk to the language centre."
            ),
            "conseil": "Add a time expression such as 'at seven o'clock' or 'before breakfast'.",
        },
    },
    {
        "numero_lecon": 12,
        "code_niveau": "A1",
        "type": TypeExercice.VOCABULAIRE,
        "difficulte": 2,
        "intitule": "My language class",
        "contenu": {
            "format": "redaction",
            "consigne": (
                "Write at least three sentences about your language class. Say when it starts and what you do."
            ),
            "enonce": "Describe one of your classes in English.",
            "mots_minimum": 20,
        },
        "corrige": {
            "reponse_attendue": (
                "My English class starts at nine o'clock. We read a short text and practise new words."
            ),
            "explication": "The answer should name the class, give a starting time and describe one activity.",
            "mots_cles": ["class", "start", "practice"],
            "exemple_reponse": (
                "My English class starts at nine o'clock. We read a short text and practise new words. "
                "I like the speaking exercise at the end."
            ),
            "conseil": "Use 'starts at' for the time and 'we practise' for the activity.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.COMPREHENSION,
        "difficulte": 2,
        "intitule": "Where did Lina go?",
        "contenu": {
            "format": "choix",
            "consigne": "Read the text and choose the correct answer.",
            "enonce": "Where did Lina go first on Saturday?",
            "choix": ["To the museum", "To the market", "To the beach"],
        },
        "corrige": {
            "reponse_attendue": "To the market",
            "explication": "The text says: 'They went to the market first.'",
            "mots_cles": [],
            "exemple_reponse": "To the market",
            "conseil": "Pay attention to the word 'first'.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 2,
        "intitule": "The past simple of 'buy'",
        "contenu": {
            "format": "choix",
            "consigne": "Choose the correct form of the verb.",
            "enonce": "Lina ___ a new notebook before the walk.",
            "choix": ["buy", "bought", "buyed"],
        },
        "corrige": {
            "reponse_attendue": "bought",
            "explication": "'Buy' is an irregular verb: the past simple is 'bought'.",
            "mots_cles": [],
            "exemple_reponse": "bought",
            "conseil": "Learn irregular verbs in three forms: buy – bought – bought.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.VOCABULAIRE,
        "difficulte": 2,
        "intitule": "To try local food",
        "contenu": {
            "format": "choix",
            "consigne": "Choose the closest meaning.",
            "enonce": "What does 'to try local food' mean?",
            "choix": ["To cook at home", "To taste dishes from the region", "To buy souvenirs"],
        },
        "corrige": {
            "reponse_attendue": "To taste dishes from the region",
            "explication": "'To try' here means 'to taste', and 'local' means 'from the region'.",
            "mots_cles": [],
            "exemple_reponse": "To taste dishes from the region",
            "conseil": "Use context: the friends are in the old town, near the river.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 3,
        "intitule": "A simple future plan",
        "contenu": {
            "format": "choix",
            "consigne": "Choose the correct form to complete the plan.",
            "enonce": "They ___ visit the gallery if it rains.",
            "choix": ["will", "did", "are"],
        },
        "corrige": {
            "reponse_attendue": "will",
            "explication": "A future plan uses 'will + verb'. The same form appears in the last part of the text.",
            "mots_cles": [],
            "exemple_reponse": "will",
            "conseil": "For a decision about the future, use 'will' + infinitive.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 3,
        "intitule": "My last weekend",
        "contenu": {
            "format": "redaction",
            "consigne": "Write at least four sentences about your last weekend. Use the past simple.",
            "enonce": "What did you do last weekend?",
            "mots_minimum": 30,
        },
        "corrige": {
            "reponse_attendue": (
                "Last weekend I went to the market with a friend. We visited a small gallery and had coffee."
            ),
            "explication": "A good answer uses past simple verbs and mentions at least one place and one activity.",
            "mots_cles": ["weekend", "went", "visited", "had"],
            "exemple_reponse": (
                "Last weekend I went to the market with a friend. We visited a small gallery and had coffee "
                "near the river. The weather was nice, so we walked home."
            ),
            "conseil": "Check the past forms of irregular verbs: go → went, have → had.",
        },
    },
    {
        "numero_lecon": 50,
        "code_niveau": "A2",
        "type": TypeExercice.GRAMMAIRE,
        "difficulte": 3,
        "intitule": "A place to visit",
        "contenu": {
            "format": "redaction",
            "consigne": (
                "Write at least four sentences about a place you would like to visit next month. "
                "Say what you will do there and why."
            ),
            "enonce": "Which place would you like to visit next month?",
            "mots_minimum": 30,
        },
        "corrige": {
            "reponse_attendue": (
                "Next month I will visit the gallery because I like modern art. I will walk there with my class."
            ),
            "explication": (
                "The answer should name a place, use 'will' for the future and give a reason with 'because'."
            ),
            "mots_cles": ["visit", "will", "because"],
            "exemple_reponse": (
                "Next month I will visit the gallery because I like modern art. I will walk there with my class "
                "and take notes for a short presentation."
            ),
            "conseil": "Link your ideas with 'because' to make your answer clearer.",
        },
    },
]


def charger_contenu_demo_us156(db: Session) -> int:
    """Charge les leçons, exercices et corrigés US156 sans jamais créer de doublon.

    Retourne le nombre de lignes ajoutées (leçons, exercices, corrigés, liaisons).
    """
    apprenant = db.scalar(select(Apprenant).join(Utilisateur).where(Utilisateur.email == EMAIL_APPRENANT_DEMO))
    langue = db.scalar(select(Langue).where(Langue.code == CODE_LANGUE))
    if apprenant is None or langue is None:
        return 0

    niveaux = {niveau.code: niveau for niveau in db.scalars(select(Niveau))}
    niveau_a1 = niveaux.get("A1")
    niveau_a2 = niveaux.get("A2")
    if niveau_a1 is None or niveau_a2 is None:
        return 0

    test = db.scalar(
        select(TestDiagnostic)
        .where(
            TestDiagnostic.id_apprenant == apprenant.id_user,
            TestDiagnostic.id_langue == langue.id_langue,
            TestDiagnostic.statut == StatutDiagnostic.TERMINE,
        )
        .order_by(TestDiagnostic.id_test.desc())
    )
    if test is None:
        test = TestDiagnostic(
            id_apprenant=apprenant.id_user,
            id_langue=langue.id_langue,
            id_niveau=niveau_a1.id_niveau,
            id_niveau_final=niveau_a2.id_niveau,
            statut=StatutDiagnostic.TERMINE,
            date_fin=datetime.now(UTC),
            score=Decimal("50.00"),
        )
        db.add(test)
        db.flush()
    elif test.id_niveau_final is None:
        test.id_niveau_final = niveau_a2.id_niveau
        test.score = Decimal("50.00")
        test.date_fin = datetime.now(UTC)

    parcours = db.scalar(select(Parcours).where(Parcours.id_test == test.id_test))
    if parcours is None:
        parcours = Parcours(
            id_test=test.id_test,
            id_langue=langue.id_langue,
            id_niveau_vise=niveau_a2.id_niveau,
            statut=StatutParcours.EN_COURS,
            lecon_atteinte=LECON_ATTEINTE_DEMO,
        )
        db.add(parcours)
        db.flush()

    cree = 0
    for donnees in LECONS:
        numero = donnees["numero"]
        if (
            db.scalar(select(Lecon).where(Lecon.id_parcours == parcours.id_parcours, Lecon.numero_lecon == numero))
            is not None
        ):
            continue
        niveau = niveaux[donnees["code_niveau"]]
        db.add(
            Lecon(
                id_parcours=parcours.id_parcours,
                numero_lecon=numero,
                titre=donnees["titre"],
                texte_original=donnees["texte_original"],
                id_niveau=niveau.id_niveau,
            )
        )
        cree += 1
    db.flush()

    for donnees in EXERCICES:
        contenu = json.dumps(donnees["contenu"], ensure_ascii=False, sort_keys=True)
        niveau = niveaux[donnees["code_niveau"]]
        exercice = db.scalar(
            select(Exercice).where(
                Exercice.type == donnees["type"],
                Exercice.id_langue == langue.id_langue,
                Exercice.id_niveau == niveau.id_niveau,
                Exercice.contenu == contenu,
            )
        )
        if exercice is None:
            exercice = Exercice(
                type=donnees["type"],
                contenu=contenu,
                intitule=donnees["intitule"],
                difficulte=donnees["difficulte"],
                id_langue=langue.id_langue,
                id_niveau=niveau.id_niveau,
            )
            db.add(exercice)
            db.flush()
            cree += 1
        else:
            exercice.intitule = donnees["intitule"]
            exercice.difficulte = donnees["difficulte"]

        if db.scalar(select(CorrigeExercice).where(CorrigeExercice.id_exercice == exercice.id_exercice)) is None:
            corrige = donnees["corrige"]
            db.add(
                CorrigeExercice(
                    id_exercice=exercice.id_exercice,
                    reponse_attendue=corrige["reponse_attendue"],
                    explication=corrige["explication"],
                    mots_cles=corrige["mots_cles"],
                    exemple_reponse=corrige["exemple_reponse"],
                    conseil=corrige["conseil"],
                )
            )
            cree += 1

        numero_lecon = donnees["numero_lecon"]
        if (
            db.scalar(
                select(ParcoursExercice).where(
                    ParcoursExercice.id_parcours == parcours.id_parcours,
                    ParcoursExercice.numero_lecon == numero_lecon,
                    ParcoursExercice.id_exercice == exercice.id_exercice,
                )
            )
            is None
        ):
            db.add(
                ParcoursExercice(
                    id_parcours=parcours.id_parcours,
                    id_exercice=exercice.id_exercice,
                    numero_lecon=numero_lecon,
                )
            )
            cree += 1

    db.commit()
    return cree
