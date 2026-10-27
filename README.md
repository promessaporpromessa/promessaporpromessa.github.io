# Promessa por Promessa

Um site para acompanhar o 4º mandato de Lula (2027–2030), promessa por promessa: o que foi prometido, como o Congresso vota, o que muda na economia e como as pessoas reagem nas redes. Cada número tem fonte.

**Site:** https://mathhbasilio28.github.io/Promessa-por-Promessa/

## Como funciona
- `index.html`: a página (estática, sem build).
- `data/*.json`: os dados de cada painel. `data/index.json` lista os conjuntos e a data da última atualização.
- `js/dash-shim.js`: lê os JSON e entrega para a página.
- Os dados são atualizados automaticamente por tarefas agendadas (diária, dias úteis às 19h47, e semanal, segunda às 8h42, horário de Brasília), que fazem commit direto em `data/`.

Curadoria: [Matheus Brandão](https://www.linkedin.com/in/matheusbbrandao/). Caricatura gerada por IA.
