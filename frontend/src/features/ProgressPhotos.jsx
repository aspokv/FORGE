import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { ImageOff, Plus, RefreshCw, Trash2 } from "lucide-react";

import VisualAssessmentResult from "./VisualAssessmentResult";
import VisualPhotoUpload, { ANGULOS } from "./VisualPhotoUpload";
import { compararAvaliacoes, dataCurta, intervaloEmPalavras } from "./compararAvaliacoes";
import { parDeAvaliacoes } from "./parDeAvaliacoes";
import "./visual-assessment.css";
import "./progress-photos.css";

/**
 * Evolucao das fotos — um caminho so, pensado para 360px.
 *
 * Duas regras sustentam a tela, e as duas nasceram de erro visto em producao:
 *
 * 1. Uma foto mostra UMA moldura. A comparacao so existe quando ha uma segunda foto do
 *    mesmo angulo em OUTRA data (ver `parDeAvaliacoes`). Reservar o segundo espaco antes
 *    disso promete um "antes e agora" que nao existe.
 *
 * 2. "Nao consegui carregar a foto" e "essa foto nao foi enviada" sao coisas diferentes e
 *    aparecem diferente. A primeira e um problema nosso, e cabe oferecer nova tentativa; a
 *    segunda e so um espaco em branco na historia da pessoa. Nos dois casos a analise
 *    escrita continua na tela: ela nao depende da imagem ter carregado.
 */

const fotoDoAngulo = (avaliacao, angulo) =>
  (avaliacao?.photos || []).find((f) => f.angle === angulo) || null;

const temAngulo = (avaliacao, angulo) =>
  (avaliacao?.views || []).includes(angulo) ||
  (avaliacao?.photos || []).some((f) => f.angle === angulo);

const rotuloDoAngulo = (id) => ANGULOS.find((a) => a.id === id)?.rotulo || id;

/* ── Uma foto ───────────────────────────────────────────────────────────────── */

/**
 * A moldura tem quatro finais, e cada um diz uma coisa diferente a quem olha.
 *
 * A imagem so aparece depois de carregar: um `<img>` com endereco quebrado fica na tela
 * mostrando o proprio `alt` como texto, ao lado do icone de imagem partida do navegador.
 *
 * Quando o carregamento falha, a moldura ENCOLHE. Um retangulo alto e vazio ocupa a tela
 * inteira anunciando ausencia; o aviso compacto informa a mesma coisa sem dominar a
 * leitura, que e o que a pessoa veio ver.
 */
export function Foto({
  foto, reserva, angulo, data, rotulo, registrada, semArmazenamento, aoTentarNovamente,
}) {
  const principal = foto?.url || null;
  const [endereco, setEndereco] = useState(principal || reserva || null);
  const [estado, setEstado] = useState(principal || reserva ? "carregando" : "sem-imagem");

  useEffect(() => {
    const inicial = principal || reserva || null;
    setEndereco(inicial);
    setEstado(inicial ? "carregando" : "sem-imagem");
  }, [principal, reserva]);

  /**
   * A URL assinada vale poucos minutos. Quando ela falha e a pessoa acabou de enviar a
   * foto, o arquivo ainda esta na memoria desta sessao — mostrar o que temos e melhor que
   * anunciar falha para uma foto que a pessoa tirou ha segundos.
   */
  const aoFalhar = () => {
    if (reserva && endereco !== reserva) {
      setEndereco(reserva);
      setEstado("carregando");
      return;
    }
    console.error(
      "[forge] a foto de %s nao carregou (URL assinada vencida ou chave ausente)",
      angulo
    );
    setEstado("falhou");
  };

  // Sem URL e sem registro do angulo, nao houve foto. Com registro, houve — e sumiu.
  const falhou = estado === "falhou" || (estado === "sem-imagem" && registrada);
  const nuncaEnviada = estado === "sem-imagem" && !registrada;

  return (
    <figure className={`pf-quadro${falhou ? " pf-quadro-falhou" : ""}`}>
      {rotulo && <figcaption className="pf-rotulo">{rotulo}</figcaption>}

      <div className="pf-moldura">
        {endereco && estado !== "falhou" && (
          <img
            src={endereco}
            alt=""
            loading="lazy"
            decoding="async"
            hidden={estado !== "pronto"}
            onLoad={() => setEstado("pronto")}
            onError={aoFalhar}
          />
        )}

        {estado === "carregando" && <span className="pf-brilho" aria-hidden="true" />}

        {falhou && (
          <div className="pf-falha" data-testid="foto-indisponivel">
            <ImageOff size={16} aria-hidden="true" />
            <p>
              {semArmazenamento
                ? "Esta foto ainda não tem armazenamento permanente"
                : "Não foi possível carregar esta foto"}
            </p>
            {aoTentarNovamente && !semArmazenamento && (
              <button type="button" onClick={aoTentarNovamente} data-testid="tentar-novamente-foto">
                <RefreshCw size={13} aria-hidden="true" /> Tentar novamente
              </button>
            )}
          </div>
        )}

        {nuncaEnviada && (
          <span className="pf-ausente">
            <ImageOff size={18} aria-hidden="true" />
            <small>Sem foto de {rotuloDoAngulo(angulo).toLowerCase()}</small>
          </span>
        )}
      </div>

      <figcaption className="pf-data-foto">{data}</figcaption>
    </figure>
  );
}

/* ── Leitura da comparacao ──────────────────────────────────────────────────── */

/** Monta a frase da mudanca com concordancia certa — "3 grupos subiram", nao "subiu". */
function frasesDaMudanca(c) {
  const partes = [];
  if (c.melhoraram.length) {
    partes.push(
      c.melhoraram.length === 1
        ? "1 grupo subiu de nível"
        : `${c.melhoraram.length} grupos subiram de nível`
    );
  }
  if (c.pioraram.length) {
    partes.push(
      c.pioraram.length === 1
        ? "1 apareceu abaixo da leitura anterior"
        : `${c.pioraram.length} apareceram abaixo da leitura anterior`
    );
  }
  const iguais =
    c.mantiveram === 0
      ? ""
      : c.mantiveram === 1
        ? " 1 seguiu igual."
        : ` ${c.mantiveram} seguiram igual.`;
  return `${partes.join(", e ")}.${iguais}`.trim();
}

/**
 * "O que mudou" e "Proximo foco".
 *
 * Nao existe rota que compare duas datas — a leitura e de uma foto por vez. Entao a
 * comparacao sai das DUAS leituras, e nada alem: um grupo so conta quando as duas o
 * classificaram com confianca suficiente e os niveis diferem.
 */
function Leitura({ antiga, nova }) {
  const c = useMemo(() => compararAvaliacoes(antiga, nova), [antiga, nova]);
  const proximo = nova?.next_cycle?.length ? nova.next_cycle : nova?.training_priorities || [];

  return (
    <div className="pf-leitura" data-testid="leitura-comparacao">
      <section>
        <h4>O que mudou</h4>
        {c.confiavel ? (
          <p>
            {c.melhoraram.length || c.pioraram.length
              ? frasesDaMudanca(c)
              : `As duas leituras apontam o mesmo quadro em ${c.comparados} grupos.`}
          </p>
        ) : (
          <p className="pf-suave">
            As duas leituras não têm grupos em comum com nitidez suficiente para afirmar
            mudança.
          </p>
        )}
      </section>

      {c.confiavel && c.melhoraram.length > 0 && (
        <section>
          <h4>Onde evoluiu mais</h4>
          <ul className="pf-etiquetas">
            {c.melhoraram.slice(0, 6).map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </section>
      )}

      {proximo.length > 0 && (
        <section>
          <h4>Próximo foco</h4>
          <ul className="pf-passos">
            {proximo.slice(0, 3).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/* ── Tela ───────────────────────────────────────────────────────────────────── */

export default function ProgressPhotos({ API, profileId }) {
  const [historico, setHistorico] = useState([]);
  const [armazenamentoPronto, setArmazenamentoPronto] = useState(true);
  const [carregando, setCarregando] = useState(true);
  const [angulo, setAngulo] = useState("front");
  const [enviando, setEnviando] = useState(false);

  /**
   * A foto que acabou de subir, guardada so nesta sessao.
   *
   * O servidor devolve a avaliacao na hora, mas a URL assinada so vem na proxima leitura do
   * historico — e nao vem nenhuma enquanto o bucket nao estiver configurado. Sem isto, a
   * pessoa termina o envio e ve um espaco vazio no lugar da foto que acabou de tirar.
   */
  const [previa, setPrevia] = useState(null); // {id, angulo, url}
  const previaRef = useRef(null);

  const guardarPrevia = useCallback((nova) => {
    if (previaRef.current?.url && previaRef.current.url !== nova?.url) {
      URL.revokeObjectURL(previaRef.current.url);
    }
    previaRef.current = nova;
    setPrevia(nova);
  }, []);

  // O endereco local vive enquanto a tela vive. Sem isto ele fica preso na memoria da aba.
  useEffect(
    () => () => {
      if (previaRef.current?.url) URL.revokeObjectURL(previaRef.current.url);
    },
    []
  );

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/visual-history/${profileId}`);
      setHistorico(r.data?.assessments || []);
      setArmazenamentoPronto(r.data?.storage_ready !== false);
    } catch (e) {
      console.error("[forge] não foi possível carregar o histórico visual:", e);
      setHistorico([]);
    } finally {
      setCarregando(false);
    }
  }, [API, profileId]);

  useEffect(() => {
    if (profileId) carregar();
  }, [profileId, carregar]);

  /**
   * Nova tentativa = buscar o historico de novo.
   *
   * Reapontar para a MESMA URL nao adiantaria nada: se ela venceu, vai vencer de novo. O
   * que resolve e pedir uma assinatura nova, que e o que esta chamada faz.
   */
  const tentarNovamente = useCallback(() => {
    setCarregando(true);
    carregar();
  }, [carregar]);

  /** Angulos que a pessoa realmente enviou. Sem envio, nao ha o que escolher. */
  const angulosEnviados = useMemo(() => {
    const presentes = new Set();
    historico.forEach((a) =>
      ANGULOS.forEach((x) => temAngulo(a, x.id) && presentes.add(x.id))
    );
    return ANGULOS.filter((x) => presentes.has(x.id));
  }, [historico]);

  useEffect(() => {
    if (angulosEnviados.length && !angulosEnviados.some((a) => a.id === angulo)) {
      setAngulo(angulosEnviados[0].id);
    }
  }, [angulosEnviados, angulo]);

  /** As avaliacoes daquele angulo, da mais antiga para a mais nova. */
  const doAngulo = useMemo(
    () => historico.filter((a) => temAngulo(a, angulo)).slice().reverse(),
    [historico, angulo]
  );

  const { primeira, atual, unica, comparando } = useMemo(
    () => parDeAvaliacoes(doAngulo),
    [doAngulo]
  );
  const maisRecente = atual || unica;

  /** A copia local da foto daquela avaliacao, se for a que acabou de subir nesta sessao. */
  const reservaDe = useCallback(
    (avaliacao) =>
      previa && previa.id === avaliacao?.id && previa.angulo === angulo ? previa.url : null,
    [angulo, previa]
  );

  const apagar = async (id) => {
    try {
      await axios.delete(`${API}/visual-assessment/${id}`);
      setHistorico((x) => x.filter((a) => a.id !== id));
      if (previaRef.current?.id === id) guardarPrevia(null);
    } catch (e) {
      console.error("[forge] não foi possível apagar a avaliação:", e);
    }
  };

  const cabecalho = (
    <header className="pf-topo">
      <div>
        <p className="pf-eyebrow">Evolução das fotos</p>
        <h3>Veja a diferença.</h3>
      </div>
      {!enviando && !(historico.length === 0 && !carregando) && (
        <button
          type="button"
          className="pf-acao"
          data-testid="nova-atualizacao-visual"
          onClick={() => setEnviando(true)}
        >
          <Plus size={16} aria-hidden="true" />
          <span>Adicionar</span>
        </button>
      )}
    </header>
  );

  if (carregando) {
    return (
      <section className="pf-secao" data-testid="progress-photos">
        {cabecalho}
        <div className="pf-comparacao sozinha" aria-hidden="true">
          <div className="pf-quadro">
            <div className="pf-moldura">
              <span className="pf-brilho" />
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (enviando) {
    return (
      <section className="pf-secao" data-testid="progress-photos">
        {cabecalho}
        <VisualPhotoUpload
          API={API}
          profileId={profileId}
          onCancelar={() => setEnviando(false)}
          onConcluido={(avaliacao, local) => {
            if (local?.url && avaliacao?.id) {
              guardarPrevia({ id: avaliacao.id, angulo: local.angulo, url: local.url });
            }
            setEnviando(false);
            setCarregando(true);
            carregar();
          }}
        />
      </section>
    );
  }

  if (historico.length === 0) {
    return (
      <section className="pf-secao" data-testid="progress-photos">
        {cabecalho}
        <div className="pf-vazio" data-testid="sem-avaliacoes">
          <p>A primeira foto vira o seu ponto de partida.</p>
          <span>
            Uma foto de frente já rende uma leitura completa. A próxima, em outra data,
            liga a comparação.
          </span>
          <button
            type="button"
            className="pf-acao cheia"
            data-testid="nova-atualizacao-visual"
            onClick={() => setEnviando(true)}
          >
            <Plus size={16} aria-hidden="true" /> Adicionar foto
          </button>
        </div>
      </section>
    );
  }

  /**
   * Sem bucket, "tentar novamente" nao resolveria nada — nao ha assinatura a pedir. Entao o
   * aviso e por moldura, e nao por tela: a foto que tem copia local aparece normalmente, e
   * so as que dependem do servidor explicam que falta armazenamento.
   */
  const semArmazenamentoPara = (avaliacao) => !armazenamentoPronto && !reservaDe(avaliacao);

  return (
    <section className="pf-secao" data-testid="progress-photos">
      {cabecalho}

      {angulosEnviados.length > 1 && (
        <div className="pf-angulos" role="tablist" aria-label="Ângulo">
          {angulosEnviados.map((a) => (
            <button
              key={a.id}
              type="button"
              role="tab"
              aria-selected={a.id === angulo}
              className={a.id === angulo ? "ativo" : ""}
              data-testid={`angulo-${a.id}`}
              onClick={() => setAngulo(a.id)}
            >
              {a.rotulo}
            </button>
          ))}
        </div>
      )}

      <div
        className={`pf-comparacao${comparando ? "" : " sozinha"}`}
        data-testid="comparacao-lado-a-lado"
      >
        {comparando ? (
          <>
            <Foto
              foto={fotoDoAngulo(primeira, angulo)}
              reserva={reservaDe(primeira)}
              angulo={angulo}
              rotulo="Antes"
              data={dataCurta(primeira.created_at)}
              registrada={temAngulo(primeira, angulo)}
              semArmazenamento={semArmazenamentoPara(primeira)}
              aoTentarNovamente={tentarNovamente}
            />
            <Foto
              foto={fotoDoAngulo(atual, angulo)}
              reserva={reservaDe(atual)}
              angulo={angulo}
              rotulo="Agora"
              data={dataCurta(atual.created_at)}
              registrada={temAngulo(atual, angulo)}
              semArmazenamento={semArmazenamentoPara(atual)}
              aoTentarNovamente={tentarNovamente}
            />
          </>
        ) : (
          <Foto
            foto={fotoDoAngulo(unica, angulo)}
            reserva={reservaDe(unica)}
            angulo={angulo}
            rotulo="Primeira avaliação"
            data={dataCurta(unica.created_at)}
            registrada={temAngulo(unica, angulo)}
            semArmazenamento={semArmazenamentoPara(unica)}
            aoTentarNovamente={tentarNovamente}
          />
        )}
      </div>

      {comparando ? (
        <p className="pf-intervalo" data-testid="intervalo">
          {intervaloEmPalavras(primeira.created_at, atual.created_at)}
        </p>
      ) : (
        <p className="pf-suave" data-testid="uma-avaliacao">
          Sua primeira foto de {rotuloDoAngulo(angulo).toLowerCase()}. A próxima, em outra
          data, liga a comparação.
        </p>
      )}

      {semArmazenamentoPara(maisRecente) && (
        <p className="pf-aviso" data-testid="aviso-armazenamento">
          Esta foto aparece durante a sessão. O histórico permanente fica disponível assim
          que o armazenamento for configurado.
        </p>
      )}

      {comparando && <Leitura antiga={primeira} nova={atual} />}

      {maisRecente && (
        <VisualAssessmentResult
          resultado={{ ...maisRecente, status: maisRecente.status || "completed" }}
        />
      )}

      {doAngulo.length > 1 && (
        <div className="pf-datas" data-testid="linha-do-tempo">
          {doAngulo
            .slice()
            .reverse()
            .map((a) => (
              <div
                key={a.id}
                className={`pf-data ${
                  a.id === maisRecente?.id ? "nova" : a.id === primeira?.id ? "antiga" : ""
                }`}
              >
                <span>
                  <b>{dataCurta(a.created_at)}</b>
                  <small>{a.id === primeira?.id ? "primeira" : "atualização"}</small>
                </span>
                <button
                  type="button"
                  className="pf-apagar"
                  aria-label={`Apagar a foto de ${dataCurta(a.created_at)}`}
                  data-testid={`apagar-${a.id}`}
                  onClick={() => apagar(a.id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
        </div>
      )}
    </section>
  );
}
