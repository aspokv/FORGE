import {Camera, Image as ImageIcon, Minus, Plus} from "lucide-react";
import {prender} from "../lib/layout";

/**
 * Enquadramento da foto: zoom e deslocamento.
 *
 * Não existe corte destrutivo. A foto original continua inteira no servidor e o que se
 * guarda é uma transformação — escala e deslocamento normalizados. Isso deixa o atleta
 * voltar ao editor depois e reenquadrar sem ter perdido as bordas, e é a diferença entre
 * "ajustar o enquadramento" e "recortar a foto para sempre".
 *
 * O zoom vai de 1 a 3. Abaixo de 1 apareceria tarja preta na peça; acima de 3 uma foto de
 * 1920 px começa a mostrar pixel na exportação.
 */
const PASSO_DE_ZOOM = 0.15;
const ZOOM_MINIMO = 1;
const ZOOM_MAXIMO = 3;
const PASSO_DE_DESLOCAMENTO = 0.04;

export default function ImageCropController({transform, temFoto, onMudar, onEscolherFoto}) {
  const t = {scale: 1, offsetX: 0, offsetY: 0, ...(transform || {})};

  const aplicar = mudanca => onMudar({
    scale: prender(mudanca.scale ?? t.scale, ZOOM_MINIMO, ZOOM_MAXIMO),
    offsetX: prender(mudanca.offsetX ?? t.offsetX, -0.5, 0.5),
    offsetY: prender(mudanca.offsetY ?? t.offsetY, -0.5, 0.5),
  });

  return (
    <section className="fc-crop" data-testid="fc-crop">
      <div className="fc-crop-fonte">
        <label className="fc-acao-secundaria">
          <Camera size={15} /> Tirar foto
          <input type="file" accept="image/*" capture="environment" hidden
                 data-testid="fc-crop-camera"
                 onChange={e => e.target.files?.[0] && onEscolherFoto(e.target.files[0])} />
        </label>
        <label className="fc-acao-secundaria">
          <ImageIcon size={15} /> Escolher da galeria
          <input type="file" accept="image/*" hidden
                 data-testid="fc-crop-galeria"
                 onChange={e => e.target.files?.[0] && onEscolherFoto(e.target.files[0])} />
        </label>
      </div>

      {temFoto ? (
        <>
          <div className="fc-crop-linha">
            <span>Zoom</span>
            <div className="fc-crop-botoes">
              <button type="button" aria-label="Diminuir o zoom" data-testid="fc-zoom-menos"
                      onClick={() => aplicar({scale: t.scale - PASSO_DE_ZOOM})}>
                <Minus size={16} />
              </button>
              <input type="range" min={ZOOM_MINIMO} max={ZOOM_MAXIMO} step="0.01"
                     value={t.scale} aria-label="Zoom da foto" data-testid="fc-zoom"
                     onChange={e => aplicar({scale: Number(e.target.value)})} />
              <button type="button" aria-label="Aumentar o zoom" data-testid="fc-zoom-mais"
                      onClick={() => aplicar({scale: t.scale + PASSO_DE_ZOOM})}>
                <Plus size={16} />
              </button>
            </div>
          </div>

          <div className="fc-crop-linha">
            <span>Posição</span>
            <div className="fc-crop-direcional" role="group" aria-label="Mover a foto">
              <button type="button" aria-label="Mover a foto para cima" data-testid="fc-mover-cima"
                      onClick={() => aplicar({offsetY: t.offsetY - PASSO_DE_DESLOCAMENTO})}>↑</button>
              <button type="button" aria-label="Mover a foto para a esquerda" data-testid="fc-mover-esquerda"
                      onClick={() => aplicar({offsetX: t.offsetX - PASSO_DE_DESLOCAMENTO})}>←</button>
              <button type="button" aria-label="Centralizar a foto" data-testid="fc-mover-centro"
                      onClick={() => aplicar({offsetX: 0, offsetY: 0, scale: 1})}>•</button>
              <button type="button" aria-label="Mover a foto para a direita" data-testid="fc-mover-direita"
                      onClick={() => aplicar({offsetX: t.offsetX + PASSO_DE_DESLOCAMENTO})}>→</button>
              <button type="button" aria-label="Mover a foto para baixo" data-testid="fc-mover-baixo"
                      onClick={() => aplicar({offsetY: t.offsetY + PASSO_DE_DESLOCAMENTO})}>↓</button>
            </div>
          </div>
        </>
      ) : (
        <p className="fc-crop-vazio">
          A foto do prato é o fundo da peça. Ela continua sua: o FORGE não altera a
          fotografia, só desenha por cima.
        </p>
      )}
    </section>
  );
}
