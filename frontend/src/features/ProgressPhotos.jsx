import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ImageOff, Plus, Trash2 } from "lucide-react";

import VisualAssessmentResult from "./VisualAssessmentResult";
import VisualPhotoUpload, { ANGULOS } from "./VisualPhotoUpload";
import { compararAvaliacoes, dataCurta, intervaloEmPalavras } from "./compararAvaliacoes";
import "./visual-assessment.css";
import "./progress-photos.css";

/**
 * Evolucao das fotos — um caminho so, pensado para 360px.
 *
 * A versao anterior mostrava quatro molduras de angulo ao mesmo tempo. Parecia completa e
 * era o contrario: quatro caixas vazias lem como formulario, e quem tinha so uma foto de
 * frente ficava olhando tres buracos.
 *
 * Agora a tela mostra o angulo que a pessoa realmente enviou — frente, na esmagadora
 * maioria — e compara a PRIMEIRA foto daquele angulo com a MAIS RECENTE. Uma foto sozinha
 * ja rende leitura; a segunda liga a comparacao. Nada de grade, nada de montagem.
 */

const fotoDoAngulo = (avaliacao, angulo) =>
  (avaliacao?.photos || []).find((f) => f.angle === angulo) || null;

const temAngulo = (avaliacao, angulo) =>
  (avaliacao?.views || []).includes(angulo) ||
  (avaliacao?.photos || []).some((f) => f.angle === angulo);

const rotuloDoAngulo = (id) => ANGULOS.find((a) => a.id === id)?.rotulo || id;

/* ── Uma foto ───────────────────────────────────────────────────────────────── */

/**
 * Estados: carregando, imagem, indisponivel, angulo ausente.
 *
 * A imagem so aparece depois de carregar. Antes, o `<img>` com endereco quebrado ficava na
 * tela mostrando o proprio `alt` como texto, ao lado do icone de imagem partida do
 * navegador — exatamente o que a tela nao podia parecer.
 */
function Foto({ foto, angulo, data, registrada }) {
  const [estado, setEstado] = useState(foto?.url ? "carregando" : "vazio");

  useEffect(() => {
    setEstado(foto?.url ? "carregando" : "vazio");
  }, [foto?.url]);

  return (
    <figure className="pf-quadro">
      <div className="pf-moldura">
        {foto?.url && (
          <img
            src={foto.url}
            alt=""
            loading="lazy"
            decoding="async"
            hidden={estado !== "pronto"}
            onLoad={() => setEstado("pronto")}
            onError={() => setEstado("vazio")}
          />
        )}
        {estado === "carregando" && <span className="pf-brilho" aria-hidden="true" />}
        {estado === "vazio" && (
          /*
           * Dois textos diferentes, e a diferenca importa: "esse angulo nao foi enviado" e
           * acionavel — da para enviar depois. "A imagem nao carregou" nao e culpa de quem
           * esta olhando e nao pede acao nenhuma.
           */
          <span className="pf-ausente">
            <ImageOff size={18} aria-hidden="true" />
            <small>
              {registrada
                ? "Imagem indisponível"
                : `Sem foto de ${rotuloDoAngulo(angulo).toLowerCase()}`}
            </small>
          </span>
        )}
      </div>
      <figcaption>{data}</figcaption>
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
  const [carregando, setCarregando] = useState(true);
  const [angulo, setAngulo] = useState("front");
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/visual-history/${profileId}`);
      setHistorico(r.data?.assessments || []);
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

  const primeira = doAngulo[0] || null;
  const atual = doAngulo.length > 1 ? doAngulo[doAngulo.length - 1] : null;
  const maisRecente = atual || primeira;

  const apagar = async (id) => {
    try {
      await axios.delete(`${API}/visual-assessment/${id}`);
      setHistorico((x) => x.filter((a) => a.id !== id));
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
          onConcluido={() => {
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

  const comparando = Boolean(primeira && atual);

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
        {comparando && (
          <Foto
            foto={fotoDoAngulo(primeira, angulo)}
            angulo={angulo}
            data={dataCurta(primeira.created_at)}
            registrada={temAngulo(primeira, angulo)}
          />
        )}
        <Foto
          foto={fotoDoAngulo(maisRecente, angulo)}
          angulo={angulo}
          data={dataCurta(maisRecente.created_at)}
          registrada={temAngulo(maisRecente, angulo)}
        />
      </div>

      {comparando ? (
        <p className="pf-intervalo" data-testid="intervalo">
          {intervaloEmPalavras(primeira.created_at, atual.created_at)}
        </p>
      ) : (
        <p className="pf-suave" data-testid="uma-avaliacao">
          Sua primeira foto de {rotuloDoAngulo(angulo).toLowerCase()}. A próxima, em outra
          data, aparece aqui ao lado.
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
