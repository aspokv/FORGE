import {useRef, useState} from "react";
import {ArrowLeft, Download, Eye, Image as ImageIcon, Share2, Sliders, Utensils} from "lucide-react";
import FoodCardCanvas from "./FoodCardCanvas";
import ImageCropController from "./ImageCropController";
import useFoodCard from "../hooks/useFoodCard";
import useFoodCardDrag from "../hooks/useFoodCardDrag";
import useFoodCardExport from "../hooks/useFoodCardExport";
import {MACROS, ROTULO_DO_MACRO} from "../lib/conteudo";
import "../food-card.css";

/**
 * O editor do Forge Food Card.
 *
 * Deliberadamente NÃO é um editor gráfico. O atleta move card e âncora, ajusta o
 * enquadramento da foto e troca qual macro destacar. Fonte, cor, borda, estilo dos cards e
 * a identidade FORGE não são editáveis — é o que faz um Food Card sempre parecer um Food
 * Card, em vez de um modelo que cada um descaracteriza do seu jeito.
 *
 * A prévia remove seleção, alças e contornos e mostra exatamente o que o PNG vai ter.
 */
const ABAS = [
  {id: "foto", rotulo: "Foto", Icone: ImageIcon},
  {id: "alimentos", rotulo: "Alimentos", Icone: Utensils},
  {id: "layout", rotulo: "Layout", Icone: Sliders},
];

export default function FoodCardEditor({API, cardId, onVoltar, axiosCliente}) {
  const escalaRef = useRef({current: 1});
  const [aba, setAba] = useState("foto");
  const [preview, setPreview] = useState(false);

  const {card, estado, erro, salvando, mover, confirmarMovimento, ajustarFoto,
         trocarMacro, enviarFoto, fotoFalhou, setErro} = useFoodCard({API, cardId, axiosCliente});
  const arrasto = useFoodCardDrag({
    items: card?.items || [], escalaRef: escalaRef.current,
    aoMover: mover, aoSoltar: confirmarMovimento,
  });
  const exportacao = useFoodCardExport();

  if (estado === "carregando") {
    return <div className="fc-editor fc-editor-carregando" role="status">
      Abrindo seu Food Card…
    </div>;
  }
  if (estado === "erro" || !card) {
    return <div className="fc-editor fc-editor-carregando">
      <p role="alert">{erro || "Não foi possível abrir este Food Card."}</p>
      <button type="button" className="fc-acao-secundaria" onClick={onVoltar}>Voltar</button>
    </div>;
  }

  const paraExportar = {
    imagem: card.imageUrl, imageTransform: card.imageTransform,
    items: card.items, summary: card.summary,
  };

  return (
    <div className="fc-editor" data-testid="fc-editor">
      <header className="fc-editor-topo">
        <button type="button" aria-label="Voltar" data-testid="fc-voltar" onClick={onVoltar}>
          <ArrowLeft size={18} />
        </button>
        <div>
          <span className="fc-editor-etiqueta">FORGE FOOD CARD</span>
          <small data-testid="fc-estado-salvo">
            {salvando ? "Salvando…" : "Salvo automaticamente"}
          </small>
        </div>
        <button type="button" className={preview ? "fc-preview-ativo" : ""}
                data-testid="fc-preview" aria-pressed={preview}
                onClick={() => setPreview(x => !x)}>
          <Eye size={17} /> {preview ? "Editar" : "Visualizar"}
        </button>
      </header>

      <div className="fc-editor-palco"
           onPointerMove={preview ? undefined : arrasto.mover}
           onPointerUp={preview ? undefined : arrasto.soltar}
           onPointerCancel={preview ? undefined : arrasto.soltar}>
        <FoodCardCanvas
          imagem={card.imageUrl} imageTransform={card.imageTransform}
          items={card.items} summary={card.summary}
          selecionado={arrasto.selecionado} modoPreview={preview}
          escalaRef={escalaRef.current}
          onFotoFalhou={fotoFalhou}
          onPointerDownCard={arrasto.noCard}
          onPointerDownAncora={arrasto.naAncora}
          onFundoPressionado={arrasto.limparSelecao} />
      </div>

      {erro ? <p className="fc-erro" role="alert" data-testid="fc-erro">{erro}</p> : null}
      {exportacao.erro ? (
        <p className="fc-erro" role="alert" data-testid="fc-erro-exportacao">
          {exportacao.erro} Seu Food Card continua salvo.
        </p>
      ) : null}

      {!preview && (
        <>
          <nav className="fc-abas" role="tablist" aria-label="Controles do Food Card">
            {ABAS.map(({id, rotulo, Icone}) => (
              <button key={id} type="button" role="tab" aria-selected={aba === id}
                      className={aba === id ? "ativa" : ""} data-testid={`fc-aba-${id}`}
                      onClick={() => setAba(id)}>
                <Icone size={16} /> {rotulo}
              </button>
            ))}
          </nav>

          <div className="fc-painel">
            {aba === "foto" && (
              <ImageCropController transform={card.imageTransform} temFoto={!!card.imageUrl}
                                   onMudar={ajustarFoto}
                                   onEscolherFoto={async arquivo => {
                                     setErro("");
                                     await enviarFoto(arquivo);
                                   }} />
            )}
            {aba === "alimentos" && (
              <ul className="fc-lista-de-itens" data-testid="fc-lista-de-itens">
                {card.items.map((item, i) => (
                  <li key={item.foodId || i}>
                    <b>{item.name}</b>
                    <div role="group" aria-label={`Macro destacado de ${item.name}`}>
                      {MACROS.map(macro => (
                        <button key={macro} type="button"
                                aria-pressed={item.primaryMacro === macro}
                                className={item.primaryMacro === macro ? "ativo" : ""}
                                data-testid={`fc-macro-${i}-${macro}`}
                                onClick={() => trocarMacro(i, macro)}>
                          {ROTULO_DO_MACRO[macro]}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {aba === "layout" && (
              <p className="fc-dica">
                Toque num card para selecioná-lo e arraste para onde quiser. Arraste o
                ponto branco para apontar exatamente o alimento na foto — a linha
                acompanha sozinha.
              </p>
            )}
          </div>
        </>
      )}

      <footer className="fc-editor-acoes">
        <button type="button" className="fc-acao-principal" data-testid="fc-compartilhar"
                disabled={exportacao.estado === "gerando"}
                onClick={() => exportacao.compartilhar(paraExportar)}>
          <Share2 size={16} />
          {exportacao.estado === "gerando" ? "Gerando…" : "Compartilhar"}
        </button>
        <button type="button" className="fc-acao-secundaria" data-testid="fc-baixar"
                disabled={exportacao.estado === "gerando"}
                onClick={() => exportacao.baixar(paraExportar)}>
          <Download size={16} /> Salvar imagem
        </button>
      </footer>
    </div>
  );
}
