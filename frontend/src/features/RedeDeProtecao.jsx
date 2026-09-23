import {Component} from "react";
import "./rede-de-protecao.css";

/**
 * A rede que impede a tela de ficar preta.
 *
 * Sem isto, QUALQUER exceção durante a renderização derruba a árvore inteira do React e o
 * atleta fica olhando uma tela preta, sem mensagem, sem botão, sem saber se o problema é
 * dele, da internet ou do aplicativo. Foi exatamente o que aconteceu quando um erro de
 * plano (402) chegou como objeto e alguém tentou renderizá-lo.
 *
 * A causa daquele caso está corrigida na origem — nada que vem da rede vai para a tela sem
 * passar por `mensagemDeErro`. Esta rede existe para o PRÓXIMO caso, o que ninguém previu:
 * a diferença entre "algo quebrou, recarregue" e uma tela preta é a diferença entre um
 * incidente e um usuário perdido.
 *
 * Não tenta consertar nem esconder: mostra o que houve, oferece recarregar, e deixa o erro
 * inteiro no console para quem for investigar.
 */
export default class RedeDeProtecao extends Component {
  constructor(props) {
    super(props);
    this.state = {quebrou: false, mensagem: ""};
  }

  static getDerivedStateFromError(erro) {
    return {quebrou: true, mensagem: String(erro?.message || erro || "")};
  }

  componentDidCatch(erro, info) {
    // O console é onde isto é investigado depois. Guardar só a mensagem curta perderia a
    // pilha, que é o que diz QUAL componente caiu.
    console.error("[FORGE] a tela quebrou:", erro, info?.componentStack);
  }

  render() {
    if (!this.state.quebrou) return this.props.children;
    return (
      <div className="rede-protecao" role="alert" data-testid="rede-de-protecao">
        <h2>Não foi possível exibir esta tela.</h2>
        <p>
          Os registros já salvos continuam na sua conta. Alterações sem confirmação de
          salvamento podem precisar ser preenchidas novamente.
        </p>
        <button type="button" className="fg-btn fg-btn-cheio"
                onClick={() => window.location.reload()}>
          Recarregar o FORGE
        </button>
      </div>
    );
  }
}
