# -*- coding: utf-8 -*-
"""FORGE — as rotas do Forge Food Card.

A camada é deliberadamente fina. Ela faz três coisas:

  LÊ a refeição que o atleta já registrou, sem recalcular nada;
  DECIDE ícone, macro principal e posição inicial, chamando `food_card.py`;
  GUARDA o resultado, para o atleta poder sair do editor e voltar.

A foto reusa `visual_storage`, que é a infraestrutura que o FORGE já tem para foto de
pessoa: bucket privado compatível com S3, chave privada no documento e URL assinada de
validade curta na hora do acesso. Criar um segundo caminho de armazenamento para a mesma
classe de dado — imagem enviada pelo atleta — seria manter duas políticas de retenção
para a mesma coisa.
"""
import logging
import uuid
from datetime import date as CalendarDate, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

import food_card as motor
import visual_storage
from auth import get_current_user
from billing_plans import ALIMENTACAO
from entitlements import exigir_capacidade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/food-card", tags=["food-card"])

VERSAO_DO_MODELO = "forge-food-v1"

# O nome do objeto dentro do prefixo do Food Card.
#
# `visual_storage.chave_da_foto` valida o "ângulo" contra frente, costas, esquerda e
# direita, que é o vocabulário de foto de CORPO. Foto de prato não tem ângulo, e passar
# "front" para ela seria gravar uma informação falsa no caminho do objeto só para
# atravessar uma validação.
#
# O prefixo, esse sim, é reusado: `prefixo_da_avaliacao` põe o objeto sob
# `<prefixo>/<user_id>/<card_id>/`, então apagar o atleta inteiro continua sendo uma
# varredura por prefixo e o Food Card vai junto sem código próprio de exclusão.
NOME_DO_OBJETO = "prato.jpg"


def _chave_da_foto(cfg, user_id: str, card_id: str) -> str:
    return visual_storage.prefixo_da_avaliacao(cfg.prefixo, user_id, card_id) + NOME_DO_OBJETO


# ── Modelos ─────────────────────────────────────────────────────────────────────────

class PosicaoIn(BaseModel):
    """Coordenadas normalizadas. Pixel aqui não sobreviveria à troca de tela."""
    cardX: float = Field(ge=0.0, le=1.0)
    cardY: float = Field(ge=0.0, le=1.0)
    anchorX: float = Field(ge=0.0, le=1.0)
    anchorY: float = Field(ge=0.0, le=1.0)


class ItemIn(PosicaoIn):
    foodId: Optional[str] = None
    primaryMacro: Optional[str] = None


class TransformacaoIn(BaseModel):
    scale: float = Field(default=1.0, ge=1.0, le=4.0)
    offsetX: float = Field(default=0.0, ge=-1.0, le=1.0)
    offsetY: float = Field(default=0.0, ge=-1.0, le=1.0)


class CriarIn(BaseModel):
    date: CalendarDate
    # De onde vem a refeição: um registro do diário livre (`entry_id`) ou uma refeição do
    # plano (`meal_index`). Os dois caminhos já existem na Nutrição.
    entry_id: Optional[str] = None
    meal_index: Optional[int] = Field(default=None, ge=0, le=9)
    # Quais alimentos viram card. Vazio significa "os primeiros que couberem".
    food_ids: List[str] = Field(default_factory=list, max_length=motor.MAXIMO_DE_ITENS)


class AtualizarIn(BaseModel):
    items: Optional[List[ItemIn]] = Field(default=None, max_length=motor.MAXIMO_DE_ITENS)
    imageTransform: Optional[TransformacaoIn] = None


# ── Leitura da refeição registrada ──────────────────────────────────────────────────

async def _refeicao_registrada(db, perfil_id: str, dados: CriarIn) -> Dict[str, Any]:
    """O `actual` da refeição: alimentos e totais, exatamente como foram gravados.

    Não recalcula nada. Dois totais diferentes para a mesma comida destroem a confiança
    nos dois, e aqui o segundo total apareceria numa peça que o atleta publica.
    """
    dia = dados.date.isoformat()
    if dados.entry_id:
        linha = await db.nutrition_consumed_extras.find_one(
            {"profile_id": perfil_id, "date": dia, "entry_id": dados.entry_id}, {"_id": 0})
    elif dados.meal_index is not None:
        linha = await db.nutrition_adherence.find_one(
            {"profile_id": perfil_id, "date": dia, "meal_index": dados.meal_index},
            {"_id": 0}, sort=[("created_at", -1)])
    else:
        raise HTTPException(422, "Informe a refeição: entry_id ou meal_index.")

    atual = (linha or {}).get("actual") or {}
    if not atual.get("foods"):
        raise HTTPException(
            404, "Essa refeição não tem alimentos pesados. Registre o que você comeu "
                 "para criar o Food Card.")
    return atual


# ── Rotas ───────────────────────────────────────────────────────────────────────────

@router.get("/meal")
async def alimentos_da_refeicao(request: Request, date: CalendarDate,
                                entry_id: Optional[str] = None,
                                meal_index: Optional[int] = None,
                                user=Depends(get_current_user)):
    """Os alimentos disponíveis para virar card, já com ícone e macro sugeridos.

    A tela precisa disto ANTES de criar o Food Card: com mais de quatro alimentos, o
    atleta escolhe quais destacar.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    atual = await _refeicao_registrada(
        db, user["id"], CriarIn(date=date, entry_id=entry_id, meal_index=meal_index))
    alimentos = []
    for a in atual["foods"]:
        icone = motor.icone_de(a.get("name"))
        alimentos.append({
            "foodId": a.get("food_id"), "name": a.get("name"),
            "quantity": a.get("grams"), "unit": "g",
            "calories": a.get("kcal"), "protein": a.get("protein_g"),
            "carbs": a.get("carbs_g"), "fat": a.get("fat_g"),
            "iconKey": icone, "descriptionKey": motor.descricao_de(icone),
            "primaryMacro": motor.macro_principal(a, icone),
        })
    return {"foods": alimentos, "summary": motor.resumo(atual.get("totals") or {}),
            "maxItems": motor.MAXIMO_DE_ITENS}


@router.post("")
async def criar(dados: CriarIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    alvo = user["id"]
    atual = await _refeicao_registrada(db, alvo, dados)

    alimentos = atual["foods"]
    if dados.food_ids:
        escolhidos = [a for a in alimentos if a.get("food_id") in dados.food_ids]
        if not escolhidos:
            raise HTTPException(422, "Nenhum dos alimentos escolhidos está nessa refeição.")
        alimentos = escolhidos

    agora = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "userId": alvo,
        "mealDate": dados.date.isoformat(),
        "entryId": dados.entry_id,
        "mealIndex": dados.meal_index,
        "imageKey": None,
        "imageTransform": {"scale": 1.0, "offsetX": 0.0, "offsetY": 0.0},
        "templateVersion": VERSAO_DO_MODELO,
        "items": motor.montar_itens(alimentos),
        # O resumo usa o total da refeição COMPLETA, e não a soma dos quatro destacados.
        "summary": motor.resumo(atual.get("totals") or {}),
        "createdAt": agora,
        "updatedAt": agora,
    }
    await db.food_cards.insert_one(dict(doc))
    return doc


@router.get("/{card_id}")
async def ler(card_id: str, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    doc = await db.food_cards.find_one({"id": card_id, "userId": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Esse Food Card não existe.")
    doc["imageUrl"] = _url_da_foto(doc.get("imageKey"))
    return doc


@router.get("")
async def listar(request: Request, user=Depends(get_current_user), limit: int = 20):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    docs = await db.food_cards.find({"userId": user["id"]}, {"_id": 0}) \
        .sort("createdAt", -1).to_list(max(1, min(50, limit)))
    for d in docs:
        d["imageUrl"] = _url_da_foto(d.get("imageKey"))
    return {"cards": docs}


@router.put("/{card_id}")
async def atualizar(card_id: str, dados: AtualizarIn, request: Request,
                    user=Depends(get_current_user)):
    """Guarda o que o atleta arrastou.

    Só posição e enquadramento mudam por aqui. Nome, quantidade e macro vêm da refeição
    registrada e não são editáveis por esta rota — deixá-los editáveis abriria a porta para
    uma peça publicada com número que a refeição não tem.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    doc = await db.food_cards.find_one({"id": card_id, "userId": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Esse Food Card não existe.")

    mudancas: Dict[str, Any] = {"updatedAt": datetime.now(timezone.utc).isoformat()}
    if dados.items is not None:
        if len(dados.items) != len(doc["items"]):
            raise HTTPException(422, "A quantidade de alimentos não confere.")
        itens = []
        for guardado, recebido in zip(doc["items"], dados.items):
            item = dict(guardado)
            item.update({"cardX": recebido.cardX, "cardY": recebido.cardY,
                         "anchorX": recebido.anchorX, "anchorY": recebido.anchorY})
            if recebido.primaryMacro in motor.MACROS:
                item["primaryMacro"] = recebido.primaryMacro
            itens.append(item)
        mudancas["items"] = itens
    if dados.imageTransform is not None:
        mudancas["imageTransform"] = dados.imageTransform.model_dump()

    await db.food_cards.update_one({"id": card_id, "userId": user["id"]}, {"$set": mudancas})
    return {**doc, **mudancas, "imageUrl": _url_da_foto(doc.get("imageKey"))}


@router.post("/{card_id}/photo")
async def enviar_foto(card_id: str, request: Request, user=Depends(get_current_user),
                      photo: UploadFile = File(...)):
    """Guarda a foto do prato no mesmo bucket privado das fotos de avaliação.

    Sem credencial de armazenamento configurada, isto recusa com uma mensagem clara em vez
    de fingir que guardou — `visual_storage` se declara desligado nesse caso, e um Food
    Card que perde a foto ao recarregar seria pior do que não deixar criar.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    doc = await db.food_cards.find_one({"id": card_id, "userId": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Esse Food Card não existe.")

    cfg = visual_storage.carregar_configuracao()
    # `carregar_configuracao` devolve um dataclass, que é sempre verdadeiro: quem diz se o
    # armazenamento está ligado é `cfg.ativo`. Testar só o objeto deixava o código seguir
    # sem credencial e estourar `AttributeError` em `put_object` de um cliente nulo.
    if not cfg or not cfg.ativo:
        raise HTTPException(503, "O armazenamento de fotos não está configurado.")

    dados = await photo.read()
    if len(dados) > visual_storage.TAMANHO_MAXIMO_BYTES:
        raise HTTPException(413, "Essa foto é grande demais. Envie até 8 MB.")
    try:
        mime = visual_storage.validar_foto(dados)
    except ValueError as erro:
        raise HTTPException(422, str(erro))

    cli = visual_storage.cliente(cfg)
    chave = _chave_da_foto(cfg, user["id"], card_id)
    extras = {} if cfg.endpoint else {"ServerSideEncryption": "AES256"}
    cli.put_object(Bucket=cfg.bucket, Key=chave, Body=dados, ContentType=mime, **extras)
    await db.food_cards.update_one({"id": card_id, "userId": user["id"]}, {"$set": {
        "imageKey": chave, "updatedAt": datetime.now(timezone.utc).isoformat()}})
    return {"imageKey": chave, "imageUrl": _url_da_foto(chave)}


@router.get("/{card_id}/photo-check")
async def conferir_foto(card_id: str, request: Request, user=Depends(get_current_user)):
    """Por que a foto do prato não aparece. Perguntas que só o servidor sabe responder.

    Existe para encurtar um diagnóstico que, sem isto, é impossível: do navegador, uma foto
    que não carrega é indistinguível de uma foto que nunca subiu — o `<img>` falha igual nos
    dois casos, e o fundo preto da moldura é o mesmo. O atleta relata "fica tudo preto" e
    não há como saber se o objeto sumiu, se a credencial caiu ou se o prazo da URL venceu.

    Não devolve credencial, endereço do bucket nem caminho do objeto. Só o que ajuda a
    decidir onde procurar:

      `temChave`    o documento sabe onde a foto deveria estar;
      `existe`      o armazenamento confirma que o objeto está lá;
      `assinavel`   dá para gerar um endereço de leitura;
      `validade`    por quantos segundos esse endereço vale.

    `validade` é o que fecha o caso mais provável de todos. O padrão é 300 segundos, e
    montar um Food Card leva mais que isso; se alguém configurou um valor pequeno, a URL
    vence antes de a tela terminar de carregar e nada na interface conseguiria explicar.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    doc = await db.food_cards.find_one({"id": card_id, "userId": user["id"]},
                                       {"_id": 0, "imageKey": 1})
    if not doc:
        raise HTTPException(404, "Esse Food Card não existe.")

    chave = doc.get("imageKey")
    cfg = visual_storage.carregar_configuracao()
    resposta = {"temChave": bool(chave), "armazenamentoAtivo": bool(cfg and cfg.ativo),
                "existe": False, "assinavel": False, "validade": None, "motivo": None}
    if not chave:
        resposta["motivo"] = "sem_foto"
        return resposta
    if not cfg or not cfg.ativo:
        resposta["motivo"] = "armazenamento_desligado"
        return resposta

    resposta["validade"] = cfg.url_segundos
    try:
        cli = visual_storage.cliente(cfg)
        cli.head_object(Bucket=cfg.bucket, Key=chave)
        resposta["existe"] = True
    except Exception as erro:
        # O texto da exceção pode trazer o bucket e a chave. Só o tipo sai daqui.
        logger.warning("foto do food card %s nao encontrada no armazenamento: %s",
                       card_id, type(erro).__name__)
        resposta["motivo"] = "objeto_ausente"
        return resposta

    if _url_da_foto(chave):
        resposta["assinavel"] = True
    else:
        resposta["motivo"] = "falha_ao_assinar"
    return resposta


@router.delete("/{card_id}")
async def remover(card_id: str, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    doc = await db.food_cards.find_one({"id": card_id, "userId": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Esse Food Card não existe.")
    cfg = visual_storage.carregar_configuracao()
    if cfg and cfg.ativo and doc.get("imageKey"):
        try:
            prefixo = visual_storage.prefixo_da_avaliacao(cfg.prefixo, user["id"], card_id)
            visual_storage.apagar_prefixo(cfg, visual_storage.cliente(cfg), prefixo)
        except Exception:
            # A foto ficar órfã é ruim; a exclusão falhar e o atleta continuar vendo o
            # card que pediu para apagar é pior.
            logger.exception("falha ao apagar a foto do food card %s", card_id)
    await db.food_cards.delete_one({"id": card_id, "userId": user["id"]})
    return {"removido": card_id}


def _url_da_foto(chave: Optional[str]) -> Optional[str]:
    """URL assinada de validade curta, gerada na hora. Nunca gravada no documento.

    Endereço gravado envelhece e vaza; chave não serve para nada sem credencial.
    """
    if not chave:
        return None
    cfg = visual_storage.carregar_configuracao()
    if not cfg or not cfg.ativo:
        return None
    try:
        return visual_storage.url_assinada(cfg, visual_storage.cliente(cfg), chave)
    except Exception:
        logger.exception("falha ao assinar a URL da foto")
        return None
