import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ImageOff, Plus, Trash2, X } from "lucide-react";

import VisualAssessmentResult from "./VisualAssessmentResult";
import VisualPhotoUpload, { ANGULOS } from "./VisualPhotoUpload";
import {
  compararAvaliacoes,
  dataCurta,
  dataLonga,
  intervaloEmPalavras,
} from "./compararAvaliacoes";
import "./visual-assessment.css";
import "./progress-photos.css";

/**
 * Evolucao das fotos — pensada para 360px de largura, e so depois para o resto.
 *
 * O que a pessoa quer ver e a foto de antes ao lado da de agora. Numero convence depois; a
 * imagem convence primeiro. Por isso as duas fotos ficam grandes, lado a lado, e tudo o
 * mais — escolha de data, de angulo, analise — se organiza em volta delas.
 *
 * A comparacao e sempre do MESMO angulo. Frente contra costas nao diz nada, e deixar isso
 * acontecer por descuido daria falsa sensacao de mudanca.
 */

const fotoDoAngulo = (avaliacao, angulo) =>
  (avaliacao?.photos || []).find((f) => f.angle === angulo) || null;

const rotuloDoAngulo = (id) => ANGULOS.find((a) => a.id === id)?.rotulo || id;

/* ── Estados de uma foto ────────────────────────────────────────────────────── */

/**
 * Um quadro de foto, com os tres estados possiveis: carregando, imagem, indisponivel.
 *
 * O estado "indisponivel" e desenhado como ausencia calma, e nao como erro: uma foto que
 * ainda nao carregou nao e um defeito que a pessoa precise resolver, e um quadro vermelho
 * de alerta assustaria a toa.
 */
function Quadro({ foto, rotulo, data, temRegistro }) {
  const [estado, setEstado] = useState(foto?.url ? "carregando" : "vazio");

  useEffect(() => {
    setEstado(foto?.url ? "carregando" : "vazio");
  }, [foto?.url]);

  return (
    <figure className="pf-quadro" data-estado={estado}>
      <div className="pf-moldura">
        {foto?.url && (
          <img
            src={foto.url}
            alt={`${rotulo} — ${data}`}
            loading="lazy"
            decoding="async"
            onLoad={() => setEstado("pronto")}
            onError={() => setEstado("vazio")}
          />
        )}
        {estado === "carregando" && <span className="pf-brilho" aria-hidden="true" />}
        {estado === "vazio" && (
          /*
           * Dois estados diferentes, e a diferenca importa: "esse angulo nao foi enviado"
           * e informacao acionavel — da para enviar depois. "A imagem nao carregou" nao e
           * culpa de quem esta olhando e nao pede acao nenhuma. Um texto so para os dois
           * mandaria a pessoa procurar uma foto que ela ja tirou.
           */
          <span className="pf-ausente">
            <ImageOff size={18} aria-hidden="true" />
            <small>{temRegistro ? "Imagem indisponível" : `Sem ${rotulo.toLowerCase()}`}</small>
          </span>
        )}
      </div>
      <figcaption>{data}</figcaption>
    </figure>
  );
}

/* ── Leitura da comparacao ──────────────────────────────────────────────────── */

/**
 * "O que mudou / Onde evoluiu mais / Proximo foco".
 *
 * Tudo aqui sai das duas leituras: um grupo so aparece como mudanca quando as DUAS
 * avaliacoes o classificaram com confianca suficiente e os niveis diferem. Quando nao ha
 * base, a tela diz isso — inventar evolucao seria o pior defeito possivel numa tela cujo
 * proposito e mostrar evolucao.
 */
/** Monta a frase da mudanca com concordancia certa — "3 grupos subiram", nao "subiu". */
function frasesDaMudanca(c) {
  const partes = [];
  if (c.melhoraram.length) {
    partes.push(c.melhoraram.length === 1
      ? "1 grupo subiu de nível"
      : `${c.melhoraram.length} grupos subiram de nível`);
  }
  if (c.pioraram.length) {
    partes.push(c.pioraram.length === 1
      ? "1 apareceu abaixo da leitura anterior"
      : `${c.pioraram.length} apareceram abaixo da leitura anterior`);
  }
  const inicio = partes.join(", e ");
  const iguais = c.mantiveram === 0
    ? ""
    : c.mantiveram === 1 ? " 1 seguiu igual." : ` ${c.mantiveram} seguiram igual.`;
  return `${inicio}.${iguais}`.trim();
}

function Leitura({ antiga, nova }) {
  const c = useMemo(() => compararAvaliacoes(antiga, nova), [antiga, nova]);
  const proximo = nova?.next_cycle?.length ? nova.next_cycle : nova?.training_priorities || [];

  return (
    <div className="pf-leitura" data-testid="leitura-comparacao">
      <section>
        <h4>O que mudou</h4>
        {!c.confiavel ? (
          <p className="pf-suave">
            {c.motivo === "sem_par"
              ? "Escolha duas avaliações diferentes para comparar."
              : "As duas leituras não têm grupos em comum com nitidez suficiente para afirmar mudança."}
          </p>
        ) : c.melhoraram.length || c.pioraram.length ? (
          <p>{frasesDaMudanca(c)}</p>
        ) : (
          <p>As duas leituras apontam o mesmo quadro em {c.comparados} grupos.</p>
        )}
      </section>

      <section>
        <h4>Onde evoluiu mais</h4>
        {c.confiavel && c.melhoraram.length ? (
          <ul className="pf-etiquetas">
            {c.melhoraram.slice(0, 6).map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        ) : (
          <p className="pf-suave">
            {c.confiavel
              ? "Nenhum grupo subiu de nível entre as duas datas."
              : "Sem base para apontar evolução por região."}
          </p>
        )}
      </section>

      <section>
        <h4>Próximo foco</h4>
        {proximo.length ? (
          <ul className="pf-passos">
            {proximo.slice(0, 3).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        ) : (
          <p className="pf-suave">
            A leitura mais recente não trouxe um foco definido para o próximo ciclo.
          </p>
        )}
      </section>
    </div>
  );
}

/* ── Tela ───────────────────────────────────────────────────────────────────── */

export default function ProgressPhotos({ API, profileId }) {
  const [historico, setHistorico] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [armazenamentoPronto, setArmazenamentoPronto] = useState(true);
  const [angulo, setAngulo] = useState("front");
  const [idAntiga, setIdAntiga] = useState(null);
  const [idNova, setIdNova] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/visual-history/${profileId}`);
      const lista = r.data?.assessments || [];
      setHistorico(lista);
      setArmazenamentoPronto(Boolean(r.data?.storage_ready));
      if (lista.length >= 2) {
        // A primeira contra a mais recente: e a comparacao que a pessoa quer ver.
        setIdAntiga(lista[lista.length - 1].id);
        setIdNova(lista[0].id);
      } else if (lista.length === 1) {
        setIdNova(lista[0].id);
      }
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

  const antiga = useMemo(() => historico.find((a) => a.id === idAntiga) || null, [historico, idAntiga]);
  const nova = useMemo(() => historico.find((a) => a.id === idNova) || null, [historico, idNova]);

  /** Angulos presentes em alguma avaliacao — oferecer o que nao existe seria ruido. */
  const angulosDisponiveis = useMemo(() => {
    const presentes = new Set();
    historico.forEach((a) => (a.photos || []).forEach((f) => presentes.add(f.angle)));
    return ANGULOS.filter((x) => presentes.has(x.id));
  }, [historico]);

  useEffect(() => {
    if (angulosDisponiveis.length && !angulosDisponiveis.some((a) => a.id === angulo)) {
      setAngulo(angulosDisponiveis[0].id);
    }
  }, [angulosDisponiveis, angulo]);

  const apagar = async (id) => {
    try {
      await axios.delete(`${API}/visual-assessment/${id}`);
      setHistorico((atual) => atual.filter((a) => a.id !== id));
      if (idAntiga === id) setIdAntiga(null);
      if (idNova === id) setIdNova(null);
    } catch (e) {
      console.error("[forge] não foi possível apagar a avaliação:", e);
    }
  };

  /** Toca numa data: a mais recente das duas vira a "nova", a outra vira a "antiga". */
  const escolher = (id) => {
    if (id === idNova || id === idAntiga) return;
    setIdAntiga(idNova);
    setIdNova(id);
  };

  const temPar = Boolean(antiga && nova && antiga.id !== nova.id);
  const cabecalho = (
    <header className="pf-topo">
      <div>
        <p className="pf-eyebrow">Evolução das fotos</p>
        <h3>Veja a diferença.</h3>
      </div>
      <button
        type="button"
        className="pf-acao"
        data-testid="nova-atualizacao-visual"
        onClick={() => setEnviando((x) => !x)}
      >
        {enviando ? <X size={16} aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}
        <span>{enviando ? "Fechar" : "Nova"}</span>
      </button>
    </header>
  );

  if (carregando) {
    return (
      <section className="pf-secao" data-testid="progress-photos">
        {cabecalho}
        <div className="pf-comparacao" aria-hidden="true">
          <div className="pf-quadro" data-estado="carregando">
            <div className="pf-moldura">
              <span className="pf-brilho" />
            </div>
          </div>
          <div className="pf-quadro" data-estado="carregando">
            <div className="pf-moldura">
              <span className="pf-brilho" />
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="pf-secao" data-testid="progress-photos">
      {cabecalho}

      {enviando && (
        <VisualPhotoUpload
          API={API}
          profileId={profileId}
          onConcluido={() => {
            setEnviando(false);
            setCarregando(true);
            carregar();
          }}
        />
      )}

      {historico.length === 0 && !enviando && (
        <div className="pf-vazio" data-testid="sem-avaliacoes">
          <p>A primeira avaliação vira o seu ponto de partida.</p>
          <span>É ela que dá sentido a todas as próximas.</span>
          <button type="button" className="pf-acao cheia" onClick={() => setEnviando(true)}>
            <Plus size={16} aria-hidden="true" /> Enviar minhas fotos
          </button>
        </div>
      )}

      {historico.length > 0 && (
        <>
          {!armazenamentoPronto && (
            <p className="pf-suave" data-testid="sem-armazenamento">
              As imagens não estão disponíveis para visualização no momento. As observações
              continuam abaixo.
            </p>
          )}

          {angulosDisponiveis.length > 1 && (
            <div className="pf-angulos" role="tablist" aria-label="Ângulo comparado">
              {angulosDisponiveis.map((a) => (
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

          <div className="pf-comparacao" data-testid="comparacao-lado-a-lado">
            {temPar ? (
              <>
                <Quadro
                  foto={fotoDoAngulo(antiga, angulo)}
                  rotulo={rotuloDoAngulo(angulo)}
                  data={dataCurta(antiga.created_at)}
                  temRegistro={(antiga.views || []).includes(angulo)}
                />
                <Quadro
                  foto={fotoDoAngulo(nova, angulo)}
                  rotulo={rotuloDoAngulo(angulo)}
                  data={dataCurta(nova.created_at)}
                  temRegistro={(nova.views || []).includes(angulo)}
                />
              </>
            ) : (
              nova && (
                <Quadro
                  foto={fotoDoAngulo(nova, angulo)}
                  rotulo={rotuloDoAngulo(angulo)}
                  data={dataCurta(nova.created_at)}
                  temRegistro={(nova.views || []).includes(angulo)}
                />
              )
            )}
          </div>

          {temPar ? (
            <p className="pf-intervalo" data-testid="intervalo">
              {intervaloEmPalavras(antiga.created_at, nova.created_at)}
            </p>
          ) : (
            <p className="pf-suave" data-testid="uma-avaliacao">
              {dataLonga(nova?.created_at)} · com a próxima, as duas aparecem aqui lado a
              lado.
            </p>
          )}

          {historico.length > 1 && (
            <div className="pf-datas" data-testid="linha-do-tempo">
              {historico.map((a) => {
                const papel = a.id === idNova ? "nova" : a.id === idAntiga ? "antiga" : "";
                return (
                  <div key={a.id} className={`pf-data ${papel}`}>
                    <button
                      type="button"
                      data-testid={`escolher-${a.id}`}
                      onClick={() => escolher(a.id)}
                      aria-pressed={Boolean(papel)}
                    >
                      <b>{dataCurta(a.created_at)}</b>
                      <small>
                        {(() => {
                          const n = (a.views || []).length || (a.photos || []).length;
                          return `${n} ${n === 1 ? "ângulo" : "ângulos"}`;
                        })()}
                      </small>
                    </button>
                    <button
                      type="button"
                      className="pf-apagar"
                      aria-label={`Apagar a avaliação de ${dataLonga(a.created_at)}`}
                      data-testid={`apagar-${a.id}`}
                      onClick={() => apagar(a.id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* A leitura fica ABAIXO das fotos: a imagem convence, o texto explica. */}
          {temPar && <Leitura antiga={antiga} nova={nova} />}

          {nova && (
            <VisualAssessmentResult
              resultado={{ ...nova, status: nova.status || "completed" }}
            />
          )}
        </>
      )}
    </section>
  );
}
