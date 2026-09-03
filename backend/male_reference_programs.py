"""Structured prescriptions from the three male reference PDFs supplied in September 2026.

Only training data is included, never the books' prose, photographs or branding.
Book blueprints deliberately identify the exercise selection as an editable adaptation.
"""
from copy import deepcopy


def build_male_reference_programs(ex, session, phase, program):
    common = "Duração em semanas e RIR não informados. RIR 2 é apenas valor editável de revisão FORGE; não representa o RIR da ficha. Tempos de sessão são estimativas. Revise a prescrição antes de salvar."
    double = "Dois períodos: manter os blocos 1 e 2 separados por 5–6 horas e revisar recuperação com profissional. O FORGE lista sessões em sequência, não agenda automaticamente dois horários nem os descansos. Não executar os dois blocos como uma sessão contínua."

    def e(id, sets, reps, rest=None, technique="straight", note=""):
        if rest is None:
            rest = "90 s"
            note = (note + " Descanso não informado: 90 s propostos para revisão.").strip()
        return ex(id, sets, reps, "2", rest, technique, note)

    def s(label, focus, entries, duration=75):
        return session(label, focus, entries, "HIGH", duration)

    def p(id, name, category, sessions, note, kind="Ficha transcrita", level="Avançado"):
        # Exercise notes survive the current custom-program save schema; phase notes do not.
        sessions = deepcopy(sessions)
        sessions[0]["exercises"][0]["note"] += " " + common + " " + note
        for workout in sessions:
            if "período" in workout["label"]:
                workout["exercises"][0]["note"] += " " + double
        return program("male-"+id, category, name, level, 0, "Masculino",
                       kind + ". " + note, "Material masculino enviado", [
                           phase("base", "Rotina completa", kind, sessions, "", common + " " + note)
                       ], "expert", "Alto volume e técnicas intensificadoras: revisão profissional necessária. " + note,
                       audience_type="male")

    pyramid = "15–20/10–15/8–12/6–10"
    abs_block = lambda: [e("hanging-leg-raise",3,"falha técnica"),e("reverse-crunch",3,"falha técnica"),e("decline-crunch",3,"falha técnica")]
    calves = lambda: [e("machine-standing-calf",4,"a definir","60 s",note="Super série remetida a vídeo não importado; repetições e sequência precisam ser definidas."),e("seated-calf",5,"10–15","30 s",note="Pico de contração de 3 s.")]
    pro = [
        s("A · Peito e ombros",["Peitoral","Deltoides"],[
            e("cable-fly",3,"10–15","30 s"),e("pec-deck",4,"10–15","30 s",note="Pico de 2 s."),
            e("bb-decline-press",3,"10–15/8–12/6–10","60 s","pyramid"),
            e("db-incline-press",5,"15–20/10–15/8–12/6–10/6–10","120 s","pyramid"),
            *[e(id,6,"8–12","60 s","superset","Tri-set: supino reto com halteres + crucifixo reto + supino inclinado com barra. Descanso após o trio; revisar as 6 séries indicadas.") for id in ["db-bench-press","db-fly","bb-incline-press"]],
            e("seated-db-front",3,"10–15","45 s"),e("smith-ohp",3,"10–15","30 s"),
        ],100),
        s("B1 · Abdômen e costas · período 1",["Core","Costas"],abs_block()+[
            e("pullup",3,"falha técnica","120 s"),
            e("cable-pulldown",6,"10–15/10–15/10–15/6–10/6–10/6–10","30 s",note="Dois blocos da mesma puxada: séries 1–3 com pico de 3 s e descanso 30 s; séries 4–6 com descanso 120 s. Ajustar o cronômetro no segundo bloco."),
            e("cable-straight-arm-pulldown",5,"10–15","45 s","superset","Bi-set com puxada supinada; pico de 2 s."),
            e("supinated-pulldown",5,"10–15","45 s","superset","Bi-set com pulldown; pico de 2 s."),
        ],85),
        s("B2 · Panturrilhas e costas · período 2",["Panturrilhas","Costas"],calves()+[
            e("supinated-bb-row",4,pyramid+" + drop",technique="pyramid",note="Pico de 2 s; drop na última série."),
            e("supinated-cable-row",3,"10–15","45 s",note="Pico de 2 s."),e("db-row",3,"10–15","30 s",note="Pico de 3 s."),
            e("cable-rear-delt-crossover",3,"10–15","30 s",note="Pico de 2 s."),e("rack-pull",4,pyramid,"120 s","pyramid"),e("back-extension",3,"10–15","30 s",note="Com sobrecarga. Descanso do programa após B2."),
        ],90),
        s("C · Peito e ombros",["Deltoides","Peitoral"],[
            e("db-ohp",4,pyramid+" + drop","120 s","pyramid"),e("seated-db-lateral",5,"8–12","60 s"),
            e("incline-lateral",3,"8–12","30 s"),e("lateral-raise",3,"8–12","30 s"),
            e("db-front-raise",3,"8–12","45 s",note="A ficha indica uma variante de elevação frontal nomeada por treinador; variante exata a revisar."),
            e("bb-front-raise",4,"8–12","60 s"),e("pec-deck",4,"8–12","45 s"),
        ]),
        s("D1 · Pernas · período 1",["Posteriores","Glúteos","Panturrilhas"],calves()+[
            e("lying-leg-curl",4,pyramid+" + drop","120 s","pyramid"),e("nordic-curl",3,"falha técnica"),
            e("seated-hamstring-curl",5,"8–12","60 s","superset","Bi-set com stiff."),e("rdl",5,"8–12","60 s","superset","Bi-set com flexora sentada."),e("hip-thrust",5,"8–12","45 s"),
        ],90),
        s("D2 · Pernas · período 2",["Quadríceps","Glúteos","Core"],abs_block()+[
            e("hip-thrust",3,"15–20","30 s",note="Pico de contração."),e("abductor-machine",3,"15–20","30 s"),
            e("bb-squat",4,pyramid,"120 s","pyramid"),e("leg-press",4,"8–12","45 s"),
            e("smith-lunge",3,"10–15","45 s",note="Afundo no Smith com step."),e("sumo-deadlift",4,"8–12","45 s",note="Sobre caixote; revisar amplitude e montagem."),e("adductor-machine",3,"10–15","30 s"),
        ],90),
        s("E · Braços",["Bíceps","Tríceps","Antebraços"],[
            e("incline-rope-skullcrusher",4,pyramid+" + drop","120 s","pyramid"),e("rope-pushdown",3,"10–15/8–12/6–10 + drop","60 s","pyramid"),
            e("db-overhead-extension",4,"8–12","45 s"),e("dip",3,"falha técnica","60 s"),
            e("bb-curl",5,pyramid+" + drop/6–10 + drop","120 s","pyramid"),e("cable-preacher",4,"8–12","45 s"),
            e("spider-curl",3,"8–12","30 s",note="Pico de 2 s."),e("incline-db-curl",3,"8–12","30 s"),e("wrist-flexion-extension",3,"10–15","30 s",note="Flexão e extensão; descanso do programa após E."),
        ],90),
    ]

    five = [
        s("A · Segunda · Peito",["Peitoral"],[
            e("pec-deck",5,"8–12",technique="drop-set",note="Tabela: 5 séries. Texto menciona 3 aquecimentos e etapas adicionais, divergindo do total; confirmar. Última com 2 drops de cerca de 30%."),
            e("bb-bench-press",4,"8–12",technique="rest-pause",note="Alternativa da ficha: máquina articulada. Duas primeiras de aquecimento; demais com 2 rest-pauses de 5 s."),
            e("db-incline-press",3,"falha técnica",technique="superset",note="Com crucifixo inclinado; reduzir cerca de 50% e retornar ao supino na mesma sequência."),
            e("db-incline-fly",3,"falha técnica",technique="superset",note="Par com supino inclinado conforme observação da ficha."),e("cable-fly",4,"8–12",note="Polia alta."),e("dip",2,"falha técnica",note="Ênfase peitoral."),
        ]),
        s("B · Terça · Pernas",["Quadríceps","Posteriores"],[
            e("bb-squat",5,"8–10",note="Ficha pede primeira série de aquecimento."),e("hack-squat",3,"8–10"),
            e("leg-press",3,"falha técnica",technique="superset",note="Bi-set com extensora."),e("leg-extension",3,"falha técnica",technique="superset",note="Bi-set com leg press."),e("lying-leg-curl",3,"8–10"),e("rdl",3,"falha técnica"),
        ]),
        s("C · Quinta · Braços",["Tríceps","Bíceps"],[
            e("ez-skullcrusher",1,"falha técnica",technique="rest-pause",note="Tabela: 1 série; texto acrescenta 2 aquecimentos e 2 rest-pauses finais. Negativas assistidas somente com supervisão."),
            e("rope-pushdown",3,"falha técnica",technique="drop-set",note="2 drops em cada série."),e("cable-overhead-extension",3,"falha técnica"),e("dip",3,"falha técnica"),
            e("cable-curl",5,"8–12",technique="drop-set",note="Ficha: 5–6 séries; inicia com 5. Dois drops de 30% na última."),
            e("incline-db-curl",4,"falha técnica",technique="superset",note="Bi-set com rosca em pé."),e("standing-db-curl",4,"falha técnica",technique="superset",note="Bi-set com rosca inclinada."),e("db-cable-curl",3,"falha técnica"),
        ],85),
        s("D · Sexta · Ombros",["Deltoides"],[
            e("machine-ohp",5,"15/15/10/10/10","90 s","pyramid",note="Progressão de carga. Descanso proposto; ausente na ficha."),
            e("seated-db-front",3,"falha técnica",technique="superset",note="Bi-set com elevação frontal em pé."),e("db-front-raise",3,"falha técnica",technique="superset",note="Bi-set com elevação frontal sentada."),
            e("seated-db-lateral",3,"falha técnica"),e("db-lateral-raise",1,"10 por carga",technique="pyramid",note="Uma série estendida: 4 cargas crescentes e retorno decrescente; 10 repetições por carga."),
        ],60),
        s("E · Sábado · Costas",["Costas","Deltoide posterior"],[
            e("bb-row",4,"20/15/10/drop",technique="drop-set",note="Repetições do drop não informadas."),e("cable-row",4,"10/10/10/drop",technique="drop-set",note="Repetições do drop não informadas."),
            e("row",3,"10–12",technique="superset",note="Remada articulada pronada; bi-set com crucifixo inverso."),e("db-rear-fly",3,"10–12",technique="superset",note="Equipamento não indicado para crucifixo inverso: halteres selecionados para revisão."),
            e("cable-pulldown",3,"10/8/6",technique="drop-set",note="Texto: 10–15, 8–12 com 1 drop, 6–10 com 2 drops de 30%; tabela usa 10/8/6. Confirmar alvo."),e("rack-pull",3,"6"),e("back-extension",4,"falha técnica"),
        ],80),
    ]

    # The book specifies muscle slots, not a fixed exercise for each slot.
    # Selections below are explicitly labelled adaptations and remain editable.
    def group(ids, load_first=True):
        return [e(id,3,"6–10" if i==0 and load_first else "8–12","150 s" if i==0 and load_first else "60 s",note="Adaptação FORGE: exercício escolhido para o espaço muscular do livro. "+("Carga, intervalo 2–3 min." if i==0 and load_first else "Técnica a escolher, intervalo 30–60 s.")+" Faixa de repetições escolhida dentre as alternativas do livro.") for i,id in enumerate(ids)]
    chest = ["bb-bench-press","db-incline-press","db-decline-press","db-fly","pec-deck","cable-fly"]
    back = ["cable-pulldown","bb-row","neutral-pulldown","cable-row","back-extension"]
    shoulders = ["db-ohp","seated-db-lateral","lateral-raise","db-front-raise","cable-rear-delt-crossover"]
    biceps = ["bb-curl","incline-db-curl","cable-preacher"]
    triceps = ["ez-skullcrusher","rope-pushdown","cable-overhead-extension"]
    quads = ["bb-squat","leg-press","hack-squat","leg-extension"]
    hams = ["lying-leg-curl","seated-hamstring-curl","rdl"]
    glutes = ["hip-thrust","sumo-deadlift"]
    def extra(id):
        return [e(id,3,"8–12","60 s",note="Adaptação FORGE: ficha permite 3–5 séries, inicia com 3. Repetições/descanso propostos para revisão.")]
    def calf():
        return [e("machine-standing-calf",3,"a definir","60 s",note="Livro remete a protocolo de panturrilhas sem detalhar nesta ficha. 3 séries/60 s propostos; definir repetições e técnica antes de salvar.")]
    def legs(label):
        return s(label,["Quadríceps","Posteriores","Panturrilhas"],calf()+group(quads[:3])+group(hams[:2]))
    def lower1(label,load_glute=False):
        g=group(glutes,load_glute)
        return s(label,["Posteriores","Glúteos"],group(hams)+g+extra("abductor-machine"))
    def lower2(label):
        return s(label,["Quadríceps","Panturrilhas","Adutores"],calf()+group(quads)+extra("adductor-machine"))
    def pusharms(label):
        return s(label,["Peitoral","Bíceps"],group(chest[:5])+group(biceps))
    def delttri(label):
        return s(label,["Deltoides","Tríceps","Trapézio"],group(shoulders[:4])+extra("db-shrug")+group(triceps))
    def pulls(label):
        return s(label,["Costas","Deltoide posterior"],group(back)+group(["cable-rear-delt-crossover"],False))
    def delt(label):
        return s(label,["Deltoides","Trapézio"],group(shoulders)+extra("db-shrug"))
    def arms(label):
        return s(label,["Bíceps","Tríceps","Antebraços"],group(biceps)+extra("wrist-flexion-extension")+group(triceps))
    def vertical(label):
        return s(label,["Costas","Panturrilhas"],calf()+group(["cable-pulldown","supinated-pulldown","neutral-pulldown","cable-straight-arm-pulldown"]))
    def horizontal(label):
        return s(label,["Costas","Deltoide posterior"],group(["bb-row","cable-row","wide-cable-row","db-row"])+group(["cable-rear-delt-crossover","back-extension"],False))

    blueprint = "Modelo adaptado do livro: os capítulos definem espaços por grupo muscular; os exercícios e técnicas devem ser revisados no editor. Aquecimento geral, mobilidade e aquecimento localizado antes da carga. Acessórios opcionais não são acrescentados automaticamente."
    programs = [
        p("abcde-professional","Treino ABCDE Profissional","abcde",pro,double+" Sete sessões em cinco dias de treino; descanso após B2 e E."),
        p("abcde-five-day","Ficha de Treino ABCDE Intensivo","abcde",five,"Segunda, terça, quinta, sexta e sábado; quarta de descanso. Descansos entre séries ausentes na ficha recebem 90 s editáveis. Aquecimentos e divergências estão nas notas."),
    ]
    configs = [
        ("book-abc","Treino 3 Vezes na Semana ABC","abc",[
            s("A · Peito, ombros e tríceps",["Peitoral","Deltoides","Tríceps"],group(chest[:3])+group(shoulders[:3])+group(triceps[:2])),
            legs("B · Pernas"),s("C · Costas e bíceps",["Costas","Bíceps"],group(back[:4])+group(biceps[:2])),
        ],"Segunda, quarta e sexta, com descanso entre sessões."),
        ("book-abcd","Treino 4 Vezes na Semana ABCD","abcd",[
            pusharms("A · Peito e bíceps"),s("B · Pernas",["Quadríceps","Posteriores","Adutores","Glúteos"],legs("B")["exercises"]+extra("adductor-machine")+extra("abductor-machine")),delttri("C · Ombros e tríceps"),pulls("D · Costas"),
        ],"A/B/descanso/C/D/descanso/descanso; alternativa de treino em dias intercalados."),
        ("book-abcde-1","Treino ABCDE Estratégia 1","abcde",[
            pulls("A · Costas"),s("B · Peito",["Peitoral"],group(chest)),s("C · Pernas",["Quadríceps","Posteriores","Glúteos"],legs("C")["exercises"]+extra("adductor-machine")+extra("abductor-machine")),delt("D · Ombros"),arms("E · Braços"),
        ],"Texto introdutório: descanso após três treinos; uma marcação interna aparece antes de C. Confirmar agenda no editor."),
        ("book-abcde-2","Treino ABCDE Estratégia 2","abcde",[
            pusharms("A · Peito e bíceps"),lower2("B · Pernas · quadríceps"),pulls("C · Costas"),delttri("D · Ombros e tríceps"),lower1("E · Pernas · posteriores e glúteos",True),
        ],"Descanso após B e E. Duas sessões de pernas com ênfases distintas."),
        ("book-abcde-3","Treino ABCDE Estratégia 3 Profissional","abcde",[
            s("A · Peito",["Peitoral"],group(chest)),vertical("B1 · Costas · período 1"),horizontal("B2 · Costas · período 2"),delt("C · Ombros"),arms("D · Braços"),lower1("E1 · Pernas · período 1"),lower2("E2 · Pernas · período 2"),
        ],double+" Sete sessões em cinco dias; descanso após B2 e E2. Estrutura diferente da ficha ABCDE Profissional detalhada."),
        ("book-abcdef","Treino 6 Vezes na Semana ABCDEF","abcdef",[
            pulls("A · Costas"),s("B · Peito",["Peitoral"],group(chest)),s("C · Pernas · posteriores",["Posteriores","Glúteos","Panturrilhas"],calf()+lower1("C")["exercises"]),arms("D · Braços"),delt("E · Ombros"),lower2("F · Pernas · quadríceps"),
        ],"A/B/C/descanso/D/E/F/descanso: seis sessões em ciclo de oito dias, não seis dias consecutivos."),
        ("book-abcd-pro","Treino ABCD Profissional","abcd",[
            pusharms("A · Peito e bíceps"),lower1("B1 · Pernas · período 1"),lower2("B2 · Pernas · período 2"),delttri("C · Ombros e tríceps"),vertical("D1 · Costas · período 1"),horizontal("D2 · Costas · período 2"),
        ],double+" Seis sessões em quatro dias de treino; confirmar calendário intercalado e dias de descanso."),
    ]
    for id,name,category,sessions,note in configs:
        programs.append(p(id,name,category,deepcopy(sessions),blueprint+" "+note,"Modelo adaptado", "Intermediário" if category=="abc" else "Avançado"))
    return programs
