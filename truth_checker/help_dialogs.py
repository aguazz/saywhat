import streamlit as st


# ── Dialog 1: Claims ──────────────────────────────────────────────────────────

@st.dialog("What is a claim?")
def claims_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Una **afirmación** es una declaración sobre el mundo con la que se puede estar de acuerdo o en desacuerdo. "
            "No todas las frases son afirmaciones: las preguntas, los saludos y los chistes se descartan. "
            "Solo se conservan las aseveraciones sustantivas."
        )
        st.markdown("**Tipos de afirmación**")
        st.markdown(
            "| Tipo | Qué asevera | Ejemplo |\n"
            "|------|-------------|--------|\n"
            "| Factual | Algo que ocurrió o existe | *«Oslo prohibió los coches en 2019»* |\n"
            "| Estadística | Un número o cantidad | *«Los negocios cayeron un 15 % el primer año»* |\n"
            "| Causal | Una cosa causó otra | *«Más tráfico peatonal impulsó los ingresos»* |\n"
            "| Predictiva | Lo que ocurrirá | *«Houston se paralizaría sin coches»* |\n"
            "| Comparativa | Una comparación | *«El transporte de Oslo es mejor que el de Houston»* |\n"
            "| Interpretativa | El significado de algo | *«Una caída de un año no es un problema real»* |\n"
            "| Moral | Lo que debería hacerse | *«Las ciudades deberían prohibir los coches»* |\n"
            "| Definitoria | El significado de un término | *«Una zona peatonal no es una ciudad sin coches»* |\n"
            "| Anecdótica | Un caso personal aislado | *«La tienda de mi primo duplicó sus ventas»* |"
        )
        st.caption("La herramienta extrae 3-6 afirmaciones por turno de hablante, no cada frase.")
    else:
        st.markdown(
            "A **claim** is a statement about the world that can be agreed or disagreed with. "
            "Not every sentence is a claim: questions, greetings, and jokes are filtered out. "
            "Only substantive assertions are kept."
        )
        st.markdown("**Claim types**")
        st.markdown(
            "| Type | What it asserts | Example |\n"
            "|------|----------------|--------|\n"
            "| Factual | Something that happened or exists | *'Oslo tried a car ban in 2019'* |\n"
            "| Statistical | A number or quantity | *'Businesses dropped 15% in year one'* |\n"
            "| Causal | One thing caused another | *'Higher foot traffic drove revenue up'* |\n"
            "| Predictive | What will happen | *'Houston would be paralyzed without cars'* |\n"
            "| Comparative | A comparison | *'Oslo's transit is better than Houston's'* |\n"
            "| Interpretive | What something means | *'A one-year dip isn't a real problem'* |\n"
            "| Moral | What should be done | *'Cities should ban cars downtown'* |\n"
            "| Definitional | What a term means | *'A pedestrian zone isn't a car-free city'* |\n"
            "| Anecdotal | A single personal case | *'My cousin's shop doubled its sales'* |"
        )
        st.caption("The app extracts 3–6 claims per speaker turn, not every sentence.")


# ── Dialog 2: Threads ─────────────────────────────────────────────────────────

@st.dialog("What are threads?")
def threads_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Un **hilo** es un grupo de afirmaciones que tratan el mismo subtema, "
            "independientemente de quién las hizo."
        )
        st.markdown(
            "Los hilos permiten ver qué temas generaron más intercambio "
            "y cuáles quedaron sin resolver."
        )
        st.markdown("**Ejemplo** — debate Alex / Sam sobre los coches en el centro:")
        st.markdown(
            "| Hilo | Afirmaciones |\n"
            "|------|-------------|\n"
            "| Efectos en la calidad del aire | C1 (Alex), C2 (Sam) |\n"
            "| Impacto económico en los negocios | C3 (Sam), C4 (Alex), C5 (Alex) |\n"
            "| Generalización a otras ciudades | C6 (Sam), C7 (Sam) |"
        )
        st.caption("Un debate típico genera entre 3 y 8 hilos.")
    else:
        st.markdown(
            "A **thread** is a group of claims that address the same sub-topic, "
            "regardless of who made them."
        )
        st.markdown(
            "Threads let you see which subjects generated the most back-and-forth "
            "and which were left unresolved."
        )
        st.markdown("**Example** — Alex / Sam debate on cars in city centres:")
        st.markdown(
            "| Thread | Claims |\n"
            "|--------|--------|\n"
            "| Air quality effects | C1 (Alex), C2 (Sam) |\n"
            "| Economic impact on businesses | C3 (Sam), C4 (Alex), C5 (Alex) |\n"
            "| Generalizability to other cities | C6 (Sam), C7 (Sam) |"
        )
        st.caption("A typical debate produces 3–8 threads.")


# ── Dialog 3: Responses ───────────────────────────────────────────────────────

@st.dialog("How claims respond to each other")
def responses_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Cada vez que un hablante aborda una afirmación anterior, esa conexión es una **respuesta**. "
            "Las respuestas son las flechas del mapa de argumentos."
        )
        st.markdown("**Tipos de respuesta**")
        st.markdown(
            "| Tipo | Qué hace |\n"
            "|------|----------|\n"
            "| **refutes** | Niega directamente la conclusión |\n"
            "| **undercuts** | Cuestiona la evidencia, no la conclusión |\n"
            "| **supports** | Añade evidencia a favor |\n"
            "| **weakens** | Acepta pero reduce el alcance |\n"
            "| **reframes** | Acepta los hechos, cambia su significado |\n"
            "| **concedes** | Reconoce que el otro lado tiene razón |\n"
            "| **evades** | Cambia de tema |\n"
            "| **ignores** | Introduce un punto no relacionado |"
        )
        st.info(
            "**refutes** = «estás equivocado.»  \n"
            "**undercuts** = «tu evidencia no lo demuestra — aunque puede que tengas razón.»  \n\n"
            "Ejemplo: Sam dice que la cifra del 40 % de NO₂ proviene de «una sola calle en Madrid». "
            "Eso es un **undercut**: Sam no niega que la calidad del aire mejore, "
            "solo que este dato no lo prueba."
        )
    else:
        st.markdown(
            "Every time a speaker addresses a prior claim, that connection is a **response**. "
            "Responses are the arrows in the argument map."
        )
        st.markdown("**Response types**")
        st.markdown(
            "| Type | What it does |\n"
            "|------|--------------|\n"
            "| **refutes** | Directly denies the conclusion |\n"
            "| **undercuts** | Challenges the evidence, not the conclusion |\n"
            "| **supports** | Adds evidence in favour |\n"
            "| **weakens** | Accepts but limits scope |\n"
            "| **reframes** | Accepts facts, changes their meaning |\n"
            "| **concedes** | Acknowledges the other side has a point |\n"
            "| **evades** | Changes the subject |\n"
            "| **ignores** | Makes an unrelated new point |"
        )
        st.info(
            "**refutes** = 'you're wrong.'  \n"
            "**undercuts** = 'your evidence doesn't prove it — though you might still be right.'  \n\n"
            "Example: Sam says the 40% NO₂ figure comes from 'just one street in Madrid.' "
            "That's an **undercut** — Sam isn't saying air quality doesn't improve, "
            "just that this data point doesn't prove it does everywhere."
        )


# ── Dialog 4: Fact-checking ───────────────────────────────────────────────────

@st.dialog("How fact-checking works")
def factcheck_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "Solo se verifican las afirmaciones **comprobables** — aquellas que pueden contrastarse "
            "con evidencia externa. Las afirmaciones morales, las opiniones puras y las predicciones se omiten."
        )
        st.markdown("**Tres pasos**")
        st.markdown(
            "1. **Recuperar evidencia** — busca en Wikipedia y Semantic Scholar fuentes relevantes  \n"
            "2. **Valorar** — un modelo de IA lee la afirmación y la evidencia y las sopesa  \n"
            "3. **Veredicto** — una de siete etiquetas"
        )
        st.markdown("**Veredictos**")
        st.markdown(
            "| Veredicto | Significado |\n"
            "|-----------|-------------|\n"
            "| Respaldado | La evidencia apoya la afirmación |\n"
            "| Parcialmente respaldado | Verdadero pero incompleto o sin contexto |\n"
            "| Disputado | La evidencia apunta en ambas direcciones |\n"
            "| Engañoso | Técnicamente correcto pero desorientador |\n"
            "| No respaldado | La evidencia contradice la afirmación |\n"
            "| Fuera de alcance | No verificable (moral, subjetivo) |\n"
            "| No verificable | Evidencia insuficiente encontrada |"
        )
        st.caption(
            "«Respaldado» significa que la evidencia disponible apoya la afirmación — "
            "no que esté probada de forma definitiva."
        )
    else:
        st.markdown(
            "Only **checkable** claims are fact-checked — those that can be tested against external evidence. "
            "Moral claims, pure opinions, and predictions are skipped."
        )
        st.markdown("**Three steps**")
        st.markdown(
            "1. **Retrieve evidence** — searches Wikipedia and Semantic Scholar for relevant sources  \n"
            "2. **Assess** — an AI model reads the claim and the evidence and weighs them  \n"
            "3. **Verdict** — one of seven labels"
        )
        st.markdown("**Verdicts**")
        st.markdown(
            "| Verdict | Meaning |\n"
            "|---------|--------|\n"
            "| Supported | Evidence backs the claim |\n"
            "| Partially supported | True but incomplete or missing context |\n"
            "| Contested | Evidence cuts both ways |\n"
            "| Misleading | Technically accurate but likely to mislead |\n"
            "| Unsupported | Evidence contradicts the claim |\n"
            "| Beyond scope | Not verifiable against evidence (moral, subjective) |\n"
            "| Unverifiable | Insufficient evidence found |"
        )
        st.caption(
            "'Supported' means the available evidence backs the claim — "
            "not that it has been definitively proven."
        )


# ── Dialog 5: Rhetoric ────────────────────────────────────────────────────────

@st.dialog("Fallacies and rhetorical devices")
def rhetoric_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown(
            "**Las falacias** son errores de razonamiento. Solo se marcan cuando hay una cita concreta que señalar.  \n"
            "**Los recursos retóricos** son técnicas de persuasión. No son errores — pueden ser completamente legítimos."
        )
        st.markdown("**Falacias principales**")
        st.markdown(
            "| Falacia | Qué hace |\n"
            "|---------|----------|\n"
            "| Hombre de paja | Ataca una versión distorsionada del argumento |\n"
            "| Ad hominem | Ataca a la persona, no al argumento |\n"
            "| Selección de evidencia | Usa solo los datos favorables |\n"
            "| Falsa disyuntiva | Presenta solo dos opciones cuando hay más |\n"
            "| Pendiente resbaladiza | Un paso lleva inevitablemente al extremo |\n"
            "| Generalización apresurada | Conclusión amplia a partir de muy pocos casos |\n"
            "| Whataboutism | Desvía señalando los fallos del otro |"
        )
        st.markdown("**Recursos retóricos**")
        st.markdown(
            "| Recurso | Qué hace |\n"
            "|---------|----------|\n"
            "| Apelación a la autoridad | Cita a un experto o institución legítima |\n"
            "| Ejemplo vívido | Hace concreta una idea abstracta |\n"
            "| Prueba social | Apela al consenso amplio |\n"
            "| Lenguaje cargado | Palabras con carga emocional |"
        )
        st.caption(
            "La misma técnica (p. ej., citar autoridad) puede ser un recurso legítimo o una falacia "
            "según el contexto. La herramienta intenta distinguirlos."
        )
    else:
        st.markdown(
            "**Fallacies** are reasoning errors. They're only flagged when a specific quote can be cited.  \n"
            "**Rhetorical devices** are persuasion techniques. They're not errors — they can be entirely legitimate."
        )
        st.markdown("**Key fallacies**")
        st.markdown(
            "| Fallacy | What it does |\n"
            "|---------|-------------|\n"
            "| Straw man | Attacks a distorted version of the argument |\n"
            "| Ad hominem | Attacks the person, not the argument |\n"
            "| Cherry-picking | Uses only the supporting evidence |\n"
            "| False dichotomy | Presents only two options when more exist |\n"
            "| Slippery slope | Claims one step inevitably leads to the extreme |\n"
            "| Hasty generalisation | Broad conclusion from too few cases |\n"
            "| Whataboutism | Deflects by pointing to the other side's faults |"
        )
        st.markdown("**Rhetorical devices**")
        st.markdown(
            "| Device | What it does |\n"
            "|--------|-------------|\n"
            "| Appeal to authority | Cites a relevant expert or institution |\n"
            "| Vivid example | Makes an abstract point concrete |\n"
            "| Social proof | Appeals to wide consensus |\n"
            "| Loaded language | Emotionally charged word choice |"
        )
        st.caption(
            "The same technique (e.g., citing authority) can be a legitimate device or a fallacy "
            "depending on context. The app tries to distinguish them."
        )


# ── Dialog 6: Scoring ─────────────────────────────────────────────────────────

@st.dialog("How speakers are scored")
def scoring_dialog(lang: str = "English") -> None:
    if lang == "Español":
        st.markdown("Dos puntuaciones independientes, que miden cosas distintas.")
        st.markdown(
            "**Fiabilidad**  \n"
            "De todas las afirmaciones comprobables del hablante, ¿qué fracción resultó "
            "respaldada o parcialmente respaldada?  \n"
            "→ Mide la precisión factual. *No* mide si el argumento fue persuasivo o lógicamente sólido."
        )
        st.markdown(
            "**Tasa de respuesta directa**  \n"
            "De todas las veces que el hablante pudo responder a una afirmación concreta del otro lado, "
            "¿con qué frecuencia respondió de verdad (refutó, apoyó, reencuadró…) en lugar de evadir?  \n"
            "→ Mide el compromiso argumentativo. Una tasa alta = debatiente implicado. Baja = evita el tema."
        )
        st.markdown("**Cómo leer las dos juntas**")
        st.markdown(
            "| Fiabilidad | Tasa de respuesta | Perfil |\n"
            "|------------|-------------------|--------|\n"
            "| Alta | Alta | Más sólido: preciso y comprometido |\n"
            "| Alta | Baja | Preciso pero evasivo |\n"
            "| Baja | Alta | Comprometido pero a menudo incorrecto |\n"
            "| Baja | Baja | Evasivo e impreciso |"
        )
        st.caption(
            "Un hablante que hace solo afirmaciones morales o subjetivas mostrará N/D en fiabilidad — "
            "no una puntuación baja. Esas afirmaciones están fuera del alcance de la verificación."
        )
    else:
        st.markdown("Two independent scores, measuring different things.")
        st.markdown(
            "**Reliability**  \n"
            "Of all this speaker's checkable claims, what fraction were rated Supported or "
            "Partially Supported?  \n"
            "→ Measures factual accuracy. Does *not* measure whether the argument was persuasive or logically sound."
        )
        st.markdown(
            "**Direct response rate**  \n"
            "Of all the times this speaker could have responded to a specific claim from the other side, "
            "how often did they genuinely engage (refute, support, reframe…) rather than evade or ignore?  \n"
            "→ Measures argumentative engagement. High rate = engaged debater. Low rate = deflects."
        )
        st.markdown("**Reading both scores together**")
        st.markdown(
            "| Reliability | Response rate | Profile |\n"
            "|-------------|---------------|---------|\n"
            "| High | High | Strongest: accurate and engaged |\n"
            "| High | Low | Accurate but evasive |\n"
            "| Low | High | Engaged but often wrong |\n"
            "| Low | Low | Evasive and inaccurate |"
        )
        st.caption(
            "A speaker who makes only moral or subjective claims will show N/A for reliability — "
            "not a low score. Those claims are outside the scope of fact-checking."
        )
