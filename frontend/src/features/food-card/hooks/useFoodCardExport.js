import {useCallback, useState} from "react";
import {exportarFoodCard, nomeDoArquivo} from "../lib/exportar";

/**
 * Exportar e compartilhar a peça.
 *
 * A regra que manda aqui: **falha de exportação nunca apaga o trabalho**. O Food Card
 * fica salvo no servidor antes de qualquer tentativa, então um erro de canvas, de memória
 * ou de permissão devolve uma mensagem e deixa o editor exatamente como estava.
 *
 * O compartilhamento usa a Web Share API quando ela aceita arquivo — `canShare` com o
 * arquivo em mãos, e não só `navigator.share`, porque há navegador que tem `share` para
 * texto e recusa arquivo. Sem ela, cai no download, que funciona em todo lugar.
 */
export default function useFoodCardExport() {
  const [estado, setEstado] = useState("parado");   // parado | gerando | pronto | erro
  const [erro, setErro] = useState("");

  const gerar = useCallback(async card => {
    setEstado("gerando");
    setErro("");
    try {
      const blob = await exportarFoodCard(card);
      setEstado("pronto");
      return blob;
    } catch (e) {
      setEstado("erro");
      setErro(e?.message || "Não foi possível gerar a imagem agora.");
      return null;
    }
  }, []);

  const baixar = useCallback(async card => {
    const blob = await gerar(card);
    if (!blob) return false;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = nomeDoArquivo();
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Liberar na hora cortaria o download em alguns navegadores; um quadro depois é o
    // suficiente para o navegador já ter lido o blob.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  }, [gerar]);

  const compartilhar = useCallback(async card => {
    const blob = await gerar(card);
    if (!blob) return false;
    const arquivo = new File([blob], nomeDoArquivo(), {type: "image/png"});
    if (navigator.canShare?.({files: [arquivo]})) {
      try {
        await navigator.share({files: [arquivo], title: "FORGE Food Card"});
        return true;
      } catch (e) {
        // Cancelar o menu do sistema não é erro: é o atleta mudando de ideia, e mostrar
        // "falhou" aqui seria mentir sobre o que aconteceu.
        if (e?.name === "AbortError") return false;
      }
    }
    return await baixar(card);
  }, [gerar, baixar]);

  return {estado, erro, gerar, baixar, compartilhar,
          podeCompartilhar: typeof navigator !== "undefined" && !!navigator.canShare};
}
