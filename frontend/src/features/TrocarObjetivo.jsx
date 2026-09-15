import {useEffect, useState} from "react";
import axios from "axios";
import {Target} from "lucide-react";
import "./trocar-objetivo.css";
import {mensagemDeErro} from "./mensagemDeErro";

/**
 * Trocar o objetivo alimentar e o ritmo, direto da Nutricao.
 *
 * Antes, sair de emagrecimento para ganho de massa exigia refazer o questionario inteiro —
 * peso, altura, idade, dias, refeicoes — para mudar dois campos. Objetivo e a coisa que
 * mais muda ao longo do ano e era a mais cara de mudar.
 *
 * Fechado por padrao: quem abre a Nutricao todo dia vem olhar o plano, e nao trocar de
 * objetivo. Deixar aberto empurraria o plano do dia para fora da primeira dobra.
 */
export default function TrocarObjetivo({API, objetivoAtual, intensidadeAtual, onTrocado}) {
  const [aberto, setAberto] = useState(false);
  const [catalogo, setCatalogo] = useState(null);
  const [objetivo, setObjetivo] = useState(objetivoAtual || "");
  const [intensidade, setIntensidade] = useState(intensidadeAtual || "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [resultado, setResultado] = useState(null);
  // Qual plano tem o ritmo bloqueado, e em qual plano a conta esta. Sem isso o card
  // bloqueado vira um beco: a pessoa ve que nao pode e nao ve onde poderia.
  const [planos, setPlanos] = useState({});

  useEffect(() => {
    if (!aberto || catalogo) return;
    let vivo = true;
    axios.get(`${API}/nutrition/goal-catalog`)
      .then(r => { if (vivo) { setCatalogo(r.data?.goals || []); setPlanos(r.data || {}); } })
      .catch(() => { if (vivo) setErro("Não foi possível carregar os objetivos."); });
    return () => { vivo = false; };
  }, [API, aberto, catalogo]);

  const escolhido = (catalogo || []).find(g => g.id === objetivo);
  const ritmos = escolhido?.intensities || [];

  const trocarObjetivo = (id) => {
    setErro(""); setResultado(null);
    setObjetivo(id);
    // Cada objetivo tem os ritmos dele: carregar o ritmo do objetivo anterior gravaria
    // uma combinacao que nao existe, tipo "manutencao agressiva".
    const alvo = (catalogo || []).find(g => g.id === id);
    setIntensidade(alvo?.default_intensity || "");
  };

  const salvar = async () => {
    setSalvando(true); setErro(""); setResultado(null);
    try {
      const r = await axios.put(`${API}/nutrition/goal`,
        {goal: objetivo, intensity: intensidade || null});
      setResultado(r.data);
      if (onTrocado) onTrocado(r.data);
    } catch (e) {
      // NUNCA o detalhe cru: em 402 ele e um objeto, e renderizar objeto derruba a tela.
      setErro(mensagemDeErro(e, "Não foi possível trocar o objetivo agora."));
    } finally { setSalvando(false); }
  };

  const mudou = objetivo !== (objetivoAtual || "") || (intensidade || "") !== (intensidadeAtual || "");
  const rotuloAtual = (catalogo || []).find(g => g.id === objetivoAtual)?.label;

  return <section className="objetivo" data-testid="trocar-objetivo">
    <button type="button" className="objetivo-topo" aria-expanded={aberto}
            data-testid="abrir-objetivo" onClick={() => setAberto(v => !v)}>
      <Target size={17} aria-hidden="true" />
      <span>
        <strong>Meu objetivo</strong>
        <small>{rotuloAtual || "Emagrecimento, ganho de massa ou manutenção"}</small>
      </span>
      <span className="objetivo-seta" aria-hidden="true">{aberto ? "▾" : "▸"}</span>
    </button>

    {aberto && <div className="objetivo-corpo">
      {!catalogo && !erro && <div className="fg-esqueleto" aria-label="Carregando objetivos" />}

      {(catalogo || []).map(g => (
        <button type="button" key={g.id} aria-pressed={objetivo === g.id}
                className={objetivo === g.id ? "objetivo-opcao marcada" : "objetivo-opcao"}
                data-testid={`objetivo-${g.id}`} onClick={() => trocarObjetivo(g.id)}>
          <b>{g.label}</b>
          <small>{g.description}</small>
        </button>
      ))}

      {ritmos.length > 0 && <div className="objetivo-ritmos">
        <p className="fg-etiqueta">Ritmo</p>
        {/* Ritmo que este plano nao inclui vem com `locked` do servidor e NAO e clicavel.
            Antes ele era escolhivel como qualquer outro e so o "Salvar" recusava, com um
            402 — a pessoa escolhia, esperava, e levava "seu plano atual nao inclui este
            recurso" sem nunca ter sido avisada. Oferecer e depois recusar e pior do que
            deixar claro desde o inicio. Continua visivel de proposito: esconder faria
            parecer que o FORGE nao tem o recurso, quando quem nao tem e o plano. */}
        {ritmos.map(op => (
          <button type="button" key={op.id} aria-pressed={intensidade === op.id}
                  disabled={Boolean(op.locked)}
                  className={[
                    "objetivo-ritmo",
                    intensidade === op.id ? "marcada" : "",
                    op.locked ? "bloqueada" : "",
                  ].filter(Boolean).join(" ")}
                  data-testid={`ritmo-${op.id}`}
                  onClick={() => { if (op.locked) return; setIntensidade(op.id); setResultado(null); }}>
            <span className="objetivo-ritmo-nome">
              {op.label}
              {op.recommended && <em className="objetivo-tag">recomendado</em>}
              {op.advanced && !op.locked && <em className="objetivo-tag avancado">avançado</em>}
              {op.locked && <em className="objetivo-tag bloqueada"
                                data-testid={`ritmo-bloqueado-${op.id}`}>
                {planos.plan_for_advanced || "plano superior"}
              </em>}
            </span>
            <small>{op.description}</small>
            {op.locked && <span className="objetivo-bloqueio">
              {planos.current_plan
                ? `Seu plano ${planos.current_plan} não inclui este ritmo.`
                : "Seu plano atual não inclui este ritmo."}
              {" "}Veja os planos no seu perfil para liberar.
            </span>}
            {/* O aviso do protocolo extremo viaja com a opcao e nao pode ser omitido: ele
                e o que separa uma escolha informada de uma surpresa. */}
            {op.warning && intensidade === op.id && <span className="objetivo-aviso">{op.warning}</span>}
          </button>
        ))}
      </div>}

      {erro && <p className="fg-erro" role="alert">{erro}</p>}

      {resultado && <div className="objetivo-resultado" role="status" data-testid="objetivo-resultado">
        <p>Meta atualizada: <b>{Math.round(resultado.targets?.goal_calories || 0)} kcal</b> por dia
          · P {Math.round(resultado.targets?.protein_g || 0)} g
          · C {Math.round(resultado.targets?.carbs_g || 0)} g
          · G {Math.round(resultado.targets?.fat_g || 0)} g</p>
        {/* O cardapio NAO e regerado de proposito: um plano montado refeicao por refeicao
            sumindo sozinho seria pior que um alvo novo. A pessoa decide. */}
        <small>Suas refeições continuam as mesmas. Use “Montar refeição por refeição” se
          quiser refazer o cardápio com a meta nova.</small>
      </div>}

      <button type="button" className="fg-btn fg-btn-cheio" disabled={salvando || !mudou || !objetivo}
              data-testid="salvar-objetivo" onClick={salvar}>
        {salvando ? "Salvando…" : "Salvar objetivo"}
      </button>
    </div>}
  </section>;
}
