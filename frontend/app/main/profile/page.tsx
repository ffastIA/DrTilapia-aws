// CAMINHO: frontend/app/main/profile/page.tsx

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import PageHeader from '@/components/ui/PageHeader';
import BackButton from '@/components/ui/BackButton';
import Card from '@/components/ui/Card';
import Field, { Input } from '@/components/ui/Field';
import Alert from '@/components/ui/Alert';
import Button from '@/components/Button';
import { useProfile } from '@/hooks/useProfile';
import { useUpdateProfileMutation } from '@/hooks/useUpdateProfileMutation';
import { ESTADOS_BR, FARMING_TYPE_OPTIONS, FarmingType, ProfileUpsertPayload } from '@/types/profile';

const SELECT_CLASSES =
  'w-full min-h-[40px] px-2.5 py-2 text-sm bg-surface text-foreground border border-border hover:border-foreground/45 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary focus-visible:border-primary disabled:opacity-60';

const PRODUCTION_REGEX = /^\d+(\.\d)?$/;

interface FormState {
  full_name: string;
  phone: string;
  instagram: string;
  linkedin: string;
  company_name: string;
  cnpj: string;
  farming_type: FarmingType | '';
  annual_production_tons: string;
  contact_role: string;
  water_surface_area_ha: string;
  tank_count: string;
  predominant_species: string;
  company_website: string;
  address_street: string;
  address_number: string;
  address_complement: string;
  address_zip_code: string;
  address_city: string;
  address_state: string;
}

const EMPTY_FORM: FormState = {
  full_name: '',
  phone: '',
  instagram: '',
  linkedin: '',
  company_name: '',
  cnpj: '',
  farming_type: '',
  annual_production_tons: '',
  contact_role: '',
  water_surface_area_ha: '',
  tank_count: '',
  predominant_species: '',
  company_website: '',
  address_street: '',
  address_number: '',
  address_complement: '',
  address_zip_code: '',
  address_city: '',
  address_state: '',
};

export default function ProfilePage() {
  const { profile, isLoading, refetch } = useProfile();
  const updateMutation = useUpdateProfileMutation();
  const router = useRouter();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (!profile) return;
    setForm({
      full_name: profile.full_name ?? '',
      phone: profile.phone ?? '',
      instagram: profile.instagram ?? '',
      linkedin: profile.linkedin ?? '',
      company_name: profile.company_name ?? '',
      cnpj: profile.cnpj ?? '',
      farming_type: profile.farming_type ?? '',
      annual_production_tons: profile.annual_production_tons ?? '',
      contact_role: profile.contact_role ?? '',
      water_surface_area_ha: profile.water_surface_area_ha ?? '',
      tank_count: profile.tank_count != null ? String(profile.tank_count) : '',
      predominant_species: profile.predominant_species ?? '',
      company_website: profile.company_website ?? '',
      address_street: profile.address_street ?? '',
      address_number: profile.address_number ?? '',
      address_complement: profile.address_complement ?? '',
      address_zip_code: profile.address_zip_code ?? '',
      address_city: profile.address_city ?? '',
      address_state: profile.address_state ?? '',
    });
  }, [profile]);

  const setField = (name: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [name]: e.target.value }));
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!form.full_name.trim()) errors.full_name = 'Campo obrigatório.';
    if (!form.phone.trim()) errors.phone = 'Campo obrigatório.';
    if (!form.farming_type) errors.farming_type = 'Campo obrigatório.';
    if (!form.annual_production_tons.trim()) {
      errors.annual_production_tons = 'Campo obrigatório.';
    } else if (!PRODUCTION_REGEX.test(form.annual_production_tons.trim())) {
      errors.annual_production_tons = 'Use um número com no máximo 1 casa decimal (ex.: 125.5).';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError('');
    setSuccessMessage('');
    if (!validate()) return;

    const payload: ProfileUpsertPayload = {
      full_name: form.full_name.trim(),
      phone: form.phone.trim(),
      farming_type: form.farming_type as FarmingType,
      annual_production_tons: parseFloat(form.annual_production_tons),
      instagram: form.instagram.trim() || null,
      linkedin: form.linkedin.trim() || null,
      company_name: form.company_name.trim() || null,
      cnpj: form.cnpj.trim() || null,
      contact_role: form.contact_role.trim() || null,
      water_surface_area_ha: form.water_surface_area_ha.trim() ? parseFloat(form.water_surface_area_ha) : null,
      tank_count: form.tank_count.trim() ? parseInt(form.tank_count, 10) : null,
      predominant_species: form.predominant_species.trim() || null,
      company_website: form.company_website.trim() || null,
      address_street: form.address_street.trim() || null,
      address_number: form.address_number.trim() || null,
      address_complement: form.address_complement.trim() || null,
      address_zip_code: form.address_zip_code.trim() || null,
      address_city: form.address_city.trim() || null,
      address_state: form.address_state || null,
    };

    const wasIncomplete = !profile?.has_profile;

    updateMutation.mutate(payload, {
      onSuccess: () => {
        if (wasIncomplete) {
          // Primeira conclusão do cadastro: libera o gate de onboarding e volta à tela principal.
          Cookies.set('profileComplete', '1', { path: '/', sameSite: 'lax' });
          router.push('/main/hub');
          return;
        }
        setSuccessMessage('Perfil salvo com sucesso.');
        refetch();
      },
      onError: (error) => {
        setFormError(error.message);
      },
    });
  };

  return (
    <div>
      <PageHeader
        kicker="Cadastro"
        title="Meu Perfil"
        description="Mantenha seus dados de contato, empresa e produção atualizados. Você pode editar este cadastro quando quiser."
        actions={<BackButton />}
      />

      {isLoading ? (
        <Card className="text-center py-12 text-muted-foreground">Carregando…</Card>
      ) : (
        <form onSubmit={handleSubmit}>
          <Card className="mb-6">
            <h2 className="font-heading font-semibold uppercase text-sm mb-4">Dados pessoais</h2>

            <Field label="Nome completo *" htmlFor="full_name">
              <Input
                id="full_name"
                value={form.full_name}
                onChange={setField('full_name')}
                disabled={updateMutation.isPending}
              />
              {fieldErrors.full_name && <p className="text-xs text-destructive mt-1">{fieldErrors.full_name}</p>}
            </Field>

            <Field label="Telefone de contato *" htmlFor="phone">
              <Input
                id="phone"
                value={form.phone}
                onChange={setField('phone')}
                placeholder="(00) 00000-0000"
                disabled={updateMutation.isPending}
              />
              {fieldErrors.phone && <p className="text-xs text-destructive mt-1">{fieldErrors.phone}</p>}
            </Field>

            <Field label="Email" htmlFor="email">
              <Input id="email" value={profile?.email ?? ''} disabled />
              <p className="text-xs text-muted-foreground mt-1">
                Este é o email da sua conta. Para alterá-lo, use as configurações de login.
              </p>
            </Field>

            <Field label="Instagram" htmlFor="instagram">
              <Input
                id="instagram"
                value={form.instagram}
                onChange={setField('instagram')}
                placeholder="@seuusuario"
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="LinkedIn" htmlFor="linkedin">
              <Input
                id="linkedin"
                value={form.linkedin}
                onChange={setField('linkedin')}
                placeholder="linkedin.com/in/seuusuario"
                disabled={updateMutation.isPending}
              />
            </Field>
          </Card>

          <Card className="mb-6">
            <h2 className="font-heading font-semibold uppercase text-sm mb-4">Empresa e produção</h2>

            <Field label="Nome da empresa" htmlFor="company_name">
              <Input
                id="company_name"
                value={form.company_name}
                onChange={setField('company_name')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="CNPJ" htmlFor="cnpj">
              <Input
                id="cnpj"
                value={form.cnpj}
                onChange={setField('cnpj')}
                placeholder="00.000.000/0000-00"
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Cargo/função" htmlFor="contact_role">
              <Input
                id="contact_role"
                value={form.contact_role}
                onChange={setField('contact_role')}
                placeholder="Ex.: sócio-proprietário, técnico responsável"
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Tipo de criação *" htmlFor="farming_type">
              <select
                id="farming_type"
                className={SELECT_CLASSES}
                value={form.farming_type}
                onChange={setField('farming_type')}
                disabled={updateMutation.isPending}
              >
                <option value="">Selecione…</option>
                {FARMING_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {fieldErrors.farming_type && (
                <p className="text-xs text-destructive mt-1">{fieldErrors.farming_type}</p>
              )}
            </Field>

            <Field label="Produção em toneladas/ano *" htmlFor="annual_production_tons">
              <Input
                id="annual_production_tons"
                inputMode="decimal"
                value={form.annual_production_tons}
                onChange={setField('annual_production_tons')}
                placeholder="Ex.: 125.5"
                disabled={updateMutation.isPending}
              />
              {fieldErrors.annual_production_tons && (
                <p className="text-xs text-destructive mt-1">{fieldErrors.annual_production_tons}</p>
              )}
            </Field>

            <Field label="Área de lâmina d'água (ha)" htmlFor="water_surface_area_ha">
              <Input
                id="water_surface_area_ha"
                inputMode="decimal"
                value={form.water_surface_area_ha}
                onChange={setField('water_surface_area_ha')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Nº de tanques/viveiros" htmlFor="tank_count">
              <Input
                id="tank_count"
                inputMode="numeric"
                value={form.tank_count}
                onChange={setField('tank_count')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Espécie predominante" htmlFor="predominant_species">
              <Input
                id="predominant_species"
                value={form.predominant_species}
                onChange={setField('predominant_species')}
                placeholder="Ex.: Tilápia"
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Site da empresa" htmlFor="company_website">
              <Input
                id="company_website"
                value={form.company_website}
                onChange={setField('company_website')}
                placeholder="https://"
                disabled={updateMutation.isPending}
              />
            </Field>
          </Card>

          <Card className="mb-6">
            <h2 className="font-heading font-semibold uppercase text-sm mb-4">Endereço</h2>

            <Field label="Logradouro" htmlFor="address_street">
              <Input
                id="address_street"
                value={form.address_street}
                onChange={setField('address_street')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Número" htmlFor="address_number">
              <Input
                id="address_number"
                value={form.address_number}
                onChange={setField('address_number')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Complemento" htmlFor="address_complement">
              <Input
                id="address_complement"
                value={form.address_complement}
                onChange={setField('address_complement')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="CEP" htmlFor="address_zip_code">
              <Input
                id="address_zip_code"
                value={form.address_zip_code}
                onChange={setField('address_zip_code')}
                placeholder="00000-000"
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Cidade" htmlFor="address_city">
              <Input
                id="address_city"
                value={form.address_city}
                onChange={setField('address_city')}
                disabled={updateMutation.isPending}
              />
            </Field>

            <Field label="Estado" htmlFor="address_state">
              <select
                id="address_state"
                className={SELECT_CLASSES}
                value={form.address_state}
                onChange={setField('address_state')}
                disabled={updateMutation.isPending}
              >
                <option value="">Selecione…</option>
                {ESTADOS_BR.map((uf) => (
                  <option key={uf.value} value={uf.value}>
                    {uf.value} — {uf.label}
                  </option>
                ))}
              </select>
            </Field>
          </Card>

          {formError && <Alert variant="error">{formError}</Alert>}
          {successMessage && <Alert variant="success">{successMessage}</Alert>}

          <Button type="submit" variant="primary" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Salvando...' : 'Salvar perfil'}
          </Button>
        </form>
      )}
    </div>
  );
}
