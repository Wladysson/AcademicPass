# AcademicPass

#### Bloco relacionado ao projeto: 

> **ATENÇÃO:** Para este projeto deve ser adotada a branch **main** como a principal para ser **criada** as outras branchs relacionadas ao **desenvolvimento do codigo**. 

> A branch `develop` foi utilizada apenas durante a fase inicial de estruturação do projeto e **não deve ser utilizada como base para novas branches de desenvolvimento.**

#### Bloco relacionado a manutenção e desenvolvimento ( Trabalhou = Documentou ):

> **NOTA**: O(a) desenvolvedor(a) responsável por uma determinada tarefa tem a **OBRIGAÇÃO** de atualizar a documentação relacionada a qualquer modificação, atualização, correção, configuração ou comportamento alterado na plataforma. Pois, se analisar, cada service, bloco e infraestrutura detem de uma documentação e é de suma importancia que ela esteja atualizada conforme o andamento de todo o projeto.

> A atualização da documentação deve ser incluída no mesmo Pull Request da alteração correspondente. Pull Requests que modifiquem comportamento do sistema sem a devida atualização documental podem ser devolvidos para ajustes antes da aprovação.


---

<br>

Bem-vindo(a).

Este documento estabelece as diretrizes obrigatórias para contribuição, versionamento, revisão de código, segurança da informação e integração de alterações no projeto.

## 1. Objetivo

O objetivo dessas orientações é centralizar o desenvolvimento, a manutenção e a evolução controlada do projeto, garantindo:

- Rastreabilidade das alterações;
- Qualidade e padronização do código;
- Revisão colaborativa antes da integração;
- Proteção das branches estratégicas;
- Conformidade com as políticas internas de segurança e desenvolvimento.

## 2. Responsabilidades da equipe

| Papel | Responsabilidades |
|---|---|
| **Desenvolvedor(a)** | Criar branches, implementar alterações, realizar commits padronizados, abrir Pull Requests e atender às revisões. |
| **Revisor(a)** | Analisar o Pull Request, validar boas práticas, apontar ajustes e aprovar somente alterações alinhadas aos padrões do projeto. |
| **Responsável técnico** | Orientar decisões técnicas, mediar divergências, acompanhar a qualidade das entregas e apoiar a evolução da arquitetura. |
| **Administrador(a) do repositório** | Gerenciar permissões, configurações de proteção de branch, integrações e políticas de segurança. |

## 3. Estrutura de branches

A branch `main` é considerada a branch principal e deve permanecer estável, pronta para deploy ou uso em produção.

| Branch | Finalidade |
|---|---|
| `main` | Código estável e validado. |
| `develop` | Integração contínua das entregas, quando aplicável. |
| `feature/nome-da-feature` | Desenvolvimento de novas funcionalidades. |
| `fix/nome-da-correcao` | Correção de defeitos. |
| `hotfix/nome-da-correcao` | Correções urgentes em produção. |
| `refactor/nome-da-alteracao` | Melhorias internas sem mudança de comportamento. |
| `docs/nome-da-documentacao` | Alterações exclusivamente documentais. |

## 4. Fluxo de contribuição

Todas as alterações devem seguir obrigatoriamente o fluxo abaixo:

1. Sincronizar a branch base com a versão mais recente da `main`.
2. Criar uma nova branch a partir da `main` ou da `develop`, quando o projeto utilizar essa estratégia.
3. Implementar as alterações de forma incremental e coesa.
4. Realizar commits claros, atômicos e padronizados.
5. Executar testes, validações e verificações locais antes do envio.
6. Enviar a branch para o repositório remoto.
7. Abrir um Pull Request para a branch base definida.
8. Preencher a descrição do Pull Request com contexto, objetivo, alterações realizadas e evidências de teste.
9. Solicitar revisão de outro integrante da equipe.
10. Corrigir os apontamentos recebidos, caso existam.
11. Obter, no mínimo, **uma aprovação** de revisor.
12. Aguardar a aprovação dos testes automatizados e checks obrigatórios das pipelines.
13. Realizar o merge na branch base.

## 5. Pull Requests

Todo Pull Request deve conter:

- Título claro e objetivo;
- Descrição do problema ou demanda;
- Escopo das alterações;
- Evidências de teste, quando aplicável;
- Referência à issue, tarefa ou card relacionado;
- Checklist de validações realizadas.

## 6. Padrão de commits

Os commits devem ser claros, atômicos e escritos no padrão **Conventional Commits**, que utiliza prefixes padronizados para identificar o tipo de alteração.

Formato recomendado:

```bash
tipo(escopo): descrição
```


### Tipos aceitos

| Tipo | Uso |
|---|---|
| `feat` | Nova funcionalidade. |
| `fix` | Correção de defeito. |
| `docs` | Alterações em documentação. |
| `style` | Ajustes de formatação que não alteram comportamento. |
| `refactor` | Melhorias internas sem alteração funcional. |
| `test` | Criação ou ajuste de testes. |
| `chore` | Tarefas de manutenção, configuração ou infraestrutura. |

## 7. Revisão de código

A revisão é uma etapa obrigatória do processo e deve priorizar:

- Correção funcional;
- Legibilidade e manutenibilidade;
- Aderência aos padrões do projeto;
- Segurança e tratamento de dados;
- Cobertura e qualidade dos testes;
- Impacto em performance, custos e ambientes downstream.

O revisor deve fazer comentários construtivos e objetivos. Alterações solicitadas devem ser resolvidas antes da aprovação final.

## 8. Proteção da branch principal

A branch `main` é protegida e não permite alterações diretas. O GitHub permite configurar regras de proteção que exigem revisão, checks bem-sucedidos e impedem force push ou exclusão da branch.

### Regras obrigatórias

- Push direto na `main` não é permitido.
- Force push na `main` não é permitido.
- Exclusão da `main` não é permitida.
- Nenhum merge pode ser realizado sem aprovação de revisor.
- Os testes automatizados e checks obrigatórios devem passar antes do merge.
- Alterações sensíveis devem passar por revisão adicional, quando aplicável.

## 9. Segurança e dados sensíveis

É proibido versionar ou expor:

- Senhas, tokens, chaves de API e credenciais;
- Dados pessoais, financeiros ou confidenciais;
- Arquivos de configuração com informações sensíveis;
- Conexões, strings de conexão ou segredos de ambiente;
- Dados de clientes, parceiros ou sistemas internos.

Utilize variáveis de ambiente, secret managers ou mecanismos seguros de configuração. Caso informações sensíveis sejam identificadas em commits, a equipe deve ser comunicada imediatamente e o incidente tratado conforme a política interna de segurança.

## 10. Testes e validações

Antes de abrir um Pull Request, o(a) contribuidor(a) deve garantir que:

- O código executa sem erros;
- Os testes existentes passam;
- Novas funcionalidades possuem testes adequados;
- Correções incluem validação do cenário corrigido;
- Dependências e configurações foram revisadas;
- A documentação relacionada foi atualizada.

Os checks automatizados são utilizados para confirmar se o Pull Request está apto a ser integrado; quando configurados como obrigatórios, devem estar bem-sucedidos antes do merge.

## 11. Contato e suporte

Em caso de dúvidas sobre o fluxo de contribuição, permissões, padrões técnicos ou segurança, entre em contato com:

- **Responsável técnico**
- **Administrador(a) do repositório** 
- **Canal da equipe** 

---