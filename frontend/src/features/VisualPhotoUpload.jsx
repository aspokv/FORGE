import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Camera, RefreshCw, X } from "lucide-react";

import { comprimirImagem } from "./comprimirImagem";
import "./visual-assessment.css";

/**
 * Envio de UMA foto por atualizacao.
 *
 * A versao anterior oferecia quatro espacos de angulo na mesma tela. Parecia completa e
 * era o contrario: quatro molduras vazias de uma vez lem como formulario a preencher, e a
 * pessoa que so queria mandar uma foto de frente ficava sem saber se podia.
 *
 * Agora o caminho e um so — escolher a foto, confirmar o angulo (frente por padrao, que e
 * o que quase todo mundo manda) e enviar. Outros angulos continuam possiveis, em
 * atualizacoes separadas, e a comparacao junta as datas do mesmo angulo depois.
 */

export const ANGULOS = [
  { id: "front", rotulo: "Frente" },
  { id: "back", rotulo: "Costas" },
  { id: "left", rotulo: "Lado esquerdo" },
  { id: "right", rotulo: "Lado direito" },
];

/**
 * Traduz a recusa em algo que a pessoa possa resolver.
 *
 * "Erro 415" nao ajuda ninguem. O que ajuda e saber se o problema foi o arquivo, a foto,
 * ou o servico — e o que dizer para cada caso e diferente.
 */
function explicar(erro) {
  const motivo = erro?.response?.data?.detail?.reason;
  const status = erro?.response?.status;

  if (motivo === "unsupported_media_type" || motivo === "not_an_image") {
    return {
      titulo: "Esse arquivo não é uma imagem que dá para ler",
      texto: "Envie uma foto em JPG, PNG ou WebP — a foto direto da galeria costuma servir.",
    };
  }
  if (motivo === "payload_too_large" || status === 413) {
    return {
      titulo: "A imagem ficou grande demais",
      texto: "Tente uma foto com menos resolução, ou tire uma nova pelo próprio celular.",
    };
  }
  if (status === 401 || status === 403) {
    return {
      titulo: "Sua sessão expirou",
      texto: "Entre de novo e repita o envio; a foto não foi perdida.",
    };
  }
  if (status >= 500 || !status) {
    return {
      titulo: "Não foi possível concluir agora",
      texto: "Foi uma falha temporária do serviço. A foto está aqui — é só tentar de novo.",
    };
  }
  return {
    titulo: "Não foi possível enviar essa foto",
    texto: "Confira se a pessoa aparece inteira, com boa luz e sem contraluz, e tente de novo.",
  };
}

export default function VisualPhotoUpload({ API, profileId, onConcluido, onCancelar }) {
  const [foto, setFoto] = useState(null); // {arquivo, miniatura}
  const [angulo, setAngulo] = useState("front");
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState(0);
  const [falha, setFalha] = useState(null);
  const entrada = useRef(null);

  useEffect(() => () => foto && URL.revokeObjectURL(foto.miniatura), [foto]);

  const escolher = async (evento) => {
    const arquivo = (evento.target.files || [])[0];
    evento.target.value = "";
    if (!arquivo) return;
    setFalha(null);
    try {
      const comprimida = await comprimirImagem(arquivo);
      if (foto) URL.revokeObjectURL(foto.miniatura);
      setFoto({ arquivo: comprimida, miniatura: URL.createObjectURL(comprimida) });
    } catch {
      setFalha({
        titulo: "Não deu para preparar essa imagem",
        texto: "Escolha outra foto, ou tire uma nova pelo celular.",
      });
    }
  };

  const enviar = async () => {
    if (!foto || enviando) return;
    setEnviando(true);
    setProgresso(0);
    setFalha(null);

    const corpo = new FormData();
    corpo.append("profile_id", profileId || "");
    corpo.append("consent", "true");
    corpo.append("views", JSON.stringify([angulo]));
    corpo.append("photos", foto.arquivo, `${angulo}.jpg`);

    try {
      const r = await axios.post(`${API}/visual-assessment`, corpo, {
        onUploadProgress: (e) => {
          if (!e.total) return;
          // Para em 95%: o resto e a leitura no servidor, que nao tem progresso a
          // informar. Cravar 100% antes da resposta seria mentir para quem olha.
          setProgresso(Math.min(95, Math.round((e.loaded / e.total) * 95)));
        },
      });
      setProgresso(100);
      // A miniatura NAO e descartada aqui: quem recebe passa a ser dono dela e a mostra
      // enquanto a URL assinada do servidor nao chega — ou enquanto o bucket nao existe.
      // Revogar agora deixaria a pessoa olhando um vazio logo depois de enviar a foto.
      const local = { angulo, url: foto.miniatura };
      setFoto(null);
      onConcluido?.(r.data, local);
    } catch (e) {
      console.error("[forge] falha ao enviar a avaliação visual:", e);
      setFalha(explicar(e));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="vp-envio" data-testid="visual-photo-upload">
      {foto ? (
        <figure className="vp-previa">
          <img src={foto.miniatura} alt="Prévia da foto escolhida" />
          {!enviando && (
            <button
              type="button"
              className="vp-remover"
              aria-label="Trocar a foto"
              data-testid="trocar-foto"
              onClick={() => {
                URL.revokeObjectURL(foto.miniatura);
                setFoto(null);
              }}
            >
              <X size={15} />
            </button>
          )}
        </figure>
      ) : (
        <label className="vp-adicionar" data-testid="adicionar-fotos">
          <Camera size={26} aria-hidden="true" />
          <b>Adicionar foto</b>
          <span>Corpo inteiro, boa luz, sem contraluz.</span>
          <input
            ref={entrada}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            disabled={enviando}
            onChange={escolher}
          />
        </label>
      )}

      <div className="vp-angulo">
        <label htmlFor="vp-angulo-sel">Ângulo desta foto</label>
        <select
          id="vp-angulo-sel"
          value={angulo}
          data-testid="angulo-foto"
          disabled={enviando}
          onChange={(e) => setAngulo(e.target.value)}
        >
          {ANGULOS.map((a) => (
            <option key={a.id} value={a.id}>
              {a.rotulo}
            </option>
          ))}
        </select>
      </div>

      {falha && (
        <div className="vp-falha" role="alert" data-testid="visual-upload-error">
          <b>{falha.titulo}</b>
          <p>{falha.texto}</p>
          <button
            type="button"
            className="vp-tentar"
            data-testid="tentar-novamente"
            onClick={() => (foto ? enviar() : entrada.current?.click())}
          >
            <RefreshCw size={14} aria-hidden="true" /> Tentar novamente
          </button>
        </div>
      )}

      {enviando && (
        <div className="vp-progresso" data-testid="visual-upload-progress">
          <div className="vp-barra">
            <i style={{ width: `${progresso}%` }} />
          </div>
          <span>{progresso < 95 ? `Enviando ${progresso}%` : "Lendo a foto…"}</span>
        </div>
      )}

      <div className="vp-acoes">
        {onCancelar && !enviando && (
          <button type="button" className="vp-secundario" onClick={onCancelar}>
            Cancelar
          </button>
        )}
        <button
          type="button"
          className="vp-primario"
          data-testid="submit-visual-assessment"
          disabled={!foto || enviando}
          aria-busy={enviando}
          onClick={enviar}
        >
          {enviando ? "Enviando…" : "Enviar foto"}
        </button>
      </div>
    </div>
  );
}
