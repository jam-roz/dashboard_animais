# Relatório de qualidade e limpeza - AAC Shelter Outcomes (todas as espécies)

## Resumo

- Linhas de entrada: **78,256** -> saída: **78,246** (10 duplicatas removidas)
- Colunas de entrada: **12** -> saída: **38**
- Período dos desfechos: **2013-10-01** a **2018-02-01**
- Animais distintos: **70,855** (um mesmo animal pode ter mais de um desfecho)
- Validações finais: **todas OK**

## Linhas por espécie

| Espécie | Desfechos | % |
|---|---:|---:|
| Dog | 44,240 | 56.5% |
| Cat | 29,415 | 37.6% |
| Other | 4,248 | 5.4% |
| Bird | 334 | 0.4% |
| Livestock | 9 | 0.0% |

## Problemas encontrados e ações

| # | Problema | Linhas afetadas | Ação |
|---|---|---:|---|
| 1 | Texto 'NULL' em `age_upon_outcome` | 8 | convertido para nulo de verdade |
| 2 | Espaços sobrando em `name` | 16 | strip + colapso de espaços |
| 3 | Texto 'NULL' em `sex_upon_outcome` | 2 | convertido para nulo de verdade |
| 4 | Linhas 100% duplicadas | 10 | removidas (mantida a primeira ocorrência) |
| 5 | Data de nascimento ausente/posterior ao desfecho | 8 | nascimento e tudo que deriva dele (idade, faixa etária, filhote/adulto) viram nulo/Unknown; linha mantida e marcada em `dob_invalid` |
| 6 | `monthyear` era um duplicado do datetime completo | 78,246 | agora é o 1º dia do mês (AAAA-MM-01) - agrega corretamente por mês |
| 7 | Horário do desfecho exatamente 00:00:00 ou 09:00:00 (volume anômalo) | 4,063 | mantido, mas marcado em `outcome_time_unreliable` - filtre ao analisar por hora do dia |
| 8 | Plural errado em `age_upon_outcome` ('1 weeks') | 513 | corrigido para singular |
| 9 | '0 years' em `age_upon_outcome` (animais com 0 dias) | 87 | rótulo -> '0 days' |
| 10 | `age_upon_outcome` nulo com nascimento válido | 8 | rótulo mantido nulo; a idade exata está em `age_days` / `age_years` |
| 11 | Faixa etária e filhote/adulto derivados da idade exata | 78,246 | `age_group` em faixas de 2 anos ('0-1 yrs'...) + `age_group_order`; `life_stage` = Young se idade <= 182 dias |
| 12 | `sex_upon_outcome` nulo ('NULL') | 2 | preenchido com 'Unknown' |
| 13 | `sex` e `spay_neuter` derivados de `sex_upon_outcome` | 78,246 | Female/Male e Yes/No; Unknown permanece Unknown |
| 14 | Capitalização inconsistente: 'Rto-Adopt' (sigla) | 150 | padronizado para 'RTO-Adopt' |
| 15 | `outcome_type` nulo | 12 | preenchido com 'Unknown' (lote sem desfecho registrado) |
| 16 | `outcome_subtype` nulo (sem subtipo) | 42,288 | preenchido com 'Not specified' (facilita filtros) |
| 17 | Nomes placeholder ('X', 'U', 'No Name') | 74 | convertidos para nulo |
| 18 | Nomes em CAIXA ALTA | 48 | convertidos para Title Case |
| 19 | Prefixo '*' no nome (convenção do AAC: nome dado pelo abrigo) | 18,603 | asterisco removido; informação preservada em `name_assigned_by_shelter` |
| 20 | Raça mista com a mesma raça nas duas posições (ex.: 'x/x') | 20 | breed2 -> nulo |
| 21 | Raça normalizada | 78,246 | minúsculas, sufixo 'Mix' removido e guardado em `is_mix`, mistura 'a/b' separada em `breed1`/`breed2` |
| 22 | Cor separada em cor-base e padrão | 78,246 | `color1`/`color2` (antes/depois da '/'), `coat` (cor-base: 'brown tabby' -> 'brown') e `coat_pattern` ('tabby', 'brindle'...) |

## Nulos restantes (todos esperados)

| Coluna | Nulos | % | Motivo |
|---|---:|---:|---|
| `name` | 23,957 | 30.62% | animais sem nome registrado (use `has_name`) |
| `date_of_birth` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `dob_year` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `dob_month` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `dob_monthyear` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `age_upon_outcome` | 16 | 0.02% | rótulo ausente na origem ('NULL') ou nascimento inválido; use `age_days` |
| `age_days` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `age_years` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `age_group_order` | 8 | 0.01% | consequência de nascimento inválido (`dob_invalid`) |
| `breed2` | 71,143 | 90.92% | só existe em raças mistas 'a/b' |
| `color2` | 37,279 | 47.64% | animais de uma cor só |

## Pontos de atenção para o dashboard

- **Último mês incompleto:** a base termina no início de fevereiro/2018 - o mês tem poucos registros e distorce séries temporais.
- **Hora do dia:** use `outcome_time_unreliable = False` em gráficos por hora (00:00 e 09:00 aparecem em volume anômalo).
- **Granularidade:** cada linha é um *desfecho*, não um animal. Para contar animais use `COUNT DISTINCT animal_id`.
- **Espécies não são comparáveis sem cuidado:** sexo 'Unknown' é raro em cães (~0,5%) e comum em gatos (~9%) e outros animais (~85%); transferências e devoluções ao tutor têm pesos muito diferentes entre espécies.
- **Filhote:** `life_stage = Young` = até 182 dias (~6 meses), regra herdada da base de gatos; para cães, muitos filhotes de 6 a 12 meses contam como adultos.
- **Idade:** use `age_days` / `age_years` (exatas); `age_group` tem faixas de 2 anos e `age_group_order` dá a ordem.

## Dicionário das colunas derivadas

| Coluna | Descrição |
|---|---|
| `has_name`, `name_assigned_by_shelter` | tem nome; nome começava com `*` (dado pelo abrigo) |
| `outcome_date`, `monthyear` | data do desfecho; 1º dia do mês do desfecho |
| `outcome_time_unreliable` | horário 00:00:00 ou 09:00:00 exato |
| `dob_year`, `dob_month`, `dob_monthyear`, `dob_invalid` | partes do nascimento; nascimento ausente ou posterior ao desfecho |
| `age_days`, `age_years` | idade exata no desfecho |
| `age_group`, `age_group_order`, `life_stage` | faixa etária (2 anos), ordem e filhote (Young) / adulto (Adult) |
| `sex`, `spay_neuter` | derivados de `sex_upon_outcome` |
| `breed1`, `breed2`, `is_mix` | raças separadas (minúsculas) e indicador de mistura |
| `color1`, `color2`, `coat`, `coat_pattern` | cores, cor-base e padrão (tabby, brindle, ...) |
