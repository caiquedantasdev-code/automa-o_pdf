# Segurança do Analisador de Editais

## Proteções implementadas

### Upload de arquivos

- Limite de 25 MB por arquivo.
- Limite de 300 páginas por PDF.
- Extensão `.pdf` validada antes do processamento.
- Assinatura `%PDF-` validada no conteúdo do arquivo.
- Estrutura do PDF validada com PyMuPDF.
- PDFs protegidos por senha são recusados.
- Nome original não é usado como caminho de armazenamento.
- Arquivo recebe um identificador aleatório antes de ser salvo.
- O arquivo temporário é removido ao final da análise.
- Arquivos temporários antigos são removidos na inicialização da aplicação.

### Aplicação web

- Token CSRF obrigatório no formulário de análise.
- Sessão protegida com `HttpOnly` e `SameSite=Lax`.
- `Secure` pode ser ativado com `COOKIE_SEGURO=1` quando a aplicação estiver em HTTPS.
- `SECRET_KEY` deve ser definida explicitamente em produção.
- `debug` fica desativado por padrão.
- Limitação de cache das respostas com `Cache-Control: no-store`.
- Cabeçalhos `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e `Permissions-Policy`.
- Política de segurança de conteúdo (CSP) configurada para restringir origens externas.
- Mensagens de erro não expõem exceções internas ao usuário.

### Conteúdo do edital e IA

O texto extraído de um edital deve ser tratado como **dado não confiável**, nunca como instrução para o sistema.

Quando for adicionada uma integração com IA, o fluxo deverá:

1. Separar instruções do sistema e conteúdo do documento.
2. Informar explicitamente ao modelo que o edital é apenas dado de entrada.
3. Ignorar instruções encontradas dentro do documento que tentem alterar o comportamento do analisador.
4. Exigir saída estruturada.
5. Registrar página e trecho de origem para cada conclusão relevante.
6. Diferenciar exigência expressa, exigência condicionada, ausência de identificação e ponto que precisa de conferência.
7. Nunca apresentar uma interpretação da IA como prova independente do edital.

## Próximas camadas para produção

Antes de disponibilizar o sistema publicamente, ainda devem ser considerados HTTPS obrigatório, limitação de requisições por IP/usuário, autenticação, autorização por usuário, armazenamento privado de documentos, monitoramento, auditoria e execução isolada do processamento de PDFs.
