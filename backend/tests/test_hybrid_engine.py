# -*- coding: utf-8 -*-
"""Hybrid Training Engine: as cinco arquiteturas, os três roles e a rotação de vetor.

O que esta suíte protege
------------------------
Um motor de alta frequência erra de duas maneiras, e nenhuma das duas levanta exceção:

  1. **Repete o estímulo.** Seis sessões com "peito" em três delas produz três vezes o
     mesmo supino inclinado, em três máquinas diferentes, e chama isso de frequência.
     Os testes de rotação olham PADRÃO MOTOR e REGIÃO, e não o nome do exercício.

  2. **Confunde frequência com volume.** Cinco exposições de peitoral vira cinco treinos
     de peito, a recuperação não fecha, e o atleta para em três semanas achando que o
     problema é ele. Os testes de role prendem a microdose em 1 a 2 séries e cobram que a
     contagem de exposições saiba separar as duas coisas.

E protege uma terceira, que é a mais fácil de quebrar sem perceber: **nada disso pode
tocar quem não usa híbrido.** PPL, Upper/Lower, ABC e os programas já salvos precisam sair
byte a byte iguais ao que saíam antes da instalação.

Roda com `--noconftest`: nada aqui toca banco, rede ou relógio.
"""
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import engine  # noqa: E402
import training_engine_hybrid as hybrid  # noqa: E402
from hybrid_metadata import ALTA, regiao_de  # noqa: E402

hybrid.install(engine)

PERFIL = {
    "experience": "Avançado", "session_minutes": 70, "priorities": [], "baseline": [],
    "equipment": ["Academia completa"], "gym_complete": True, "goal": "Hipertrofia",
}


def perfil(**extra):
    return {**PERFIL, **extra}


def semana(split, dias=None, p=None):
    dias = dias or hybrid.ARQUITETURAS[split]["dias"]
    return engine.build_all_sessions(p or PERFIL, split, dias, 70)


def ex_de(sessao):
    return [engine.EXERCISE_INDEX[i["exercise_id"]] for i in sessao["exercises"]]


# ── As cinco arquiteturas existem e geram ───────────────────────────────────────────

@pytest.mark.parametrize("split", hybrid.TODAS)
def test_toda_arquitetura_gera_uma_semana_completa(split):
    arq = hybrid.ARQUITETURAS[split]
    sessoes = semana(split)
    assert len(sessoes) == arq["dias"]
    for s in sessoes:
        assert s["exercises"], f"{split} {s['label']} saiu vazio"
        assert s["label"] and s["demand"] in ("HIGH", "MODERATE", "LOW")
        assert s["architecture"] == split


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_nenhuma_sessao_e_curta_ou_absurda_demais(split):
    """Duas sessões de três exercícios não é híbrido, é um programa incompleto; doze é
    uma sessão que ninguém termina."""
    for s in semana(split):
        n = len(s["exercises"])
        minimo = 3 if s["demand"] == "LOW" else 4
        assert minimo <= n <= 11, f"{split} {s['label']}: {n} exercícios"


def test_seis_dias_oferecem_hibrido_e_sete_tambem():
    seis = engine.compatible_splits(6, "Avançado")
    sete = engine.compatible_splits(7, "Avançado")
    assert set(hybrid.DE_SEIS) <= set(seis)
    assert set(hybrid.DE_SETE) <= set(sete)


def test_quem_ja_treina_seis_dias_nao_muda_de_programa_sozinho():
    """O item 11 da especificação em um teste: não quebrar programa salvo.

    `determine_split` usa `options[0]` para quem não tem preferência gravada, e o
    formulário de avaliação nasce com `split_preference` vazio — ou seja, a maioria. Com
    as híbridas no começo da lista, todo atleta de seis dias abriria o aplicativo no dia
    seguinte com outro programa, no meio do ciclo, sem ter pedido nada.
    """
    for dias in (6, 7):
        padrao = engine.determine_split(dias, "Avançado", "Hipertrofia", None)
        assert not hybrid.e_hibrido(padrao), (
            f"{dias} dias sem preferência caiu em {padrao} sozinho")


def test_quem_pede_um_hibrido_recebe_o_hibrido():
    """Ele está na lista de compatíveis, então a preferência é honrada."""
    for chave in hybrid.DE_SEIS:
        assert engine.determine_split(6, "Avançado", "Hipertrofia", chave) == chave
    for chave in hybrid.DE_SETE:
        assert engine.determine_split(7, "Avançado", "Hipertrofia", chave) == chave


def test_o_hibrido_e_reconhecido_como_preferencia_gravada_no_perfil():
    """`profile_split_preference` só aceita chave que esteja em `SPLIT_LABELS`. Sem o
    registro, gravar `hybrid_02` no perfil seria o mesmo que não gravar nada."""
    for chave in hybrid.TODAS:
        assert engine.profile_split_preference({"split_preference": chave}) == chave


def test_quatro_dias_continuam_sem_hibrido():
    """O híbrido é uma resposta para 6 e 7 dias. Oferecê-lo para quem treina quatro seria
    vender uma arquitetura que precisa de frequência que a pessoa não tem."""
    for dias in (1, 2, 3, 4, 5):
        assert not (set(hybrid.TODAS) & set(engine.compatible_splits(dias, "Avançado")))


# ── 7x e o dia obrigatoriamente leve ────────────────────────────────────────────────

@pytest.mark.parametrize("split", hybrid.DE_SETE)
def test_a_semana_de_sete_dias_tem_pelo_menos_um_dia_LOW(split):
    """A especificação é explícita: em 7x, pelo menos um treino tem de ser de baixa
    fadiga. Sete sessões pesadas seguidas não é frequência alta, é dívida."""
    demandas = [s["demand"] for s in semana(split)]
    assert len(demandas) == 7
    assert "LOW" in demandas, demandas


@pytest.mark.parametrize("split", hybrid.DE_SETE)
def test_o_dia_leve_nao_tem_movimento_sistemico_pesado(split):
    """O D7 LOW existe para o corpo ser estimulado sem cobrar recuperação. Um agachamento
    ou um terra ali apagam a razão de ele existir."""
    for s in semana(split):
        if s["demand"] != "LOW":
            continue
        for e in ex_de(s):
            assert e.get("fatigue") != "high", \
                f"{split} {s['label']}: {e['name']} é fadiga alta num dia LOW"


def test_o_dia_leve_do_hybrid_04_e_so_de_isolador():
    """Esta arquitetura declara `so_isolador` no sétimo dia, e é o que a especificação
    descreve: crucifixo, pullover, lateral, extensora, flexora, tríceps, bíceps leve."""
    ultimo = semana(hybrid.HYBRID_04)[-1]
    assert ultimo["demand"] == "LOW"
    compostos = [e["name"] for e in ex_de(ultimo) if e.get("category") == "compound"]
    assert compostos == [], f"compostos no dia leve: {compostos}"


def test_no_dia_leve_toda_prescricao_e_microdose():
    for split in hybrid.DE_SETE:
        for s in semana(split):
            if not hybrid.ARQUITETURAS[split]["sessoes"][s["day"] - 1].get("so_isolador"):
                continue
            for i in s["exercises"]:
                assert i["role"] == hybrid.MICRODOSE, f"{s['label']}: {i}"
                assert i["sets"] <= 2, f"microdose com {i['sets']} séries"


# ── Rotação de vetor ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("split", hybrid.TODAS)
def test_nenhum_exercicio_aparece_tres_vezes_na_semana(split):
    contagem = Counter(i["exercise_id"] for s in semana(split) for i in s["exercises"])
    repetidos = {k: v for k, v in contagem.items() if v > 2}
    assert repetidos == {}, f"{split}: {repetidos}"


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_o_peitoral_nao_repete_o_mesmo_padrao_em_sessoes_seguidas(split):
    """O defeito que a especificação nomeia: D1 incline press, D2 incline press, D3
    incline press. A rotação tem de olhar padrão motor, e não nome de exercício."""
    _sem_padrao_repetido_em_sequencia(split, {"upper_chest", "mid_chest"}, "peitoral")


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_as_costas_nao_repetem_o_mesmo_padrao_em_sessoes_seguidas(split):
    _sem_padrao_repetido_em_sequencia(split, {"lats", "upper_back"}, "costas")


def _sem_padrao_repetido_em_sequencia(split, musculos, nome):
    """O que se cobra aqui é o EXERCÍCIO e a REGIÃO, e não o padrão motor cru.

    A primeira versão deste teste exigia conjuntos de padrão diferentes entre sessões
    consecutivas do grupo, e falhou — corretamente. Medindo: TODO exercício de espessura
    do catálogo é `horizontal_pull`, os oito. Exigir padrão diferente entre duas sessões
    de espessura é exigir o impossível, e a própria especificação do HYBRID 01 coloca
    espessura no D2 e no D4.

    O defeito que a especificação nomeia é outro: "D1 incline press, D2 incline press,
    D3 incline press". Isso é o mesmo EXERCÍCIO, ou a mesma REGIÃO três vezes seguidas.
    É isso que se mede.
    """
    from hybrid_metadata import regiao_de as _regiao
    anteriores_ids, regioes_seguidas = set(), []
    for s in semana(split):
        # Microdose fica de fora da regra de repetição, e o motivo é do catálogo, não do
        # motor: o vetor largura tem UM único isolador (`cable-straight-arm-pulldown`),
        # e o dia leve só aceita isolador. Quando as duas regras se cruzam não existe
        # escolha que satisfaça as duas, e uma série leve repetida não é o defeito que a
        # especificação nomeia — ela fala de trabalho principal repetido. O teste logo
        # abaixo prende essa escassez para ela não passar despercebida.
        do_grupo = [engine.EXERCISE_INDEX[i["exercise_id"]] for i in s["exercises"]
                    if i.get("role") != hybrid.MICRODOSE
                    and engine.EXERCISE_INDEX[i["exercise_id"]]["primary_muscle"] in musculos]
        if not do_grupo:
            continue
        ids = {e["id"] for e in do_grupo}
        repetidos = ids & anteriores_ids
        assert not repetidos, (
            f"{split} {s['label']}: {nome} repetiu o exercício da sessão anterior: {repetidos}")

        regioes = frozenset(_regiao(e) for e in do_grupo)
        regioes_seguidas.append(regioes)
        if len(regioes_seguidas) >= 3:
            assert len(set(regioes_seguidas[-3:])) > 1, (
                f"{split} {s['label']}: {nome} ficou em {set(regioes)} por três sessões seguidas")
        anteriores_ids = ids


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_o_peitoral_aparece_em_pelo_menos_duas_regioes_diferentes(split):
    """Se todas as aparições fossem clavicular, seria frequência sem rotação."""
    regioes = {regiao_de(e) for s in semana(split) for e in ex_de(s)
               if e["primary_muscle"] in ("upper_chest", "mid_chest")}
    assert len(regioes) >= 2, f"{split}: peitoral só em {regioes}"


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_as_costas_cobrem_largura_E_espessura_na_semana(split):
    """Uma semana de costas só com puxada, ou só com remada, é meia semana de costas."""
    from hybrid_metadata import ESPESSURA, LARGURA
    regioes = {regiao_de(e) for s in semana(split) for e in ex_de(s)
               if e["primary_muscle"] in ("lats", "upper_back")}
    assert {LARGURA, ESPESSURA} <= regioes, f"{split}: cobre só {regioes}"


# ── Roles ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("split", hybrid.TODAS)
def test_todo_exercicio_carrega_um_role_valido(split):
    for s in semana(split):
        for i in s["exercises"]:
            assert i["role"] in hybrid.ROLES, i
            assert i["role_label"]


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_microdose_e_uma_ou_duas_series_sempre(split):
    """É o número que faz a alta frequência caber. Se a periodização ou a demanda
    pudessem inflá-lo, a microdose viraria mais um exercício."""
    for s in semana(split):
        for i in s["exercises"]:
            if i["role"] == hybrid.MICRODOSE:
                assert 1 <= i["sets"] <= 2, f"{s['label']}: {i}"


def test_microdose_pede_menos_esforco_que_o_principal():
    """RIR 2–4 contra 1–3: microdose é estímulo, não é trabalho até perto da falha."""
    assert hybrid.RIR_POR_ROLE[hybrid.MICRODOSE] == "2–4"
    assert hybrid.RIR_POR_ROLE[hybrid.PRIMARY] == "1–3"


def test_nenhum_role_prescreve_falha_automatica():
    """A especificação é explícita: falha não é regra automática em nenhuma série."""
    for split in hybrid.TODAS:
        for s in semana(split):
            for i in s["exercises"]:
                assert str(i["rir"]).strip() not in ("0", "0–0"), f"{s['label']}: {i}"


def test_a_microdose_mantem_o_peitoral_frequente_sem_virar_treino_de_peito():
    """O número que a especificação pede que o FORGE saiba mostrar: "peitoral, 5
    exposições semanais", sem que isso signifique cinco sessões pesadas de peito."""
    sessoes = semana(hybrid.HYBRID_03)
    exposicoes = engine.hybrid_exposures(sessoes)
    peito = {"upper_chest": 0, "mid_chest": 0}
    for m in peito:
        peito[m] = exposicoes.get(m, {}).get("exposicoes", 0)
    total = sum(peito.values())
    assert total >= 4, f"peitoral com só {total} exposições: {peito}"

    # E a conta precisa saber separar: nem toda exposição é sessão relevante de peito.
    pesadas = sum(exposicoes.get(m, {}).get(hybrid.PRIMARY, 0) for m in peito)
    assert pesadas < total, "todas as exposições viraram trabalho principal"


def test_a_contagem_de_exposicoes_usa_o_role_mais_forte_da_sessao():
    """Se um músculo aparece como principal E como microdose no mesmo dia, aquele dia
    conta como principal — senão a média desce sozinha e a leitura mente para baixo."""
    falsas = [{"exercises": [
        {"exercise_id": "bb-bench-press", "role": hybrid.MICRODOSE},
        {"exercise_id": "pec-deck", "role": hybrid.PRIMARY}]}]
    contagem = engine.hybrid_exposures(falsas)
    assert contagem["mid_chest"]["exposicoes"] == 1
    assert contagem["mid_chest"][hybrid.PRIMARY] == 1
    assert contagem["mid_chest"][hybrid.MICRODOSE] == 0


# ── Restrições articulares ──────────────────────────────────────────────────────────

def test_sensibilidade_de_tendao_reduz_a_demanda_de_biceps_da_semana():
    """Preferência e penalidade, não blacklist: a semana continua tendo costas, mas o
    volume migra para pegada neutra e movimento estabilizado.

    A conta é PONDERADA, e não "quantos exercícios de demanda alta". Medindo a semana sem
    restrição: zero exercícios de demanda alta, seis de média e quatro de baixa. Contar só
    os altos comparava zero com zero, e o teste passava sem medir coisa nenhuma.
    """
    from hybrid_metadata import MEDIA, demanda_de_biceps
    peso = {ALTA: 2, MEDIA: 1}

    def carga_de_biceps(p):
        return sum(peso.get(demanda_de_biceps(e), 0)
                   for s in semana(hybrid.HYBRID_02, p=p) for e in ex_de(s)
                   if e["primary_muscle"] in ("lats", "upper_back", "biceps"))

    sem = carga_de_biceps(PERFIL)
    com = carga_de_biceps(perfil(limitations={"bicepsTendonSensitivity": True}))
    assert sem > 0, "a semana de referência não cobra bíceps: o teste não mede nada"
    assert com < sem, f"com restrição {com}, sem restrição {sem}"


def test_a_restricao_nao_apaga_as_costas_da_semana():
    """Uma penalidade que remove o grupo inteiro é uma blacklist com outro nome."""
    p = perfil(limitations={"bicepsTendonSensitivity": True})
    costas = [e for s in semana(hybrid.HYBRID_02, p=p) for e in ex_de(s)
              if e["primary_muscle"] in ("lats", "upper_back")]
    assert len(costas) >= 6, f"só {len(costas)} exercícios de costas"


def test_dor_relatada_tira_o_exercicio_da_selecao():
    """Aqui não é penalidade. Insistir num movimento que dói é o caminho para a lesão que
    tira o atleta por meses."""
    doido = "bb-bench-press"
    p = perfil(painful_exercises=[doido])
    ids = {i["exercise_id"] for s in semana(hybrid.HYBRID_01, p=p) for i in s["exercises"]}
    assert doido not in ids


def test_a_restricao_escrita_em_texto_livre_tambem_vale():
    """`limitations` já existe no perfil como lista de texto, preenchida na avaliação. Ela
    nunca tinha chegado à seleção de exercício — nem essa nem nenhuma outra."""
    p = perfil(limitations=["Dor no tendão do bíceps ao puxar supinado"])
    assert hybrid.sensibilidade_de_biceps(p) is True


# ── Nada disso pode tocar quem não usa híbrido ──────────────────────────────────────

@pytest.mark.parametrize("split,dias", [
    (engine.SPLIT_PUSH_PULL_LEGS, 3), (engine.SPLIT_UPPER_LOWER, 4),
    (engine.SPLIT_FULL_BODY, 3), (engine.SPLIT_ABC, 3), (engine.SPLIT_ABCD, 4),
])
def test_divisao_classica_nao_passa_por_nenhuma_linha_do_hibrido(split, dias):
    """A primeira linha do construtor delega. Se um dia alguém inverter essa ordem, o
    programa de quem treina PPL muda sozinho, e ninguém liga uma coisa à outra."""
    sessoes = engine.build_all_sessions(PERFIL, split, dias, 70)
    assert len(sessoes) == dias
    for s in sessoes:
        assert s["exercises"]
        assert "architecture" not in s, "sessão clássica recebeu campo do híbrido"
        for i in s["exercises"]:
            assert "role" not in i, "exercício clássico recebeu role do híbrido"


def test_os_rotulos_das_divisoes_antigas_continuam_intactos():
    for chave in ("ppl", "upper_lower", "full_body", "abc", "abcd", "abcde"):
        assert chave in engine.SPLIT_LABELS
        assert not engine.SPLIT_LABELS[chave].startswith("Híbrido")


def test_instalar_duas_vezes_nao_empilha_camada():
    antes = engine.build_all_sessions
    hybrid.install(engine)
    assert engine.build_all_sessions is antes


# ── Escolha automática ──────────────────────────────────────────────────────────────

def test_sete_dias_caem_na_arquitetura_que_tem_dia_leve_obrigatorio():
    escolha = hybrid.escolher_arquitetura(7, "Avançado", [])
    assert escolha in hybrid.DE_SETE
    assert "LOW" in [s["demand"] for s in hybrid.ARQUITETURAS[escolha]["sessoes"]]


def test_especializacao_em_peito_ou_costas_cai_na_arquitetura_que_gira_os_dois():
    assert hybrid.escolher_arquitetura(6, "Avançado", ["upper_chest"]) == hybrid.HYBRID_02
    assert hybrid.escolher_arquitetura(6, "Avançado", ["lats"]) == hybrid.HYBRID_02


def test_quem_nao_treina_seis_ou_sete_dias_nao_recebe_hibrido():
    for dias in (0, 3, 4, 5, 8):
        assert hybrid.escolher_arquitetura(dias, "Avançado", []) is None


def test_pedir_um_hibrido_de_sete_treinando_seis_nao_e_atendido():
    """Não é preferência, é um programa que não existe: faltaria um dia inteiro."""
    escolha = hybrid.escolher_arquitetura(6, "Avançado", [], preferencia=hybrid.HYBRID_04)
    assert escolha != hybrid.HYBRID_04
    assert hybrid.ARQUITETURAS[escolha]["dias"] == 6


# ── O que o catálogo limita, e o motor não pode consertar ───────────────────────────

def test_a_largura_tem_um_unico_isolador_no_catalogo():
    """Este teste existe para uma escassez não virar mistério.

    O dia leve das arquiteturas de sete dias só aceita isolador. O vetor largura tem um
    isolador só em 134 exercícios, então quando ele já apareceu na semana, o dia leve o
    repete — não há segunda opção que seja isolador de largura.

    Isso é limite de catálogo, e não defeito de motor. Se um dia entrar outro isolador de
    largura (uma máquina de pullover, por exemplo), este teste falha e avisa que a
    exceção documentada logo acima deixou de ser necessária.
    """
    idx = hybrid._indice_por_vetor(engine.EXERCISES)
    from hybrid_metadata import LARGURA
    isoladores = [e for e in idx[LARGURA]
                  if engine.EXERCISE_INDEX[e].get("category") == "isolation"]
    assert isoladores == ["cable-straight-arm-pulldown"], isoladores


def test_o_trabalho_principal_prefere_composto_quando_ha_escolha():
    """O principal da sessão é o movimento composto — quando o vetor oferece um.

    A primeira versão deste teste exigia metade dos principais compostos em toda sessão, e
    falhou corretamente: `hybrid_03 Lower B` tem flexão de joelho como principal, e TODA
    flexão de joelho do catálogo é isolador. Exigir composto ali é exigir o impossível.

    O que se mede é a correção de verdade: no vetor largura, que tem oito compostos e um
    isolador, o trabalho principal não pode levar justamente o isolador. Era o que
    acontecia em demanda média, e era isso que deixava o dia leve sem opção.
    """
    from hybrid_metadata import LARGURA, regiao_de as _regiao
    for split in hybrid.TODAS:
        for s in semana(split):
            if s["demand"] == "LOW":
                continue
            principais_de_largura = [
                engine.EXERCISE_INDEX[i["exercise_id"]] for i in s["exercises"]
                if i["role"] == hybrid.PRIMARY
                and _regiao(engine.EXERCISE_INDEX[i["exercise_id"]]) == LARGURA]
            isoladores = [e["name"] for e in principais_de_largura
                          if e.get("category") == "isolation"]
            assert not isoladores, (
                f"{split} {s['label']}: isolador de largura como trabalho principal: "
                f"{isoladores}")


# ── Qualidade de volume ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("split", hybrid.TODAS)
def test_nenhum_musculo_essencial_fica_com_zero_volume(split):
    """O validador do v5 apontou isto nas cinco arquiteturas de uma vez: deltoide
    anterior, adutores e abdômen com zero séries na semana.

    Não era escolha, era esquecimento — a especificação fala em "deltoides" nos dias de
    superior e eu só tinha posto lateral e posterior. Uma semana de seis a sete sessões
    que não toca num grupo inteiro é um programa incompleto, não um programa focado.
    """
    volume = engine.count_weekly_sets_per_muscle(semana(split))
    for musculo in ("front_delts", "side_delts", "rear_delts", "adductors", "abs",
                    "biceps", "triceps", "calves"):
        assert volume.get(musculo, 0) > 0, f"{split}: {musculo} com zero série"


@pytest.mark.parametrize("split", hybrid.TODAS)
def test_nenhum_musculo_estoura_o_teto_de_volume_semanal(split):
    """Medido antes da correção: quadríceps em 18 a 21 séries, contra um teto de 12 no
    nível normal. Alta frequência que vira alto volume é exatamente como estes programas
    quebram a recuperação de quem os segue."""
    teto = engine.VOLUME_TIERS["priority"]["max_sets"]
    volume = engine.count_weekly_sets_per_muscle(semana(split))
    estourados = {m: n for m, n in volume.items() if n > teto}
    assert estourados == {}, f"{split}: {estourados} (teto {teto})"
