# Auditoria tecnica EssenceK - 2026-08-05

## Estado e regra de seguranca

Esta auditoria foi executada sem publicacao em producao e sem escrita no banco online. A producao, o banco Neon, as variaveis da Vercel e a pasta `mind` foram tratados como fontes protegidas. Nenhum `DROP`, `TRUNCATE`, limpeza em massa, reset de Git, force-push, seed ou migration foi executado em producao.

Estado de referencia identificado:

| Item | Estado |
| --- | --- |
| Projeto local | `C:\paragua` |
| Repositorio | `MarcosPauloOtaviano/essencek` |
| Branch de trabalho | `feat/sincronizacao-performance-categorias` |
| Branch de producao | `main` |
| Commit publicado antes da auditoria | `ef06608e6db3f3ae4b0802b01c245d5c7829054a` |
| Conta GitHub | `MarcosPauloOtaviano` |
| Conta Vercel | `marcospaulootaviano` |
| Time Vercel | `marcos-paulos-projects-7e938b4a` |
| Projeto Vercel | `essencek` |
| Dominio principal | `https://essencekimportados.com.br` |
| Aplicacao | Django 4.2 / Python 3.12 / templates Django |
| Banco online | Neon PostgreSQL 17.10, regiao `sa-east-1` |
| Regiao anterior da Function | `iad1` |
| Regiao configurada nesta branch | `gru1` |

## Backups confirmados

| Conteudo | Local |
| --- | --- |
| Codigo local completo | `C:\EssenceKBackups\essencek-backup-20260804-210810\paragua` |
| Branch de seguranca | `backup/pre-sincronizacao-performance-categorias-20260804-210810` |
| Pasta `mind` | `C:\EssenceKBackups\mind-backup-20260805-213724\mind` |
| Dados do banco, exportacao logica gzip | `C:\EssenceKBackups\database-backup-20260805-214128\essencek-data.json.gz` |
| Schema e inventario do banco | `C:\EssenceKBackups\database-backup-20260805-214128` |
| Banco e evidencias E2E isolados | `C:\EssenceKBackups\e2e-browser-20260805-224753` |

O backup da `mind` possui 3.890 arquivos e 33.540.843 bytes. A exportacao logica do banco possui 29.124.108 bytes; a descompressao e o parse JSON foram validados, com 486 objetos no nivel principal. O arquivo esta codificado em Windows-1252 e deve ser convertido para UTF-8 antes de uma restauracao com ferramentas que exijam UTF-8. Toda restauracao deve ser ensaiada primeiro em banco isolado.

## Inventario do banco

Leitura realizada no banco online, sem alteracoes:

- PostgreSQL 17.10.
- 31 tabelas, 302 colunas, 101 constraints e 99 indices.
- 62 migrations registradas antes da migration nova desta branch.
- Nenhuma view, function, trigger ou policy encontrada.
- RLS nao esta habilitado; a autorizacao atual ocorre na aplicacao Django e no acesso privado ao banco.
- Nenhum indice invalido e nenhum indice de chave estrangeira ausente no inventario.
- 55 produtos ativos, 205 registros de midia e 5 categorias ativas sem produtos.
- 2 usuarios no momento do inventario; nenhum dado pessoal foi copiado para este documento.
- Nenhum pedido ou pagamento no snapshot de producao analisado.
- Um carrinho anonimo legado sem identidade ativa foi preservado, sem exclusao automatica.

A migration `orders/0006_alter_order_payment_method_alter_order_status.py` apenas amplia choices e defaults de status/forma de pagamento. Ela nao remove tabela, coluna ou dado. Ela nao foi aplicada ao banco de producao nesta auditoria.

## Diagnostico de performance

Medicao de referencia feita antes das correcoes:

| Rota | Primeiro acesso | Acesso aquecido | HTML |
| --- | ---: | ---: | ---: |
| Home | 35,59 s | 0,17-0,25 s | 65.869 bytes |
| Catalogo | 9,215 s | 0,188-0,261 s | 63.373 bytes |

Causas encontradas:

1. `migrate --run-syncdb` era executado dentro de `wsgi.py` a cada cold start.
2. A Function executava em `iad1`, enquanto o banco esta em `sa-east-1`, adicionando latencia de rede a cada consulta.
3. Paginas publicas nao podiam aproveitar CDN porque HTML de cards carregava CSRF e podia criar cookies de sessao.
4. Home, catalogo, filtros e imagens faziam consultas repetidas evitaveis.
5. A verificacao de existencia de midia persistida consultava o banco antes de retornar cada URL.

Correcoes:

- migrations removidas da inicializacao WSGI; passam a ser uma etapa explicita e auditavel.
- Function configurada para `gru1`.
- cache CDN curto somente para GET anonimo realmente publico, recusando respostas com cookie, CSRF, streaming, JSON ou usuario autenticado.
- quick-add solicita CSRF somente no clique e mantem link de detalhe como fallback sem JavaScript.
- `select_related`, `prefetch_related`, agregacoes e contagens consolidadas nas rotas publicas e administrativas.
- cache curto da navegacao e eliminacao de consultas de imagem repetidas.
- busca GTIN vazia corrigida para nao transformar qualquer busca textual em correspondencia universal.

## Catalogo, categorias e home

- Rotas legiveis adicionadas para ofertas, destaques, pronta entrega e categorias.
- Menus, carrossel de categorias e atalhos circulares da home usam categorias e disponibilidade reais.
- Categorias ativas vazias deixam de aparecer para o cliente, sem serem apagadas do painel.
- Agrupamentos de Perfumes, K-Beauty, Decanter e Eletronicos aceitam a taxonomia existente e seus descendentes.
- Ofertas exigem preco promocional valido, positivo, menor que o preco normal e produto disponivel.
- As bolinhas da home permanecem rolaveis no celular e nao sao mais cobertas pelos atalhos flutuantes.
- Instagram flutuante e ocultado no celular porque o link continua disponivel no rodape; WhatsApp fica com alvo de toque de 44 px.

## Carrinho e frete

- Carrinho anonimo passou a usar UUID estavel na sessao, sem depender da rotacao do session key.
- Carrinho anonimo e autenticado sao mesclados com limite de estoque e lock transacional.
- Produto, variante, quantidade e estoque sao revalidados no add, update e checkout.
- Itens que ficaram indisponiveis continuam visiveis para correcao, mas bloqueiam checkout.
- Alterar qualquer item invalida a cotacao de frete anterior.
- A opcao de frete e validada no servidor contra as opcoes calculadas e contra uma assinatura do carrinho.
- Calculo na pagina de produto nao cria carrinho anonimo.
- Frete aceita valor zero quando uma opcao gratuita valida for selecionada.
- Interface AJAX trata cliques rapidos, mantem o ultimo valor desejado e atualiza subtotal, total e contador global.
- Em ate 768 px, a tabela vira um cartao responsivo completo, sem cortar produto ou preco.

## Checkout temporario pelo WhatsApp

Com `WHATSAPP_CHECKOUT_ONLY=True`:

- o pedido e criado uma unica vez por token de checkout;
- dados, itens, variantes, quantidades, precos, frete e total sao recalculados no servidor dentro de transacao;
- a mensagem do WhatsApp usa somente o snapshot persistido do pedido;
- o pedido inicia em `awaiting_contact` com `payment_method=whatsapp`;
- o estoque nao baixa ao criar o pedido;
- paginas Pix/cartao redirecionam ao resumo do WhatsApp e o webhook Mercado Pago responde 404;
- a confirmacao manual no painel baixa estoque uma unica vez, com locks e nova validacao de disponibilidade.

O modo e reversivel. Com `WHATSAPP_CHECKOUT_ONLY=False`, o checkout volta a exibir Pix/cartao, cria pedido `awaiting_payment` e segue para o fluxo de gateway preservado.

## Seguranca

- logout alterado para POST com CSRF.
- rate limit de login limpa tentativas apos autenticacao bem-sucedida.
- `SECRET_KEY` passa a ser obrigatoria no ambiente Vercel real.
- HTTPS, cookies seguros e HSTS ficam ativos nas settings Vercel.
- webhook Mercado Pago sem secret e rejeitado; no modo WhatsApp ele fica fechado.
- download de imagem remota limita protocolo, credenciais na URL, DNS/IP publico, redirects, tipo MIME, tamanho, tempo e streaming.
- caminhos absolutos ou com `..` sao rejeitados no endpoint e storage de midia.
- textos externos continuam renderizados como texto, sem `safe` ou HTML remoto.
- dependencias atualizadas para Django 4.2.30, Pillow 12.3.0, Requests 2.34.2 e Cryptography 50.0.0.

## Interface e acessibilidade

- landmarks, headings, labels, breadcrumbs, avisos e nomes acessiveis revisados.
- contraste dos status, textos secundarios e rodape corrigido.
- botoes de quantidade usam icones com `aria-label`.
- menus e filtros moveis mantem estado acessivel e nao criam overflow.
- paginas 404 e 500 personalizadas usam o layout da loja e linguagem que nao confirma pedido indevidamente.
- o painel foi revisado em modo somente leitura em todas as telas principais.

## Verificacoes executadas

Automacao:

- `python manage.py test --noinput`: 88 testes, todos aprovados em 65,987 s.
- `python manage.py check`: sem problemas.
- `python manage.py check --deploy --settings=paraguashopping.settings.vercel`: sem problemas.
- `python manage.py makemigrations --check --dry-run`: nenhuma mudanca nao migrada.
- `python -m compileall`: aprovado.
- `node --check static/js/main.js`: aprovado.
- `git diff --check`: aprovado; apenas avisos informativos de LF/CRLF no Windows.
- `pip check`: nenhuma dependencia quebrada.
- `pip-audit -r requirements.txt`: nenhuma vulnerabilidade conhecida.
- Bandit com severidade media/alta: nenhum achado.
- `collectstatic` em pasta isolada: 145 arquivos copiados e 417 pos-processados.

Navegador, banco SQLite copiado e usuarios de teste isolados:

- desktop, 390 x 844 e tablet 768 x 1024;
- home, busca positiva/negativa, catalogo, categoria, filtros, produto e calculo de frete;
- add, update rapido, persistencia, remocao, contador e merge anonimo/autenticado;
- login, logout POST, cadastro, perfil, pedidos, detalhe e bloqueio de usuario comum no painel;
- checkout com retirada, pedido WhatsApp, idempotencia e confirmacao de que o estoque nao baixa antes do pagamento;
- dashboard, produtos, formularios, categorias, marcas, pedidos, encomendas, clientes, vitrine, proxima viagem, relatorios e configuracoes;
- 404 com `DEBUG=False`, WhiteNoise e assets versionados;
- imagens quebradas e overflow horizontal: zero nas telas finais verificadas;
- axe-core: zero violacoes nas telas finais. A home conserva um resultado inconclusivo do axe em um circulo parcialmente cortado pelo carrossel horizontal; contraste preto sobre fundo claro foi verificado manualmente.

Nenhum clique destrutivo do painel foi executado. Todos os pedidos, usuarios e alteracoes de carrinho usados no E2E ficaram no banco copiado.

## Variaveis necessarias, somente nomes

Principais nomes conferidos: `SECRET_KEY`, `SITE_URL`, `DATABASE_URL`, `POSTGRES_URL`, `USE_DATABASE_MEDIA_STORAGE_ON_VERCEL`, `STORE_WHATSAPP`, `WHATSAPP_CHECKOUT_ONLY`, `FERNET_KEY`, `CRON_SECRET`, `FRENET_TOKEN`, `FRENET_SENDER_CEP`, `COSMOS_API_TOKEN`, `PAYMENT_GATEWAY`, `PAYMENT_SANDBOX`, `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `MP_WEBHOOK_SECRET`, `MP_USE_SANDBOX_LINK`, `MP_MAX_INSTALLMENTS` e `SECURE_HSTS_SECONDS`.

Valores nao foram copiados para este arquivo.

## Deploy e rollback

Fluxo autorizado nesta auditoria:

1. commits separados na branch de trabalho;
2. push sem force para o GitHub;
3. Pull Request em rascunho;
4. Preview Deployment da Vercel;
5. testes somente leitura no Preview, pois Preview e Production compartilham o banco atual;
6. nenhuma migration e nenhuma promocao para producao sem autorizacao explicita.

Rollback de codigo: reimplantar o commit de referencia `ef06608e6db3f3ae4b0802b01c245d5c7829054a` ou usar a branch de seguranca, sem reescrever historico. Rollback de banco somente a partir do backup validado e depois de ensaio isolado; a migration nova nao deve ser revertida automaticamente, pois a remocao de choices/defaults deve ser avaliada contra pedidos criados no novo modo.

## Preview

O artefato de codigo do commit `bfeb527` foi publicado somente como Preview e validado em leitura:

| Item | Valor |
| --- | --- |
| Pull Request | `https://github.com/MarcosPauloOtaviano/essencek/pull/11` |
| Alias estavel da branch | `https://essencek-git-feat-sincro-24b5f4-marcos-paulos-projects-7e938b4a.vercel.app` |
| Deployment validado | `https://essencek-lh54k6ij9-marcos-paulos-projects-7e938b4a.vercel.app` |
| Deployment ID | `dpl_DspdVPgFczPcMtqTd1fS5moq3VMm` |
| Estado | `Ready`, target `Preview` |
| Function | 44,06 MB em `gru1` |

Medicoes HTTP do Preview final, com query unica para separar MISS e HIT:

| Rota | MISS | HIT | HTML |
| --- | ---: | ---: | ---: |
| Home | 0,509 s | 0,216 s | 61.306 bytes |
| Catalogo | 0,304 s | 0,190 s | 63.042 bytes |
| Categoria Perfumes | 0,317 s | 0,202 s | 62.861 bytes |

As respostas foram `200`, passaram de `X-Vercel-Cache: MISS` para `HIT`, vieram de `gru1`, nao emitiram `Set-Cookie` e preservaram a separacao entre paginas publicas e estado de sessao. A primeira invocacao observada logo apos um deployment anterior levou 1,804 s, contra 35,59 s da Home de producao antes das correcoes.

Tres arquivos de midia persistida responderam `200` entre 0,197 s e 0,309 s. No navegador, 47 de 47 imagens da Home terminaram carregadas. Foram revistos Home, catalogo, categoria, produto, busca positiva, busca sem resultado, filtros, paginas institucionais e 404 customizada em desktop e celular. Nao houve erro no console, overflow horizontal ou imagem quebrada nas telas finais; catalogo e produto terminaram com zero violacoes e zero resultados inconclusivos no axe. As bolinhas dinamicas da Home permaneceram rolaveis e livres dos atalhos flutuantes no celular.

A busca negativa final respondeu `200`, mostrou zero cards e o estado vazio correto, sem criar cookie. O calculo de frete na pagina de produto retornou opcoes sem criar carrinho. Logs de erro do deployment nos 30 minutos finais: nenhum registro.

Login, carrinho, checkout, pedidos e painel nao foram alterados no Preview porque ele compartilha o banco de producao. Esses fluxos foram exercitados no ambiente local isolado descrito acima. O PR permanece em rascunho e a producao permanece no commit `ef06608e6db3f3ae4b0802b01c245d5c7829054a`, sem migration ou promocao, ate autorizacao explicita.

## Atualizacao de performance por miniaturas - 2026-08-06

O commit `609e134` acrescentou miniaturas sob demanda para as imagens persistidas, sem regravar o arquivo original ou alterar o banco. As telas publicas solicitam versoes de 160 px para categorias, 480 px para cards de produto e 960 px para slides; somente tamanhos permitidos sao aceitos. Arquivos invalidos, animados ou fora dos limites mantem a resposta original como fallback. Cada resposta de midia e imutavel e cacheavel na CDN por um ano.

Validacao direta de uma imagem de categoria anteriormente com 1.115,1 KB:

| Recurso | Resultado |
| --- | --- |
| Original | PNG de 1.115,1 KB |
| Miniatura `w=160` | PNG de 35.379 bytes |
| Reducao | 96,9% |
| CDN | `MISS` em 0,561 s, seguido de `HIT` em 0,200 s |
| Integridade | `200`, `image/png`, transparencia preservada, sem gravacao no banco |

O Preview do commit foi `https://essencek-7idi7codg-marcos-paulos-projects-7e938b4a.vercel.app`, deployment `dpl_RueTnYvsCVKzNSMAz81uqLt4scsP`, pronto em `gru1`. No navegador mobile de 390 x 844, categorias e cards usaram as URLs de miniatura corretas, as bolinhas permaneceram visiveis, e foram confirmados zero erros de console, imagens quebradas e overflow horizontal.

| Lighthouse de laboratorio | Antes | Depois |
| --- | ---: | ---: |
| Mobile Performance | 85 | 94 |
| Mobile FCP | 1,870 s | 1,776 s |
| Mobile LCP | 3,409 s | 3,008 s |
| Mobile transferido | 4,522 MB | 0,943 MB |
| Mobile TBT | 269 ms | 5 ms |
| Mobile CLS | 0 | 0 |

O desktop final registrou Performance 93, Acessibilidade 100, Boas praticas 100, FCP 0,673 s, LCP 0,931 s, TBT 0 ms, CLS 0 e 1,039 MB transferidos. A variacao do score de Performance entre execucoes desktop e sensivel a animacao visual e a simulacao de rede; os tempos de LCP, bytes transferidos e ausencia de bloqueio permanecem os sinais comparaveis. O SEO 63 no Preview decorre exclusivamente do `X-Robots-Tag: noindex` aplicado pela Vercel a deployments de Preview.

Foram adicionados quatro testes unitarios para URL, limites, transparencia, resposta HTTP e cache de miniaturas. A suite completa passou com 92 testes em 66,769 s; `check`, `check --deploy` com ambiente isolado, `makemigrations --check`, compilacao, Bandit, `pip-audit` e `collectstatic` passaram. Os relatorios Lighthouse foram gravados em `C:\EssenceKBackups\e2e-browser-20260805-224753`. No Windows, a CLI do Lighthouse pode avisar `EPERM` apenas ao limpar sua pasta temporaria depois de gravar o JSON; os relatorios foram confirmados e nao restaram processos headless do ensaio.

## Complemento de navegacao e desempenho - 2026-08-06

A captura recebida nesta data corresponde a producao, que permanece no commit antigo. As bolinhas dessa versao apontavam para consultas genericas como `?category=perfumes` e `?category=beleza-coreana`; esses slugs nao correspondem as categorias reais do catalogo e a busca de perfumes podia retornar vazia.

Os commits `13af6c2`, `0636aaf` e `134e146` corrigem a branch do PR sem alterar o banco:

- `Perfumes` agrega perfumes arabes, de nicho e para cabelo/corpo;
- `Beleza Asiatica` agrega skincare coreano e japones;
- URLs antigas continuam funcionais por compatibilidade e as rotas novas sao canonicas;
- `Decanter` e `Eletronicos` continuam ocultos enquanto nao houver produto publico em cada grupo;
- os cinco atalhos visiveis recebem destino real e os rotulos cabem integralmente nas bolinhas.

O Preview atualizado foi validado em leitura no alias estavel. Os cinco cliques da Home abriram, respectivamente, `/ofertas/`, `/categoria/perfumes/`, `/categoria/beleza-asiatica/`, `/destaques/` e `/pronta-entrega/`, todos com `200` e pelo menos um card. A verificacao de layout confirmou largura e altura de 64 px, sem overflow de texto. A suite completa do codigo passou com 93 testes em 62,814 s; apos o refinamento exclusivamente visual, os 7 testes de navegacao passaram novamente.

Medicoes HTTP com query unica, sem alterar estado:

| Rota | Producao antiga | Preview atualizado |
| --- | ---: | ---: |
| Home | 13,122 s | 0,450 s |
| Catalogo | 9,259 s | 0,430 s |

A producao continua lenta porque ainda executa o codigo anterior: inicializacao pesada com migracao no caminho da requisicao, funcao fora da regiao do banco Neon e sem cache publico seguro ou miniaturas responsivas. Para levar a melhora ao dominio publico e necessario autorizar explicitamente a promocao controlada do PR `#11`, confirmar as variaveis de producao, executar a migration pendente `orders/0006_alter_order_payment_method_alter_order_status.py` durante manutencao e validar somente leitura apos o deploy. Nenhuma dessas acoes foi executada nesta atualizacao.

## Otimizacao do carrinho - 2026-08-06

O commit `ad78643` reduz a latencia de inclusao sem alterar o contrato do carrinho ou o banco. O catalogo solicita o token CSRF em segundo plano apos a pagina ficar ociosa, evitando que o primeiro clique comum aguarde duas requisicoes sequenciais. As mutacoes de carrinho reutilizam a transacao ja aberta, a contagem usa `SUM(quantity)` e a inclusao deixa de bloquear a linha global do produto; os locks do carrinho e de itens existentes continuam protegendo alteracoes concorrentes do mesmo carrinho.

No perfil de banco de teste, o primeiro `cart_add` caiu de 14 para 12 comandos SQL e a duracao interna registrada foi 6,7 ms. A resposta AJAX agora inclui `Server-Timing`, permitindo separar processamento do servidor e rede depois da promocao. O Preview validou 16 controles de adicao, o script atualizado e a rota segura de CSRF com `200` em 0,247 s. A suite completa passou com 94 testes em 61,921 s. O Preview compartilha o banco de producao, portanto nenhum produto foi adicionado durante essa validacao.
