# CAMINHO: backend/app/profile_schemas.py

from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator


FarmingType = Literal["piscicultura", "carcinicultura"]

ESTADOS_BR = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
})


def _validate_uf(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    normalized = value.strip().upper()
    if normalized not in ESTADOS_BR:
        raise ValueError(f"Estado inválido: '{value}'. Use uma sigla de UF ou DF.")
    return normalized


def _validate_one_decimal(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    # exponent é a posição do menor dígito; -1 = uma casa decimal, 0 = inteiro
    if isinstance(exponent, int) and exponent < -1:
        raise ValueError("Produção anual deve ter no máximo uma casa decimal.")
    return value


# ── Requisição de upsert ────────────────────────────────────────────────────────

class ProfileUpsertRequest(BaseModel):
    # Obrigatórios
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=30)
    farming_type: FarmingType
    annual_production_tons: Decimal = Field(ge=0)

    # Opcionais — pessoais
    instagram: Optional[str] = Field(default=None, max_length=100)
    linkedin: Optional[str] = Field(default=None, max_length=200)

    # Opcionais — empresa/produção
    company_name: Optional[str] = Field(default=None, max_length=200)
    cnpj: Optional[str] = Field(default=None, max_length=18)
    contact_role: Optional[str] = Field(default=None, max_length=100)
    water_surface_area_ha: Optional[Decimal] = Field(default=None, ge=0)
    tank_count: Optional[int] = Field(default=None, ge=0)
    predominant_species: Optional[str] = Field(default=None, max_length=100)
    company_website: Optional[str] = Field(default=None, max_length=200)

    # Opcionais — endereço
    address_street: Optional[str] = Field(default=None, max_length=200)
    address_number: Optional[str] = Field(default=None, max_length=20)
    address_complement: Optional[str] = Field(default=None, max_length=100)
    address_zip_code: Optional[str] = Field(default=None, max_length=9)
    address_city: Optional[str] = Field(default=None, max_length=100)
    address_state: Optional[str] = Field(default=None)

    @field_validator("annual_production_tons")
    @classmethod
    def _check_one_decimal(cls, value: Decimal) -> Decimal:
        return _validate_one_decimal(value)

    @field_validator("address_state")
    @classmethod
    def _check_uf(cls, value: Optional[str]) -> Optional[str]:
        return _validate_uf(value)

    @field_validator(
        "instagram", "linkedin", "company_name", "cnpj", "contact_role",
        "predominant_species", "company_website", "address_street",
        "address_number", "address_complement", "address_zip_code", "address_city",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


# ── Resposta ─────────────────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    has_profile: bool
    email: str
    sequential_id: Optional[int] = None

    full_name: Optional[str] = None
    phone: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None

    company_name: Optional[str] = None
    cnpj: Optional[str] = None
    farming_type: Optional[FarmingType] = None
    annual_production_tons: Optional[Decimal] = None
    contact_role: Optional[str] = None
    water_surface_area_ha: Optional[Decimal] = None
    tank_count: Optional[int] = None
    predominant_species: Optional[str] = None
    company_website: Optional[str] = None

    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_zip_code: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
