"""Schémas publics du parcours personnalisé (contrat US41-US44)."""

from typing import Literal

from pydantic import BaseModel, Field

StatutParcoursText = Literal["EN_COURS", "TERMINE", "ABANDONNE"]
PhaseParcoursText = Literal["PASSIVE", "ACTIVE"]
TypeExerciceText = Literal["GRAMMAIRE", "VOCABULAIRE", "COMPREHENSION", "ECOUTE", "ORAL"]
StatutExerciceText = Literal["A_FAIRE", "REUSSI", "A_REVOIR"]


class ModuleParcoursOut(BaseModel):
    numero: int
    titre: str
    description: str
    premiere_lecon: int
    derniere_lecon: int


class ParcoursEnCoursOut(BaseModel):
    id_parcours: int
    statut: StatutParcoursText
    date_creation: str
    code_langue: str
    libelle_langue: str
    cadre: Literal["CECRL", "HSK"]
    niveaux_cadre: list[str]
    niveau_depart: str | None = None
    niveau_vise: str
    lecon_atteinte: int
    phase: PhaseParcoursText
    est_lecon_de_revision: bool
    modules: list[ModuleParcoursOut]


class ExerciceParcoursOut(BaseModel):
    id_parcours_exercice: int
    id_exercice: int
    numero_lecon: int
    type: TypeExerciceText
    difficulte: int = Field(ge=1, le=5)
    intitule: str | None = None
    statut: StatutExerciceText
    score_obtenu: int | None = None


class ExerciceLeconOut(ExerciceParcoursOut):
    contenu: str


class LeconParcoursOut(BaseModel):
    numero_lecon: int
    titre: str
    texte_original: str
    est_lecon_de_revision: bool
    code_langue: str
    exercices: list[ExerciceLeconOut]


class ReponseExerciceCreate(BaseModel):
    format: Literal["choix", "redaction"]
    reponse: str = Field(min_length=1)


class ErreurReleveeOut(BaseModel):
    extrait: str
    correction: str
    explication: str


class CorrectionExerciceOut(BaseModel):
    statut: Literal["REUSSI", "A_REVOIR"]
    score_obtenu: int = Field(ge=0, le=100)
    mode_correction: Literal["AUTOMATIQUE"] = "AUTOMATIQUE"
    commentaire: str
    reponse_attendue: str | None = None
    explication: str | None = None
    points_forts: list[str] = Field(default_factory=list)
    erreurs: list[ErreurReleveeOut] = Field(default_factory=list)
    conseil: str | None = None
