## 1. Novas variáveis do script

- [x] 1.1 Adicionar `$BackendInternalUrl`, `$NextPublicSupabaseUrl`, `$NextPublicSupabaseAnonKey`
      ao bloco `# ---- Preencher com os valores reais antes de usar ----` de
      `deploy/build-and-push.ps1`, com placeholders no mesmo padrão das variáveis existentes
      (`<BACKEND_PRIVATE_IP_E_PORTA>`, etc.).

## 2. Build do frontend desacoplado do Compose

- [x] 2.1 Substituir a chamada `docker compose build backend frontend` por duas chamadas
      separadas: `docker compose build backend` (inalterado) e `docker build -f frontend.Dockerfile
      --build-arg BACKEND_INTERNAL_URL=$BackendInternalUrl --build-arg
      NEXT_PUBLIC_SUPABASE_URL=$NextPublicSupabaseUrl --build-arg
      NEXT_PUBLIC_SUPABASE_ANON_KEY=$NextPublicSupabaseAnonKey -t drtilapia-aws-frontend:latest .`
      (context `.`, mesmo diretório usado hoje pelo Compose).
- [x] 2.2 Confirmar que as tags/push subsequentes (`docker tag`, `docker push`) continuam
      funcionando sem alteração, já que a imagem local `drtilapia-aws-frontend:latest` é produzida
      da mesma forma.

## 3. Validação

- [ ] 3.1 Preencher `$BackendInternalUrl` com o IP privado real da EC2 do backend (só disponível
      depois de `add-two-ec2-deploy-topology` provisionar essa instância).
- [ ] 3.2 Rodar o script e inspecionar a imagem gerada para confirmar que o rewrite de
      `/api-proxy/*` aponta para o IP correto antes do primeiro `docker push` de produção.
- [x] 3.3 Confirmar que um `docker compose build frontend` local (desenvolvimento) continua usando
      `http://backend:8000`, sem qualquer interferência das novas variáveis do script de produção.
