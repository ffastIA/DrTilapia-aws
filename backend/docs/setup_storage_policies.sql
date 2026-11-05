-- ============================================================
-- DrTilapIA — Policies por dono no bucket fish-images (SEC-10)
-- Execute no Supabase SQL Editor ANTES de trocar o cliente de Storage
-- de supabase_admin para get_user_scoped_client em fish_image_service.py.
-- Convenção de path: {user_id}/{uuid}.{ext}  (ver _make_storage_path)
-- A service_role ignora RLS, então o backend atual continua funcionando.
-- ============================================================

CREATE POLICY "fish_images_storage_select_own"
  ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'fish-images' AND (storage.foldername(name))[1] = auth.uid()::text);

CREATE POLICY "fish_images_storage_insert_own"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'fish-images' AND (storage.foldername(name))[1] = auth.uid()::text);

CREATE POLICY "fish_images_storage_update_own"
  ON storage.objects FOR UPDATE TO authenticated
  USING (bucket_id = 'fish-images' AND (storage.foldername(name))[1] = auth.uid()::text);

CREATE POLICY "fish_images_storage_delete_own"
  ON storage.objects FOR DELETE TO authenticated
  USING (bucket_id = 'fish-images' AND (storage.foldername(name))[1] = auth.uid()::text);

-- O bucket deve ser PRIVADO (Storage → fish-images → Public bucket desligado).
