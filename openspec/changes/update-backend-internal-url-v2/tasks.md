## 1. Aplicar o novo endereço

- [ ] 1.1 `deploy/build-and-push.ps1`: `$BackendInternalUrl` = `http://10.1.2.22:8000`.
- [ ] 1.2 Conferir que nenhum outro arquivo de `deploy/` referencia `10.1.20.128`.

## 2. Build e publicação

- [ ] 2.1 `.\deploy\build-and-push.ps1 -Target frontend -Platform arm64 -Builder desktop-linux` (só a
      camada do `next build` é refeita).
- [ ] 2.2 Confirmar no ECR que `drtilapia-aws-frontend:latest` é `linux/arm64` com digest novo
      (`docker buildx imagetools inspect`).

## 3. Deploy e verificação (na EC2 `tilapia-frontend`)

- [ ] 3.1 Confirmar no backend v2: `curl -s http://localhost:8000/health` ⇒ `{"status":"ok"}` e
      `docker ps` com a imagem arm64 do backend.
- [ ] 3.2 `docker pull` da imagem do frontend e recriar o container (`docker stop`/`rm`/`run`, como nas
      instruções finais do script).
- [ ] 3.3 `GET https://<dominio-cloudfront>/api-proxy/health` ⇒ 200 `{"status":"ok"}` em poucos segundos.
- [ ] 3.4 Login em janela anônima com conta de teste (ver change `fix-login-first-access-redirect`).

## 4. Follow-up (fora desta change)

- [ ] 4.1 Substituir o IP fixo por um nome DNS interno / ALB interno, para que trocar a instância de
      backend não exija rebuild do frontend.
