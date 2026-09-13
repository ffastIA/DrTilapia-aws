// CAMINHO: frontend/types/profile.ts

export type FarmingType = 'piscicultura' | 'carcinicultura';

export const FARMING_TYPE_OPTIONS: { value: FarmingType; label: string }[] = [
  { value: 'piscicultura', label: 'Piscicultura' },
  { value: 'carcinicultura', label: 'Carcinicultura' },
];

export const ESTADOS_BR: { value: string; label: string }[] = [
  { value: 'AC', label: 'Acre' },
  { value: 'AL', label: 'Alagoas' },
  { value: 'AP', label: 'Amapá' },
  { value: 'AM', label: 'Amazonas' },
  { value: 'BA', label: 'Bahia' },
  { value: 'CE', label: 'Ceará' },
  { value: 'DF', label: 'Distrito Federal' },
  { value: 'ES', label: 'Espírito Santo' },
  { value: 'GO', label: 'Goiás' },
  { value: 'MA', label: 'Maranhão' },
  { value: 'MT', label: 'Mato Grosso' },
  { value: 'MS', label: 'Mato Grosso do Sul' },
  { value: 'MG', label: 'Minas Gerais' },
  { value: 'PA', label: 'Pará' },
  { value: 'PB', label: 'Paraíba' },
  { value: 'PR', label: 'Paraná' },
  { value: 'PE', label: 'Pernambuco' },
  { value: 'PI', label: 'Piauí' },
  { value: 'RJ', label: 'Rio de Janeiro' },
  { value: 'RN', label: 'Rio Grande do Norte' },
  { value: 'RS', label: 'Rio Grande do Sul' },
  { value: 'RO', label: 'Rondônia' },
  { value: 'RR', label: 'Roraima' },
  { value: 'SC', label: 'Santa Catarina' },
  { value: 'SP', label: 'São Paulo' },
  { value: 'SE', label: 'Sergipe' },
  { value: 'TO', label: 'Tocantins' },
];

export interface UserProfile {
  has_profile: boolean;
  email: string;
  sequential_id: number | null;

  full_name: string | null;
  phone: string | null;
  instagram: string | null;
  linkedin: string | null;

  company_name: string | null;
  cnpj: string | null;
  farming_type: FarmingType | null;
  annual_production_tons: string | null;
  contact_role: string | null;
  water_surface_area_ha: string | null;
  tank_count: number | null;
  predominant_species: string | null;
  company_website: string | null;

  address_street: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_zip_code: string | null;
  address_city: string | null;
  address_state: string | null;

  created_at: string | null;
  updated_at: string | null;
}

export interface ProfileUpsertPayload {
  full_name: string;
  phone: string;
  farming_type: FarmingType;
  annual_production_tons: number;

  instagram?: string | null;
  linkedin?: string | null;
  company_name?: string | null;
  cnpj?: string | null;
  contact_role?: string | null;
  water_surface_area_ha?: number | null;
  tank_count?: number | null;
  predominant_species?: string | null;
  company_website?: string | null;

  address_street?: string | null;
  address_number?: string | null;
  address_complement?: string | null;
  address_zip_code?: string | null;
  address_city?: string | null;
  address_state?: string | null;
}
