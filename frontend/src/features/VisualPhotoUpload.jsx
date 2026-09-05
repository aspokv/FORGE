import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Camera, Plus, X } from "lucide-react";

import { comprimirImagem } from "./comprimirImagem";
import "./visual-assessment.css";

/**
 * Envio da avaliacao visual: ate quatro fotos, uma por angulo.
 *
 * A versao anterior aceitava UM arquivo. Quatro angulos mudam o produto, nao so a tela: e
 * o que permite comparar "costas de hoje" com "costas de um mes atras" mais adiante, no
 * historico. Por isso o angulo e escolhido no envio, e nao adivinhado depois.
 *
 * Enviar com uma foto continua valendo. Mais angulos deixam a leitura mais completa, e a
 * tela diz isso — mas nao exige.
 */

export const ANGULOS = [
  { id: "front", rotulo: "Frente" },
  { id: "back", rotulo: "Costas" },
  { id: "left", rotulo: "Lado esquerdo" },
  { id: "right", rotulo: "Lado direito" },
];

const TAMANHO_MAXIMO = 8 * 1024 * 1024;

export default function VisualPhotoUpload({ API, profileId, onConcluido }) {
  const [fotos, setFotos] = useState([]); // {angulo, arquivo, miniatura, bytes}
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState(0);
  const [erro, setErro] = useState("");
  const entrada = useRef(null);

  // Miniatura vive num object URL; sem revogar, cada troca de foto vaza memoria.
  useEffect(() => {
    return () => fotos.forEach((f) => URL.revokeObjectURL(f.miniatura));
    // Intencionalmente so na desmontagem: a revogacao por item acontece em `remover`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const proximoAngulo = useCallback(
    (usados) => ANGULOS.find((a) => !usados.includes(a.id))?.id || null,
    []
  );

  const escolher = async (evento) => {
    const arquivos = [...(evento.target.files || [])];
    evento.target.value = ""; // permite reescolher o mesmo arquivo
    if (!arquivos.length) return;
    setErro("");

    const atuais = [...fotos];
    for (const arquivo of arquivos) {
      if (atuais.length >= ANGULOS.length) break;
      if (arquivo.size > TAMANHO_MAXIMO * 4) {
        setErro("Uma das imagens é grande demais.");
        continue;
      }
      try {
        // Comprime ANTES de qualquer coisa: o que sobe e o que a pessoa gastou de dados.
        const comprimida = await comprimirImagem(arquivo);
        atuais.push({
          angulo: proximoAngulo(atuais.map((f) => f.angulo)),
          arquivo: comprimida,
          miniatura: URL.createObjectURL(comprimida),
          bytes: comprimida.size,
        });
      } catch {
        setErro("Não foi possível preparar uma das imagens.");
      }
    }
    setFotos(atuais.filter((f) => f.angulo));
  };

  const remover = (indice) => {
    setFotos((atuais) => {
      URL.revokeObjectURL(atuais[indice].miniatura);
      return atuais.filter((_, i) => i !== indice);
    });
  };

  const trocarAngulo = (indice, angulo) => {
    setFotos((atuais) =>
      atuais.map((f, i) => {
        if (i === indice) return { ...f, angulo };
        // Angulo e unico: quem ja usava esse troca com o que esta saindo.
        if (f.angulo === angulo) return { ...f, angulo: atuais[indice].angulo };
        return f;
      })
    );
  };

  const enviar = async () => {
    if (!fotos.length || enviando) return;
    setEnviando(true);
    setProgresso(0);
    setErro("");

    const corpo = new FormData();
    corpo.append("profile_id", profileId || "");
    corpo.append("consent", "true");
    corpo.append("views", JSON.stringify(fotos.map((f) => f.angulo)));
    fotos.forEach((f) => corpo.append("photos", f.arquivo, `${f.angulo}.jpg`));

    try {
      const r = await axios.post(`${API}/visual-assessment`, corpo, {
        onUploadProgress: (e) => {
          if (!e.total) return;
          // Para em 95%: o resto e a analise no servidor, que nao tem progresso para
          // informar. Cravar 100% aqui e depois esperar seria mentir para quem olha.
          setProgresso(Math.min(95, Math.round((e.loaded / e.total) * 95)));
        },
      });
      setProgresso(100);
      fotos.forEach((f) => URL.revokeObjectURL(f.miniatura));
      setFotos([]);
      onConcluido?.(r.data);
    } catch (e) {
      // O motivo tecnico fica no console; na tela vai o que da para fazer a respeito.
      console.error("[forge] falha ao enviar a avaliação visual:", e);
      const recusa = e?.response?.data?.detail;
      setErro(
        typeof recusa?.message === "string"
          ? recusa.message
          : "Não foi possível enviar agora. Tente novamente em alguns minutos."
      );
    } finally {
      setEnviando(false);
    }
  };

  const usados = fotos.map((f) => f.angulo);
  const faltam = ANGULOS.filter((a) => !usados.includes(a.id));

  return (
    <div className="vp-envio" data-testid="visual-photo-upload">
      <div className="vp-grade">
        {fotos.map((foto, i) => (
          <figure className="vp-item" key={`${foto.angulo}-${i}`}>
            <img src={foto.miniatura} alt={`Prévia — ${foto.angulo}`} />
            <button
              type="button"
              className="vp-remover"
              aria-label="Remover foto"
              data-testid={`remover-foto-${i}`}
              onClick={() => remover(i)}
              disabled={enviando}
            >
              <X size={14} />
            </button>
            <figcaption>
              <select
                value={foto.angulo}
                aria-label="Ângulo da foto"
                data-testid={`angulo-foto-${i}`}
                onChange={(e) => trocarAngulo(i, e.target.value)}
                disabled={enviando}
              >
                {ANGULOS.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.rotulo}
                  </option>
                ))}
              </select>
            </figcaption>
          </figure>
        ))}

        {fotos.length < ANGULOS.length && (
          <label className="vp-adicionar" data-testid="adicionar-fotos">
            <Plus size={22} aria-hidden="true" />
            <span>Adicionar fotos</span>
            <input
              ref={entrada}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              multiple
              disabled={enviando}
              onChange={escolher}
            />
          </label>
        )}
      </div>

      <p className="vp-dica">
        {fotos.length === 0 ? (
          <>
            <Camera size={13} aria-hidden="true" /> Frente, costas e os dois lados. Uma
            foto já funciona; mais ângulos deixam a leitura mais completa.
          </>
        ) : faltam.length ? (
          <>Faltam: {faltam.map((a) => a.rotulo).join(", ")}. Você pode enviar assim mesmo.</>
        ) : (
          <>Os quatro ângulos enviados.</>
        )}
      </p>

      {erro && (
        <p className="vp-erro" role="alert" data-testid="visual-upload-error">
          {erro}
        </p>
      )}

      {enviando && (
        <div className="vp-progresso" data-testid="visual-upload-progress">
          <div className="vp-barra">
            <i style={{ width: `${progresso}%` }} />
          </div>
          <span>
            {progresso < 95 ? `Enviando ${progresso}%` : "Lendo o que as fotos mostram…"}
          </span>
        </div>
      )}

      <button
        type="button"
        className="primary-button"
        data-testid="submit-visual-assessment"
        disabled={!fotos.length || enviando}
        aria-busy={enviando}
        onClick={enviar}
      >
        {enviando ? "Enviando…" : `Enviar ${fotos.length || ""} ${fotos.length === 1 ? "foto" : "fotos"}`.trim()}
      </button>
    </div>
  );
}
