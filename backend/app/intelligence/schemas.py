from typing import Any
from pydantic import BaseModel, Field


class EducationEntry(BaseModel):
    degree: str
    institution: str
    graduation_year: int | None = None
    grade: str | None = None


class ProjectEntry(BaseModel):
    title: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    link: str | None = None


class ExperienceEntry(BaseModel):
    title: str
    company: str
    duration: str | None = None
    description: str | None = None
    type: str = "FULL_TIME"  # INTERNSHIP, FULL_TIME, CONTRACT, FREELANCE


class CandidateProfileOutput(BaseModel):
    candidate_name: str
    email: str | None = None
    experience_level: str = "FRESHER"  # FRESHER, ENTRY_LEVEL, MID, SENIOR
    experience_years: float = 0
    target_roles: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    work_experience: list[ExperienceEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    summary: str = ""




class JobEnrichmentOutput(BaseModel):
    standardized_title: str
    role_category: str
    seniority: str  # FRESHER, ENTRY_LEVEL, MID, SENIOR, LEAD
    min_experience_years: int | None = None
    max_experience_years: int | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    core_responsibilities: list[str] = Field(default_factory=list)
    requirements_summary: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    remote_policy_reasoning: str | None = None
