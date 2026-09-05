import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { CalendarDays, ImageOff, Plus, Trash2, X } from "lucide-react";

import VisualAssessmentResult from "./VisualAssessmentResult";
import VisualPhotoUpload from "./VisualPhotoUpload";
import { ANGULOS } from "./VisualPhotoUpload";
import "./visual-assessment.css";

/**
 * Evolucao das fotos: o historico visual e a comparacao entre duas datas.
 *
 * A tela de Progresso ja mostrava carga, series e consistencia. O que faltava era o que a
 * pessoa realmente quer ver — a foto de antes ao lado da de agora. Numero convence depois;
 * a imagem convence primeiro.
 *
 * A comparacao e sempre do MESMO angulo. Comparar frente com costas nao diz nada, e deixar
 * isso acontecer por descuido daria uma falsa sensacao de mudanca.
 */

const formatarData = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
};

/** Distancia entre duas avaliacoes, em linguagem de gente. */
function intervalo(deIso, ateIso) {
  const de = new Date(deIso);
  const ate = new Date(ateIso);
  if (Number.isNaN(de.getTime()) || Number.isNaN(ate.getTime())) return "";
  const dias = Math.round((ate - de) / 86400000);
  if (dias <= 0) return "mesmo dia";
  if (dias === 1) return "1 dia depois";
  if (dias < 14) return `${dias} dias depois`;
  if (dias < 60) return `${Math.round(dias / 7)} semanas depois`;
  const meses = Math.round(dias / 30);
  return meses === 1 ? "1 mês depois" : `${meses} meses depois`;
}

const fotoDoAngulo = (avaliacao, angulo) =>
  (avaliacao?.photos || []).find((f) => f.angle === angulo) || null;

export default function ProgressPhotos({ API, profileId }) {
  const [historico, setHistorico] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [armazenamentoPronto, setArmazenamentoPronto] = useState(true);
  const [angulo, setAngulo] = useState("front");
  const [idEsquerda, setIdEsquerda] = useState(null);
  const [idDireita, setIdDireita] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/visual-history/${profileId}`);
      const lista = r.data?.assessments || [];
      setHistorico(lista);
      setArmazenamentoPronto(Boolean(r.data?.storage_ready));
      // Padrao util: a mais antiga contra a mais nova, que e a comparacao que interessa.
      if (lista.length >= 2) {
        setIdEsquerda(lista[lista.length - 1].id);
        setIdDireita(lista[0].id);
      }
    } catch (e) {
      // Sem historico a tela continua de pe; o motivo tecnico nao vai para o usuario.
      console.error("[forge] não foi possível carregar o histórico visual:", e);
      setHistorico([]);
    } finally {
      setCarregando(false);
    }
  }, [API, profileId]);

  useEffect(() => {
    if (profileId) carregar();
  }, [profileId, carregar]);

  const esquerda = useMemo(
    () => historico.find((a) => a.id === idEsquerda) || null,
    [historico, idEsquerda]
  );
  const direita = useMemo(
    () => historico.find((a) => a.id === idDireita) || null,
    [historico, idDireita]
  );

  /** Angulos que existem em ao menos uma avaliacao — nao adianta oferecer o que nao ha. */
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
      if (idEsquerda === id) setIdEsquerda(null);
      if (idDireita === id) setIdDireita(null);
    } catch (e) {
      console.error("[forge] não foi possível apagar a avaliação:", e);
    }
  };

  const fotoEsq = fotoDoAngulo(esquerda, angulo);
  const fotoDir = fotoDoAngulo(direita, angulo);
  const podeComparar = Boolean(fotoEsq && fotoDir && esquerda.id !== direita.id);

  return (
    <section className="panel vp-secao" data-testid="progress-photos">
      <header className="vp-cabecalho">
        <div>
          <p className="eyebrow">EVOLUÇÃO DAS FOTOS</p>
          <h3>Veja a diferença, não só os números.</h3>
        </div>
        <button
          type="button"
          className="secondary-button"
          data-testid="nova-atualizacao-visual"
          onClick={() => setEnviando((x) => !x)}
        >
          {enviando ? <X size={15} aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}{" "}
          {enviando ? "Fechar" : "Nova atualização"}
        </button>
      </header>

      {enviando && (
        <VisualPhotoUpload
          API={API}
          profileId={profileId}
          onConcluido={() => {
            setEnviando(false);
            carregar();
          }}
        />
      )}

      {carregando && <p className="muted">Carregando suas avaliações…</p>}

      {!carregando && historico.length === 0 && (
        <p className="muted" data-testid="sem-avaliacoes">
          Você ainda não tem avaliações visuais. A primeira vira o seu ponto de partida —
          é ela que dá sentido a todas as próximas.
        </p>
      )}

      {!carregando && historico.length > 0 && !armazenamentoPronto && (
        <p className="muted" data-testid="sem-armazenamento">
          As fotos destas avaliações não estão disponíveis para visualização no momento. As
          observações continuam abaixo.
        </p>
      )}

      {historico.length > 0 && (
        <>
          {angulosDisponiveis.length > 1 && (
            <div className="vp-angulos" role="tablist" aria-label="Ângulo comparado">
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

          {podeComparar ? (
            <>
              <div className="vp-comparacao" data-testid="comparacao-lado-a-lado">
                <figure>
                  <img src={fotoEsq.url} alt={`Avaliação de ${formatarData(esquerda.created_at)}`} />
                  <figcaption>
                    <CalendarDays size={12} aria-hidden="true" />
                    {formatarData(esquerda.created_at)}
                  </figcaption>
                </figure>
                <figure>
                  <img src={fotoDir.url} alt={`Avaliação de ${formatarData(direita.created_at)}`} />
                  <figcaption>
                    <CalendarDays size={12} aria-hidden="true" />
                    {formatarData(direita.created_at)}
                  </figcaption>
                </figure>
              </div>
              <p className="vp-intervalo">
                {intervalo(esquerda.created_at, direita.created_at)}
              </p>
            </>
          ) : (
            <p className="muted" data-testid="sem-comparacao">
              {historico.length < 2
                ? "Com uma segunda avaliação, as duas aparecem aqui lado a lado."
                : "As duas datas escolhidas não têm foto do mesmo ângulo, então não dá para comparar com honestidade."}
            </p>
          )}

          {/* A analise fica ABAIXO das imagens, como pedido: a foto convence, o texto explica. */}
          {direita && <VisualAssessmentResult resultado={{ ...direita, status: direita.status || "completed" }} />}

          <div className="vp-linha-do-tempo" data-testid="linha-do-tempo">
            <p className="eyebrow">Suas avaliações</p>
            <ul>
              {historico.map((a) => {
                const foto = fotoDoAngulo(a, angulo);
                return (
                  <li key={a.id} className={a.id === idDireita ? "atual" : ""}>
                    <button
                      type="button"
                      className="vp-miniatura"
                      data-testid={`escolher-${a.id}`}
                      onClick={() => (idEsquerda === a.id ? setIdDireita(a.id) : setIdEsquerda(a.id))}
                      aria-label={`Comparar a avaliação de ${formatarData(a.created_at)}`}
                    >
                      {foto ? (
                        <img src={foto.url} alt="" />
                      ) : (
                        <span className="vp-sem-foto" aria-hidden="true">
                          <ImageOff size={16} />
                        </span>
                      )}
                      <small>{formatarData(a.created_at)}</small>
                    </button>
                    <button
                      type="button"
                      className="vp-apagar"
                      aria-label={`Apagar a avaliação de ${formatarData(a.created_at)}`}
                      data-testid={`apagar-${a.id}`}
                      onClick={() => apagar(a.id)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}
