import { lerAltura, emMetros, ALTURA_MIN_CM, ALTURA_MAX_CM } from "./alturaEmCm";
import "./campo-altura.css";

/**
 * Campo de altura que entende metro e centimetro, e diz o que entendeu.
 *
 * A alternativa obvia seria um seletor "m / cm" ao lado. Nao e o certo aqui: adiciona uma
 * decisao a um formulario que ja tem muitas, e nao elimina o erro — quem digita "1,80" com
 * o seletor em "cm" erra exatamente igual, e agora com a interface concordando com ele.
 *
 * Este campo aceita as duas formas, converte, e ECOA a leitura embaixo. A confirmacao
 * substitui o seletor: a pessoa ve "1,80 m = 180 cm" e segue, ou corrige na hora. Quando o
 * valor ja veio em centimetros, o eco nao aparece — aviso que sempre aparece vira moldura,
 * e para de ser lido.
 */
export default function CampoAltura({ valor, aoMudar, id = "campo-altura", testid = "assessment-height_cm" }) {
  const leitura = lerAltura(valor);
  const ecoId = `${id}-eco`;

  return (
    <label className="deep-field fg-altura" htmlFor={id}>
      <span>Altura</span>

      <span className="fg-altura-caixa">
        <input
          id={id}
          data-testid={testid}
          type="text"
          /* `decimal` traz o teclado com virgula no celular; `number` esconderia a virgula
             em parte dos aparelhos, que e justamente como a pessoa escreve 1,80. */
          inputMode="decimal"
          autoComplete="off"
          placeholder="1,80 ou 180"
          aria-describedby={ecoId}
          value={valor ?? ""}
          onChange={(e) => aoMudar(e.target.value)}
        />
        <span className="fg-altura-unidade" aria-hidden="true">
          {leitura.interpretado ? "m" : "cm"}
        </span>
      </span>

      {/*
        `aria-live` porque o eco e a confirmacao: quem usa leitor de tela precisa ouvir a
        leitura mudar, nao descobrir depois que o plano saiu errado.
      */}
      <span className="fg-altura-eco" id={ecoId} role="status" aria-live="polite">
        {leitura.cm === null ? (
          ""
        ) : leitura.foraDeFaixa ? (
          <em className="fg-altura-alerta" data-testid="altura-fora-de-faixa">
            {leitura.cm} cm está fora do que uma pessoa tem. Confira o número.
          </em>
        ) : leitura.interpretado ? (
          <em data-testid="altura-convertida">
            {emMetros(leitura.cm)} = <b>{leitura.cm} cm</b>
          </em>
        ) : (
          <em data-testid="altura-confirmada">{emMetros(leitura.cm)}</em>
        )}
      </span>
    </label>
  );
}

export { ALTURA_MIN_CM, ALTURA_MAX_CM };
