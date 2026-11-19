# Arvore base relacionada a estrutura principal da plataforma

## Estrutura do Projeto

```text
academicpass/                                        # Plataforma distribuída de busca e indexação do acervo ENADE
├── docker/                                         # Orquestração local com Docker Compose
│   └── env/                                        # Modelos de variáveis de ambiente dos componentes
│
├── docs/                                           # Documentação técnica e acadêmica da plataforma
│   ├── architecture/                               # Arquitetura, comunicação, persistência e resiliência
│   ├── security/                                   # Autenticação, autorização, LDAP e Kerberos
│   ├── diagrams/                                   # Diagramas da arquitetura, APIs, mensageria e infraestrutura
│   ├── report/                                     # Material de elaboração do relatório técnico
│   │   ├── sbc-template/                            # Modelo e recursos para formatação nas normas SBC
│   │   ├── metrics/                                 # Resultados de desempenho, ingestão, cache e extração
│   │   └── evidence/                                # Evidências dos testes, experimentos e recuperação de falhas
│   └── decisions/                                  # Registros das decisões arquiteturais e suas justificativas
│
├── services/                                       # Aplicações independentes que compõem a plataforma
│   ├── identity-service/                           # Java + Quarkus: autenticação LDAP, sessões e perfis
│   │   └── src/                                    # Código-fonte e testes do serviço
│   │       ├── main/java/org/enade/identity/        # Pacote principal da aplicação
│   │       │   ├── api/                            # Endpoints de autenticação e consulta de sessão
│   │       │   ├── application/                    # Casos de uso de login e gerenciamento de sessão
│   │       │   ├── domain/                         # Modelos e regras do domínio de identidade
│   │       │   │   ├── model/                      # Usuários, perfis e sessões
│   │       │   │   └── exception/                  # Exceções de autenticação e sessão
│   │       │   ├── infrastructure/                 # Integrações técnicas e persistência
│   │       │   │   ├── ldap/                       # Autenticação e consulta de usuários e grupos
│   │       │   │   ├── redis/                      # Persistência de sessões e controle de expiração
│   │       │   │   └── security/                   # Segurança da comunicação interna
│   │       │   └── presentation/                   # Representações de entrada e saída da aplicação
│   │       │       └── dto/                        # Contratos de login, sessão e erros
│   │       └── test/                               # Testes automatizados do serviço
│   │           ├── unit/                           # Testes de autenticação, sessão e perfis
│   │           └── integration/                    # Testes de integração com LDAP e Redis
│   │
│   ├── ingestion-service/                          # Python: coleta, validação, armazenamento e publicação de PDFs
│   │   ├── src/ingestion/                          # Código-fonte da aplicação de ingestão
│   │   │   ├── collectors/                         # Descoberta e download de provas, gabaritos e diretrizes
│   │   │   ├── storage/                            # Persistência dos PDFs e referências de armazenamento
│   │   │   ├── events/                             # Modelos de eventos e publicação no Kafka
│   │   │   └── observability/                      # Métricas de coleta, falhas, duração e volume processado
│   │   └── tests/                                  # Testes automatizados da ingestão
│   │       ├── unit/                               # Testes de validação, checksum e eventos
│   │       └── integration/                        # Testes com Kafka e armazenamento
│   │
│   ├── extraction-service/                         # Python: transformação de PDFs em questões estruturadas
│   │   ├── src/extraction/                         # Código-fonte da aplicação de extração
│   │   │   ├── consumers/                          # Consumo de eventos de documentos disponíveis
│   │   │   ├── storage/                            # Recuperação dos PDFs e verificação de integridade
│   │   │   ├── parsers/                            # Extração, segmentação, classificação e metadados
│   │   │   ├── media/                              # Conversão de fórmulas, diagramas e tabelas com apoio de IA
│   │   │   ├── producers/                          # Publicação de questões estruturadas e eventos de erro
│   │   │   ├── resilience/                         # Retentativas, idempotência e encaminhamento para DLQ
│   │   │   └── schemas/                            # Modelos de validação dos eventos da extração
│   │   └── tests/                                  # Testes automatizados da extração
│   │       ├── fixtures/                           # PDFs e resultados esperados para testes reproduzíveis
│   │       ├── unit/                               # Testes de segmentação, classificação, mídia e metadados
│   │       └── integration/                        # Testes com Kafka, armazenamento e provedor de IA simulado
│   │
│   ├── indexing-service/                           # Python: consumo de questões e indexação no Elasticsearch
│   │   ├── src/indexing/                           # Código-fonte da aplicação de indexação
│   │   │   ├── consumers/                          # Consumo dos eventos de questões estruturadas
│   │   │   ├── transformers/                       # Conversão dos eventos em documentos de busca
│   │   │   ├── elasticsearch/                      # Cliente, indexação em lote e gerenciamento dos índices
│   │   │   ├── resilience/                         # Controle de offsets, retentativas e tratamento de falhas
│   │   │   └── observability/                      # Métricas de indexação, erros e duração do processamento
│   │   └── tests/                                  # Testes automatizados da indexação
│   │       ├── unit/                               # Testes de transformação e construção dos documentos
│   │       └── integration/                        # Testes com Kafka e Elasticsearch
│   │
│   ├── search-service/                             # Java + Quarkus: busca, filtros, agregações e cache
│   │   └── src/                                    # Código-fonte e testes do serviço
│   │       ├── main/java/org/enade/search/          # Pacote principal da aplicação
│   │       │   ├── api/                            # Endpoints de consulta de questões e agregações
│   │       │   ├── application/                    # Casos de uso de busca e análise do acervo
│   │       │   ├── domain/                         # Modelos e regras do domínio de consulta
│   │       │   │   ├── model/                      # Questões, filtros e resultados paginados
│   │       │   │   └── exception/                  # Exceções das operações de consulta
│   │       │   ├── infrastructure/                 # Integrações técnicas utilizadas pelo serviço
│   │       │   │   ├── elasticsearch/              # Consultas full-text, filtros, highlights e agregações
│   │       │   │   ├── redis/                      # Cache de resultados e controle de expiração
│   │       │   │   ├── identity/                   # Validação das credenciais do usuário
│   │       │   │   └── security/                   # Autorização por perfil e comunicação interna protegida
│   │       │   └── presentation/                   # Representações públicas dos resultados
│   │       │       ├── dto/                        # Contratos de busca, respostas e erros
│   │       │       └── mapper/                     # Conversão dos modelos para respostas da API
│   │       └── test/                               # Testes automatizados do serviço
│   │           ├── unit/                           # Testes de busca, cache e autorização
│   │           └── integration/                    # Testes com Elasticsearch, Redis e validação de identidade
│   │
│   ├── question-selection-service/                 # Java + Quarkus: gerenciamento da seleção pessoal de questões
│   │   └── src/                                    # Código-fonte e testes do serviço
│   │       ├── main/java/org/enade/selection/       # Pacote principal da aplicação
│   │       │   ├── api/                            # Endpoints de adição, consulta, remoção e limpeza da seleção
│   │       │   ├── application/                    # Casos de uso de gerenciamento da seleção
│   │       │   ├── domain/                         # Modelos e regras do domínio de seleção
│   │       │   │   ├── model/                      # Seleção do usuário e questões selecionadas
│   │       │   │   └── exception/                  # Exceções das operações de seleção
│   │       │   ├── infrastructure/                 # Integrações técnicas e persistência
│   │       │   │   ├── redis/                      # Armazenamento das seleções e controle de expiração
│   │       │   │   ├── identity/                   # Validação das credenciais do usuário
│   │       │   │   └── security/                   # Autorização e isolamento por proprietário
│   │       │   └── presentation/                   # Representações de entrada e saída da API
│   │       │       └── dto/                        # Contratos das operações de seleção
│   │       └── test/                               # Testes automatizados do serviço
│   │           ├── unit/                           # Testes de duplicidade, limites e regras da seleção
│   │           └── integration/                    # Testes com Redis e validação de identidade
│   │
│   ├── simulado-service/                           # Java + Quarkus: geração e exportação assíncrona de simulados
│   │   └── src/                                    # Código-fonte e testes do serviço
│   │       ├── main/java/br/org/enade/simulado/     # Pacote principal da aplicação
│   │       │   ├── api/                            # Endpoints de solicitação, acompanhamento e download
│   │       │   ├── application/                    # Casos de uso de solicitação e geração de simulados
│   │       │   ├── domain/                         # Modelos e regras do domínio de simulados
│   │       │   │   ├── model/                      # Simulados, questões, formatos e estados da exportação
│   │       │   │   └── exception/                  # Exceções de processamento e exportação
│   │       │   ├── workers/                        # Processamento assíncrono e geração de PDF ou JSON
│   │       │   ├── infrastructure/                 # Integrações técnicas necessárias à exportação
│   │       │   │   ├── kafka/                      # Publicação e consumo dos pedidos de exportação
│   │       │   │   ├── storage/                    # Persistência e recuperação dos arquivos gerados
│   │       │   │   ├── redis/                      # Status e referências das exportações
│   │       │   │   ├── search/                     # Cliente da API de consulta de questões
│   │       │   │   ├── selection/                  # Cliente da API de seleção de questões
│   │       │   │   ├── identity/                   # Validação das credenciais do solicitante
│   │       │   │   └── security/                   # Permissões de professor e comunicação interna protegida
│   │       │   └── presentation/                   # Representações públicas dos pedidos e resultados
│   │       │       └── dto/                        # Contratos de solicitação, status e exportação
│   │       └── test/                               # Testes automatizados do serviço
│   │           ├── unit/                           # Testes das regras de geração e exportação
│   │           └── integration/                    # Testes com Kafka, Redis, armazenamento e APIs dependentes
│   │
│   └── web-client/                                 # React: interface de busca, seleção e montagem de simulados
│       ├── src/                                    # Código-fonte da aplicação web
│       │   ├── api/                                # Clientes HTTP para comunicação com as APIs pelo gateway
│       │   ├── stores/                             # Estado de autenticação, busca e seleção
│       │   ├── components/                         # Componentes reutilizáveis da interface
│       │   │   ├── search/                         # Busca, filtros, resultados e paginação
│       │   │   ├── media/                          # Renderização de fórmulas, diagramas e tabelas
│       │   │   ├── selection/                      # Gerenciamento da lista de questões
│       │   │   └── analytics/                      # Gráficos e visualizações analíticas
│       │   └── views/                              # Páginas de login, busca, detalhes, seleção e painel
│       └── tests/                                  # Testes automatizados do frontend
│           ├── unit/                               # Testes de componentes e gerenciamento de estado
│           └── e2e/                                # Testes dos fluxos completos pela interface
│
├── shared/                                         # Contratos e definições compartilhados entre aplicações
│   ├── contracts/                                  # Contratos de mensageria e exposição das APIs
│   │   └── service-openapi/                        # Especificações OpenAPI dos serviços REST
│   ├── schemas/                                    # Schemas dos eventos de documentos, questões, exportações e erros
│   └── docs/                                       # Políticas de compartilhamento e evolução dos contratos
│
├── data/                                           # Dados controlados para desenvolvimento e avaliação
│   ├── samples/                                    # Amostras pequenas de documentos para desenvolvimento e CI
│   └── validation/                                 # Amostra revisada de questões e resultados de qualidade
│
├── scripts/                                        # Automação de inicialização, ingestão, testes, métricas e segurança
│
├── .github/                                        # Configurações de colaboração e automação do repositório
│   └── workflows/                                  # Pipelines de CI, build, segurança e testes ponta a ponta
│
└── infrastructure/                                 # Configurações dos componentes de infraestrutura
    ├── kafka/                                      # Mensageria, tópicos, segurança e acompanhamento do consumo
    │   ├── config/                                 # Brokers, KRaft, listeners e autenticação
    │   └── scripts/                                # Provisionamento de tópicos e inspeção de grupos e lag
    │
    ├── elasticsearch/                              # Configuração da indexação e busca distribuída
    │   ├── config/                                 # Configurações de cluster, rede e segurança
    │   ├── indices/                                # Mappings, analyzers, sinônimos, shards e réplicas
    │   └── scripts/                                # Criação dos índices e validação das consultas
    │
    ├── redis/                                      # Configuração do cache e armazenamento de estado
    │   ├── config/                                 # Memória, persistência e política de descarte
    │   └── scripts/                                # Inspeção de chaves de cache, sessões e seleções
    │
    ├── minio/                                      # Armazenamento de PDFs, mídia e arquivos exportados
    │   ├── config/                                 # Inicialização dos buckets e políticas de acesso
    │   └── scripts/                                # Inspeção dos objetos e seus metadados
    │
    ├── ldap/                                       # Diretório de usuários e grupos
    │   ├── bootstrap/                              # Estrutura inicial, grupos e usuários de teste
    │   └── scripts/                                # Inicialização e provisionamento do diretório
    │
    ├── kerberos/                                   # Autenticação das identidades técnicas da plataforma
    │   ├── config/                                 # Realm, KDC e permissões administrativas
    │   ├── principals/                             # Definições das identidades de componentes e clientes
    │   └── scripts/                                # Provisionamento, geração de keytabs e validação
    │
    ├── observability/                              # Monitoramento e coleta de resultados experimentais
    │   ├── prometheus/                             # Configuração da coleta de métricas e exporters
    │   ├── grafana/                                # Configuração das visualizações de monitoramento
    │   │   ├── dashboards/                         # Painéis de ingestão, busca, Kafka, cache e exportações
    │   │   └── provisioning/                       # Provisionamento de fontes de dados e painéis
    │   └── collectors/                             # Coleta de métricas e geração de artefatos do relatório
    │
    └── api-gateway/                                # Configuração do ponto de entrada das APIs
        ├── nginx/                                  # Servidor e rotas públicas
        └── config/                                 # Destinos internos e regras de encaminhamento
```