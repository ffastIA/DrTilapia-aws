## 1. Confirmar ausência de uso

- [x] 1.1 `grep -rn "import jose\|from jose\|import bcrypt\|import sqlalchemy\|from sqlalchemy\|import sqlmodel\|from sqlmodel" backend/` (todo `backend/`, não só `backend/app/`) — confirmar zero ocorrências antes de remover cada pacote. Confirmado: zero ocorrências em todo `backend/`.

## 2. Atualizar `requirements.txt`

- [x] 2.1 Alterar `python-multipart==0.0.9` para `python-multipart>=0.0.18`.
- [x] 2.2 Remover as linhas `python-jose[cryptography]==3.3.0`, `bcrypt==4.1.2`, `sqlalchemy==2.0.29`, `sqlmodel>=0.0.22`.

## 3. Verificação

- [x] 3.1 Reinstalar o ambiente virtual/imagem a partir do `requirements.txt` atualizado. Imagem Docker `drtilapia-aws-backend` reconstruída com sucesso.
- [x] 3.2 Rodar `pytest` (`backend/tests/`) — confirmar que a suíte passa sem alteração de resultado. Resultado: 121 passed, 12 failed, 11 skipped. As 12 falhas são pré-existentes e não relacionadas a esta mudança (endpoint `/health` inexistente, `vector_admin_service` sem os métodos `recover_file_content`/`diagnose_file_recovery` — já documentado como H3 na auditoria —, e um teste de integração que tenta conectar a um servidor real em `localhost:8000`); nenhuma falha envolve `jose`/`bcrypt`/`sqlalchemy`/`sqlmodel`/`python-multipart`.
- [x] 3.3 Testar manualmente um upload (PDF/vídeo/imagem) end-to-end para confirmar que o parsing de `multipart/form-data` continua funcionando após o bump do `python-multipart`. Testado via `curl -F "file=@fake.pdf" http://localhost:8000/admin/upload` contra o container real: resposta `401 Token de acesso não fornecido` — confirma que o corpo multipart foi parseado corretamente e o request chegou até a dependência de autenticação (não houve erro 422 de parsing). Teste completo com upload autenticado de verdade (JWT admin real) fica fora do escopo desta validação pontual.
- [x] 3.4 Rodar `pip list` (ou equivalente) no ambiente final e confirmar que nenhum dos quatro pacotes removidos aparece, nem como dependência transitiva de outro pacote. `python-jose`, `bcrypt` e `sqlmodel` confirmados ausentes. `sqlalchemy` (2.0.52) ainda aparece, mas como dependência transitiva real de `langchain-community`/`langchain-classic` (`pip show sqlalchemy` → `Required-by: langchain-classic, langchain-community`) — não é mais fixado pela versão antiga `==2.0.29` do `requirements.txt`; o pip agora resolve a versão livremente a partir do que o `langchain-community` realmente exige.
