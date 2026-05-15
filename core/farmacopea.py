"""Farmacopea - Base de conocimiento de medicamentos con indicaciones, mecanismo, efectos adversos y contraindicaciones."""
from __future__ import annotations

from typing import Optional

FARMACOPEA: dict[str, dict] = {
    "acetaminofen": {
        "nombre": "Acetaminofén (Paracetamol)",
        "clase": "Analgésico no opioide / Antipirético",
        "descripcion": "Analgesico y antipiretico de accion central, sin actividad antiinflamatoria significativa.",
        "indicaciones": "Fiebre, dolor leve a moderado (cefalea, odontalgia, mialgia, dolor postoperatorio). Primera linea en pediatria.",
        "mecanismo": "Inhibicion de la COX-3 a nivel central y modulacion del sistema serotoninergico descendente. Activa receptores cannabinoides CB1.",
        "beneficios": "Seguro a dosis terapeuticas. No causa irritacion gastrica. No afecta agregacion plaquetaria. Puede usarse en embarazo y lactancia.",
        "efectos_adversos": "Hepatotoxicidad dosis-dependiente (sobredosis). Raro: reacciones cutaneas graves (Sd. Stevens-Johnson). Hipotension si EV rapido.",
        "contraindicaciones": "Insuficiencia hepatica severa, alergia conocida. Precaucion en alcoholismo cronico, desnutricion. No superar 4 g/dia en adultos.",
    },
    "ibuprofeno": {
        "nombre": "Ibuprofeno",
        "clase": "AINE (Antiinflamatorio No Esteroideo)",
        "descripcion": "Antiinflamatorio no esteroideo con propiedades analgesicas, antiinflamatorias y antipireticas. Inhibidor no selectivo de COX.",
        "indicaciones": "Fiebre, dolor leve a moderado (cefalea, odontalgia, dismenorrea, dolor musculoesqueletico), inflamacion, artritis juvenil, cierre de ductus arterioso.",
        "mecanismo": "Inhibicion reversible y no selectiva de COX-1 y COX-2, disminuyendo la sintesis de prostaglandinas, prostaciclinas y tromboxanos.",
        "beneficios": "Eficaz para fiebre y dolor con efecto antiinflamatorio superior al paracetamol. Varias presentaciones pediatricas. Accion rapida.",
        "efectos_adversos": "Nauseas, dispepsia, dolor abdominal, diarrea. Riesgo de ulcera gastrica con uso prolongado. Nefrotoxicidad. Aumento riesgo cardiovascular.",
        "contraindicaciones": "Insuficiencia renal severa, ulcera peptica activa, alergia a AINEs, asma sensible a aspirina, <3 meses, IC severa, tercer trimestre embarazo.",
    },
    "amoxicilina": {
        "nombre": "Amoxicilina",
        "clase": "Antibiótico Betalactámico (Penicilina)",
        "descripcion": "Antibiotico bactericida del grupo de las aminopenicilinas. Activo contra bacterias Gram-positivas y algunas Gram-negativas.",
        "indicaciones": "Otitis media aguda, faringoamigdalitis estreptococica, sinusitis, neumonia adquirida en la comunidad, ITU, profilaxis endocarditis bacteriana.",
        "mecanismo": "Inhibicion de la sintesis de la pared celular bacteriana (transpeptidacion). Se une a PBPs, activa autolisinas y lisis bacteriana.",
        "beneficios": "Bien tolerada, amplio espectro clinico, alta biodisponibilidad oral, bajo costo. Segura en embarazo y lactancia.",
        "efectos_adversos": "Diarrea (mas frecuente con altas dosis), nausea, rash maculopapular (especialmente en mononucleosis), colitis por C. difficile.",
        "contraindicaciones": "Alergia a penicilinas o cefalosporinas (alergia cruzada 10%). Precaucion en insuficiencia renal (ajustar dosis).",
    },
    "amoxicilina_clavulanico": {
        "nombre": "Amoxicilina + Ác. Clavulánico",
        "clase": "Antibiótico Betalactámico + Inhibidor de Betalactamasa",
        "descripcion": "Combinacion de amoxicilina con acido clavulanico (inhibidor de betalactamasas) que amplia el espectro contra bacterias productoras de betalactamasas.",
        "indicaciones": "Sinusitis, otitis media recurrente, neumonia, infecciones respiratorias bajas, infecciones odontogenicas, mordeduras, infecciones intraabdominales leves.",
        "mecanismo": "Amoxicilina inhibe sintesis pared celular. Acido clavulanico inhibe betalactamasas bacterianas, protegiendo a la amoxicilina de la degradacion enzimatica.",
        "beneficios": "Espectro ampliado contra bacterias resistentes. Eficaz en infecciones polimicrobianas. Alternativa oral a cefalosporinas.",
        "efectos_adversos": "Diarrea (mas frecuente que amoxicilina sola), nausea, rash. Menos frecuente: hepatitis colestasica (asociada a edad >65 anios y tratamientos prolongados).",
        "contraindicaciones": "Alergia a betalactamicos. Insuficiencia hepatica asociada a uso previo. Evitar si mononucleosis infecciosa (rash).",
    },
    "azitromicina": {
        "nombre": "Azitromicina",
        "clase": "Antibiótico Macrólido (Azálido)",
        "descripcion": "Antibiotico bacteriostatico del grupo de los macrolidos. Larga vida media que permite dosis unica diaria y cursos cortos.",
        "indicaciones": "Neumonia atipica, bronquitis, faringoamigdalitis, sinusitis, otitis media, infecciones de piel, infecciones de transmision sexual (clamidia, gonorrea), tracoma.",
        "mecanismo": "Se une a subunidad 50S ribosomal bacteriana, inhibiendo la sintesis proteica por bloqueo del translocacion peptidica. Efecto post-antibotico prolongado.",
        "beneficios": "Dosis unica diaria. Cursos cortos (3-5 dias). Buena tolerancia gastrointestinal. Cubre atipicos (Mycoplasma, Chlamydia, Legionella).",
        "efectos_adversos": "Nauseas, dolor abdominal, diarrea, flatulencia. Prolongacion intervalo QT (raro). Hepatitis. Alteraciones del gusto. Reacciones cutaneas.",
        "contraindicaciones": "Alergia a macrolidos, historia de ictericia colestasica con uso previo. Precaucion: prolongacion QT, miastenia gravis, insuficiencia hepatica.",
    },
    "salbutamol": {
        "nombre": "Salbutamol (Albuterol)",
        "clase": "Broncodilatador β2-agonista de acción corta (SABA)",
        "descripcion": "Agonista beta-2 adrenergico de accion corta. Broncodilatador de primera linea en crisis asmatica. Relaja musculo liso bronquial.",
        "indicaciones": "Crisis asmatica aguda, broncoespasmo inducido por ejercicio, EPOC exacerbado, hipercaliemia (como tratamiento de emergencia).",
        "mecanismo": "Estimulacion selectiva de receptores β2-adrenergicos en musculo liso bronquial, activando adenilato ciclasa, aumentando AMPc y produciendo relajacion muscular.",
        "beneficios": "Inicio de accion rapido (5-15 min inhalado). Alta seguridad. Efectivo en crisis pediatricas. Varias vias de administracion (inhalatoria, nebulizada, EV).",
        "efectos_adversos": "Taquicardia, temblor fino, nerviosismo, cefalea, hipocaliemia (dosis altas), hiperglucemia (dosis altas). Tolerancia con uso cronico excesivo.",
        "contraindicaciones": "Precaucion en cardiopatias (arritmias, miocardiopatia hipertrofica), hipertiroidismo no controlado, diabetes descompensada.",
    },
    "dexametasona": {
        "nombre": "Dexametasona",
        "clase": "Corticoide (Glucocorticoide de acción prolongada)",
        "descripcion": "Glucocorticoide sintetico de accion prolongada con potente efecto antiinflamatorio e inmunosupresor. Practicamente sin actividad mineralocorticoide.",
        "indicaciones": "Crup viral, asma severa, meningitis bacteriana (coadyuvante), sindrome de dificultad respiratoria neonatal (maduracion pulmonar prenatal), edema cerebral, COVID-19 severo, alergias severas, quimioterapia antiemetica.",
        "mecanismo": "Union a receptor glucocorticoides citoplasmatico, modulacion de transcripcion genica (transrepresion de factores proinflamatorios NF-κB, AP-1). Efecto genomicos en horas, no genomicos inmediatos.",
        "beneficios": "Potente efecto antiinflamatorio. Larga duracion (36-54hs). Sin retencion de sodio. Util en edema cerebral (menor edema que otros corticoides). Bajo costo.",
        "efectos_adversos": "Agudos: hiperglucemia, insomnio, agitacion. Cronicos: supresion suprarrenal, Sd. Cushing, osteoporosis, retraso crecimiento infantil, catarata, glaucoma, miopatia.",
        "contraindicaciones": "Infecciones fungicas sistemicas no tratadas, administracion de vacunas a virus vivos. Precaucion: diabetes, HTA, tuberculosis, ulcera peptica activa.",
    },
    "dipirona": {
        "nombre": "Dipirona (Metamizol)",
        "clase": "Analgésico no opioide / Antipirético / Espasmolítico",
        "descripcion": "Analgesico, antipiretico y espasmolitico potente del grupo de las pirazolonas. No tiene efecto antiinflamatorio significativo.",
        "indicaciones": "Dolor agudo moderado a severo (postoperatorio, colico renal, dolor oncologico), fiebre refractaria a otros antipireticos. Ampliamente usado en Latinoamerica y Europa.",
        "mecanismo": "Inhibicion de COX-3 central y periferica, activacion del sistema opioide endogeno (receptores κ y CB1 cannabinoides), modulacion del sistema serotoninergico.",
        "beneficios": "Potente efecto analgesico y antipiretico. Efecto espasmolitico. No causa depresion respiratoria ni adiccion. Alternativa cuando AINEs/opioides no son opcion.",
        "efectos_adversos": "Agranulocitosis (raro 1:1.000.000, pero grave), hipotension (especialmente si EV rapido), reacciones alergicas cutaneas, nefritis intersticial.",
        "contraindicaciones": "Antecedentes de agranulocitosis con pirazolonas, porfiria aguda, deficit de G6PD, tercer trimestre embarazo, lactancia, <3 meses o <5 kg.",
    },
    "ceftriaxona": {
        "nombre": "Ceftriaxona",
        "clase": "Antibiótico Cefalosporina 3ra Generación",
        "descripcion": "Cefalosporina de tercera generacion de amplio espectro con actividad contra Gram-negativos, incluyendo resistencia a betalactamasas. Larga vida media (dosis unica diaria).",
        "indicaciones": "Neumonia, meningitis bacteriana, sepsis, infecciones intraabdominales, ITU complicada, pielonefritis, gonorrea no complicada, enfermedad inflamatoria pelvica, infecciones osteoarticulares.",
        "mecanismo": "Inhibicion de sintesis de pared celular bacteriana por union a PBPs (PBP3 principalmente). Resistente a betalactamasas de amplio espectro (ESBL en algunos casos).",
        "beneficios": "Dosis unica diaria. Amplio espectro. Buena penetracion a SNC. Eficaz en meningitis. Alternativa en alergia a penicilina (precaucion).",
        "efectos_adversos": "Diarrea, rash, eosinofilia. Seudolitiasis biliar (precipitacion sales calcicas), flebitis, colitis por C. difficile. Discrasias sanguineas (raro).",
        "contraindicaciones": "Alergia a cefalosporinas. Precaucion en alergia a penicilina (10% alergia cruzada). Evitar en neonatos con hiperbilirrubinemia (desplaza bilirrubina). No mezclar con calcio.",
    },
    "ondansetron": {
        "nombre": "Ondansetrón",
        "clase": "Antiemético / Antagonista 5-HT3",
        "descripcion": "Antiemetico potente del grupo de los antagonistas de receptores 5-HT3 (serotonina). Primera linea en prevencion de nausea y vomito por quimioterapia y postoperatorio.",
        "indicaciones": "Nausea y vomito por quimioterapia (altamente y moderadamente emetogena), radioterapia, postoperatorio, gastroenteritis aguda en ninos, hiperemesis gravidica.",
        "mecanismo": "Antagonismo selectivo de receptores 5-HT3 a nivel central (zona gatillo quimiorreceptora del area postrema) y periferico (tracto gastrointestinal, neuronas vagales aferentes).",
        "beneficios": "Alta eficacia antiemetica. Bien tolerado. No causa efectos extrapiramidales (a diferencia de metoclopramida). Formulacion oral, ODV y EV. Seguro en pediatria.",
        "efectos_adversos": "Cefalea, estreñimiento, mareos, sensacion de calor/rubor. Prolongacion de intervalo QT (dosis-dependiente). Elevacion transitoria de enzimas hepaticas.",
        "contraindicaciones": "Alergia conocida. Precaucion: prolongacion QT congenito, hipocaliemia, hipomagnesemia, uso concomitante de otros farmacos que prolongan QT. Evitar en fenilcetonuria (formulaciones con aspartamo).",
    },
    "diazepam": {
        "nombre": "Diazepam",
        "clase": "Benzodiazepina / Ansiolítico / Anticonvulsivante / Relajante Muscular",
        "descripcion": "Benzodiazepina de accion prolongada con propiedades ansioliticas, sedantes, anticonvulsivantes, hipnoticas y relajantes musculares.",
        "indicaciones": "Estatus epileptico (primera linea rectal/EV), ansiedad generalizada, trastorno de panico, sindrome de abstinencia alcoholica, espasmos musculares, sedacion pre-procedimiento.",
        "mecanismo": "Modulacion alosterica positiva de receptores GABA-A, potenciando la accion inhibitoria del GABA (acido gamma-aminobutirico) al aumentar la frecuencia de apertura del canal de Cl-.",
        "beneficios": "Amplio espectro clinico. Accion rapida (EV 1-3 min, oral 30-60 min). Larga duracion (vida media 20-50hs). Formulacion rectal util en emergencia pediatrica.",
        "efectos_adversos": "Sedacion, somnolencia, mareos, ataxia, hipotonia muscular, amnesia anterograda. Depresion respiratoria (especialmente EV o con alcohol). Tolerancia y dependencia. Sindrome de abstinencia.",
        "contraindicaciones": "Miastenia gravis, glaucoma de angulo estrecho no tratado, insuficiencia respiratoria severa, apnea del sueno no tratada, alergia a benzodiazepinas, <6 meses (precaucion).",
    },
    "omeprazol": {
        "nombre": "Omeprazol",
        "clase": "Inhibidor de Bomba de Protones (IBP)",
        "descripcion": "Inhibidor potente y de accion prolongada de la bomba de protones gastrica (H+/K+-ATPasa). Supresor efectivo de la secrecion acida gastrica.",
        "indicaciones": "ERGE (enfermedad por reflujo gastroesofagico), esofagitis erosiva, ulcera peptica gastrica y duodenal, sindrome de Zollinger-Ellison, erradicacion de H. pylori (combinacion), profilaxis de ulcera por estres, prevencion de ulcera por AINEs.",
        "mecanismo": "Inhibicion irreversible de la H+/K+-ATPasa (bomba de protones) en las celulas parietales gastricas, bloqueando la secrecion acida final comun. Acumulacion en medio acido del canaliculo secretor.",
        "beneficios": "Potente supresion acida (hasta 99%). Una dosis diaria. Cura esofagitis erosiva. Terapia corta (2-4 semanas para ulcera). Bien tolerado.",
        "efectos_adversos": "Cefalea, dolor abdominal, nausea, flatulencia, diarrea o estreñimiento. Uso prolongado: riesgo de deficit de B12, osteoporosis/fracturas, nefritis intersticial, infecciones intestinales (C. difficile), hipomagnesemia.",
        "contraindicaciones": "Alergia a IBPs. Uso concomitante con atazanavir, nelfinavir, rilpivirina, metotrexato (altas dosis). Precaucion en osteoporosis, hipomagnesemia, insuficiencia hepatica.",
    },
    "furosemida": {
        "nombre": "Furosemida",
        "clase": "Diurético de Asa",
        "descripcion": "Diuretico potente de accion rapida que actua en el asa de Henle. Bloquea el cotransportador Na+/K+/2Cl- en la rama ascendente gruesa.",
        "indicaciones": "Edema por ICC, cirrosis, sindrome nefrotico, insuficiencia renal, HTA (especialmente con retencion de liquidos), edema agudo de pulmon (EV).",
        "mecanismo": "Bloqueo del cotransportador Na+/K+/2Cl- en la membrana luminal de la rama ascendente gruesa del asa de Henle, inhibiendo la reabsorcion de sodio, cloro y potasio.",
        "beneficios": "Potente efecto diuretico y natriuretico. Accion rapida (30-60 min oral, 5 min EV). Util en emergencias (edema agudo de pulmon). Varias vias de administracion.",
        "efectos_adversos": "Hipocaliemia, hiponatremia, hipocloremia, alcalosis metabolica, deshidratacion, hiperuricemia, hiperglucemia, ototoxicidad (dosis altas EV rapido), hipotension.",
        "contraindicaciones": "Anuria, insuficiencia renal severa (oliguria no respondiente), hipovolemia/deshidratacion, hipocaliemia severa, hiponatremia severa, alergia a sulfonamidas (alergia cruzada).",
    },
    "enalapril": {
        "nombre": "Enalapril",
        "clase": "IECA (Inhibidor de Enzima Convertidora de Angiotensina)",
        "descripcion": "Inhibidor de la enzima convertidora de angiotensina (IECA). Profarmaco que se convierte en enalaprilato activo. Antihipertensivo, vasodilatador.",
        "indicaciones": "Hipertension arterial (primera linea), insuficiencia cardiaca cronica, disfuncion ventricular izquierda asintomatica, nefropatia diabetica, prevencion de eventos cardiovasculares.",
        "mecanismo": "Inhibicion de la ECA, bloqueando la conversion de angiotensina I en angiotensina II (potente vasoconstrictor). Reduce secrecion de aldosterona. Aumenta bradicinina (efecto vasodilatador).",
        "beneficios": "Eficaz en HTA e ICC. Efecto nefroprotector en diabetes. Reduce mortalidad en ICC. Bien tolerado. Una o dos dosis diarias.",
        "efectos_adversos": "Tos seca (10-20%, por aumento de bradicinina), hipotension (primera dosis), hipercaliemia, insuficiencia renal aguda (en estenosis renal bilateral), angioedema (raro, 0.3%), rash, alteraciones del gusto.",
        "contraindicaciones": "Embarazo (teratogenico - categ D 2do/3er trimestre), lactancia, estenosis bilateral de arteria renal, historia de angioedema con IECAs, hipercaliemia severa.",
    },
    "metoclopramida": {
        "nombre": "Metoclopramida",
        "clase": "Antiemético / Procinético Gastrointestinal",
        "descripcion": "Antiemetico y procinetico gastrointestinal. Antagonista dopaminergico (D2) y serotoninergico (5-HT4). Facilita el vaciamiento gastrico.",
        "indicaciones": "Nausea y vomito (postoperatorio, por quimioterapia, radiacion), gastroparesia diabetica, ERGE, procedimientos gastrointestinales (SEDA), migrana (coadyuvante antiemetico).",
        "mecanismo": "Antagonismo de receptores D2 en zona gatillo quimiorreceptora (area postrema). Agonismo de receptores 5-HT4 en tracto GI aumentando motilidad, vaciamiento gastrico y tono del EEI.",
        "beneficios": "Eficaz antiemetico. Efecto procinetico (util en gastroparesia). Bajo costo. Formulacion oral, EV, IM. Alternativa cuando ondansetron no disponible.",
        "efectos_adversos": "Sintomas extrapiramidales (distonia aguda, acatisia, parkinsonismo, especialmente en ninos y jovenes), sedacion, fatiga, diarrea, hiperprolactinemia (galactorrea, ginecomastia). Sd. neuroleptico maligno (raro).",
        "contraindicaciones": "<1 anio (riesgo ED). Hemorragia GI, obstruccion mecanica o perforacion intestinal. Feocromocitoma. Historia de discinesia tardia por neurolepticos. Epilepsia (disminuye umbral convulsivo).",
    },
    "loratadina": {
        "nombre": "Loratadina",
        "clase": "Antihistamínico H1 2da Generación",
        "descripcion": "Antihistaminico H1 de segunda generacion con minima somnolencia. Accion prolongada (24hs). No atraviesa significativamente la BHE.",
        "indicaciones": "Rinitis alergica estacional y perenne (estornudos, rinorrea, prurito nasal), urticaria cronica espontanea, prurito alergico, conjuntivitis alergica.",
        "mecanismo": "Antagonismo selectivo y periferico de receptores H1 de histamina, estabilizando la cascada alergica. Baja penetracion en SNC (menos somnolencia). Metabolito activo: desloratadina.",
        "beneficios": "Una dosis diaria. Minima somnolencia. No produce tolerancia. Bien tolerada en ninos. Varias presentaciones (jarabe, comp, ODV). Sin interaccion con alcohol.",
        "efectos_adversos": "Cefalea, somnolencia (leve, 8%), fatiga, boca seca. Raro: taquicardia, palpitaciones, elevacion de enzimas hepaticas. Reacciones alergicas cutaneas.",
        "contraindicaciones": "Alergia conocida. Insuficiencia hepatica severa (ajustar dosis). Precaucion en insuficiencia renal severa. Evitar en lactancia (excrecion en leche materna).",
    },
    "adrenalina": {
        "nombre": "Adrenalina (Epinefrina)",
        "clase": "Catecolamina / Agonista α y β adrenérgico",
        "descripcion": "Catecolamina endogena con potente accion agonista sobre receptores α y β adrenergicos. Farmaco esencial en reanimacion cardiopulmonar y anafilaxia.",
        "indicaciones": "Anafilaxia (primera linea IM), paro cardiaco (RCP), shock anafilactico, laringoespasmo/asfixia (crup severo), asma severa refractaria, hemorragia superficial (topico vasoconstrictor).",
        "mecanismo": "Agonista no selectivo: α1 (vasoconstriccion periferica), α2, β1 (aumento FC e inotropismo), β2 (broncodilatacion, vasodilatacion muscular). Dosis bajas: efecto β. Dosis altas: efecto α predominante.",
        "beneficios": "Farmaco salvador en anafilaxia y paro cardiaco. Accion ultra-rapida. Amplio margen de seguridad en emergencia. Disponible en auto-inyectores. Bajo costo.",
        "efectos_adversos": "Taquicardia, HTA severa, arritmias ventriculares, ansiedad, temblor, cefalea, hiperglucemia, necrosis tisular por extravasacion. Isquemia miocardica en dosis altas.",
        "contraindicaciones": "Relativas en situaciones no emergentes: HTA no controlada, arritmias, hipertiroidismo, feocromocitoma, glaucoma de angulo cerrado. En anafilaxia NO HAY contraindicaciones absolutas.",
    },
    "prednisolona": {
        "nombre": "Prednisolona",
        "clase": "Corticoide (Glucocorticoide de acción intermedia)",
        "descripcion": "Glucocorticoide de accion intermedia con potente efecto antiinflamatorio e inmunosupresor. Metabolito activo de la prednisona. No requiere conversion hepatica.",
        "indicaciones": "Asma aguda y cronica, enfermedades reumaticas autoinmunes (artritis idiopatica juvenil, lupus), sindrome nefrotico, enfermedades inflamatorias intestinales (Crohn, CUCI), alergias severas, dermatitis atopica severa.",
        "mecanismo": "Union a receptor glucocorticoides con modulacion genica: transrepresion de citoquinas proinflamatorias (IL-1, IL-6, TNF-α) y mediadores lipidicos (prostaglandinas, leucotrienos). Efecto genomico en horas.",
        "beneficios": "Potente antiinflamatorio oral. Alternativa a dexametasona cuando se requiere accion intermedia. Menor supresion suprarrenal que dexametasona. Formulacion liquida pediatrica disponible.",
        "efectos_adversos": "Agudos: hiperglucemia, aumento de apetito, insomnio, retencion de liquidos. Cronicos: supresion suprarrenal, Sd. Cushing, osteoporosis, retraso crecimiento, catarata, glaucoma, facil contusion.",
        "contraindicaciones": "Infecciones fungicas sistemicas no tratadas, vacunas a virus vivos. Precaucion: diabetes, HTA, osteoporosis, ulcera peptica, infecciones activas, tuberculosis.",
    },
    "cefalexina": {
        "nombre": "Cefalexina",
        "clase": "Antibiótico Cefalosporina 1ra Generación",
        "descripcion": "Cefalosporina de primera generacion. Activo contra Gram-positivos (estreptococos, estafilococos sensibles) y algunos Gram-negativos (E. coli, Klebsiella, Proteus).",
        "indicaciones": "Infecciones de piel y tejidos blandos (celulitis, impetigo, forunculosis), faringoamigdalitis estreptococica, ITU no complicada, otitis media, profilaxis en cirugia ortopedica.",
        "mecanismo": "Inhibicion de sintesis de pared celular bacteriana por union a PBPs, activacion de autolisinas bacterianas y lisis celular. Bactericida, accion tiempo-dependiente.",
        "beneficios": "Excelente biodisponibilidad oral. Activo contra S. aureus productor de penicilinasa. Alternativa oral en infecciones de piel. Bien tolerada en ninos.",
        "efectos_adversos": "Diarrea, nausea, dolor abdominal, rash. Colitis por C. difficile. Raro: nefritis intersticial, hepatitis, discrasias sanguineas. Prurito anal/ genital.",
        "contraindicaciones": "Alergia a cefalosporinas. Precaucion en alergia a penicilina (5-10% alergia cruzada). Ajustar dosis en insuficiencia renal (CrCl <50 ml/min).",
    },
    "clindamicina": {
        "nombre": "Clindamicina",
        "clase": "Antibiótico Lincosamida",
        "descripcion": "Antibiotico bacteriostatico del grupo de las lincosamidas. Activo contra anaerobios, Gram-positivos (incluyendo SAMR comunitario) y algunos protozoos.",
        "indicaciones": "Infecciones anaerobicas (intraabdominales, pelvicas, odontogenicas), infecciones de piel y tejidos blandos (incluyendo SAMR comunitario), osteomielitis, neumonia por aspiracion, acne severo (topico/sistemico), profilaxis endocarditis (alergia penicilina), malaria (combinacion).",
        "mecanismo": "Union a subunidad 50S ribosomal (sitio cercano a macrolidos), inhibiendo la sintesis proteica bacteriana por bloqueo del peptidil-transferasa. Bacteriostatico, bactericida a altas concentraciones.",
        "beneficios": "Excelente cobertura anaerobica. Penetracion osea. Alternativa en alergia a penicilina. Formulacion oral, EV, IM y topica. Activo contra SAMR comunitario.",
        "efectos_adversos": "Colitis pseudomembranosa por C. difficile (riesgo significativo), diarrea, nausea, rash. Prurito anal. Raro: bloqueo neuromuscular, hepatitis, neutropenia. Sabor metalico con IV.",
        "contraindicaciones": "Alergia conocida. Precaucion: colitis previa por C. difficile, enfermedad hepatica severa, enfermedad neuromuscular (miastenia gravis, puede potenciar bloqueo neuromuscular).",
    },
    "levetiracetam": {
        "nombre": "Levetiracetam",
        "clase": "Anticonvulsivante / Antiepiléptico",
        "descripcion": "Anticonvulsivante de amplio espectro con mecanismo de accion unico (union a SV2A). Primera linea en epilepsia focal y generalizada. Perfil farmacocinetico favorable.",
        "indicaciones": "Crisis focales con o sin generalizacion secundaria, crisis tonicoclonica generalizada, epilepsia mioclonica juvenil, crisis de ausencia, estatus epileptico (EV). Monoterapia y politerapia.",
        "mecanismo": "Union a la proteina vesicular SV2A (synaptic vesicle protein 2A) modulando la liberacion de neurotransmisores. Tambien inhibe canales de Ca++ tipo N. Diferente a otros anticonvulsivantes.",
        "beneficios": "Amplio espectro. Sin interacciones farmacocineticas significativas (no se metaboliza por citocromo P450). No requiere monitorizacion de niveles sericos. Titulacion rapida.",
        "efectos_adversos": "Somnolencia, mareos, fatiga, ataxia, irritabilidad/agresividad (especialmente en ninos), headache, anorexia. Raro: reacciones cutaneas graves (DRESS, SJS), psicosis, leucopenia.",
        "contraindicaciones": "Alergia conocida. Precaucion en insuficiencia renal (ajustar por CrCl). Evitar suspension brusca (riesgo de crisis de rebote). Embarazo: riesgo de malformaciones (categoria C).",
    },
    "morfina": {
        "nombre": "Morfina",
        "clase": "Opioide Agonista μ (MOR)",
        "descripcion": "Opioide agonista μ clasico. Farmaco de referencia para dolor moderado a severo. Alivia el dolor sin perdida de conciencia. Produce euforia y sedacion.",
        "indicaciones": "Dolor moderado a severo (postoperatorio, oncologico, trauma, infarto agudo de miocardio), disnea severa en cuidados paliativos, sedacion en procedimientos dolorosos, edema agudo de pulmon.",
        "mecanismo": "Agonista de receptores opioides μ (MOR) centrales y perifericos. Activacion de canales de K+ rectificadores, inhibicion de canales de Ca++, disminuyendo liberacion de neurotransmisores y transmision del dolor.",
        "beneficios": "Estandar de oro para dolor severo. Amplia experiencia clinica. Multiples vias (oral, EV, SC, epidural). Efecto predecible. Antidoto disponible (naloxona). Bajo costo.",
        "efectos_adversos": "Depresion respiratoria (dosis-dependiente, principal riesgo), estreñimiento (cronico), nausea/vomitos, sedacion, prurito, retencion urinaria, miosis, hipotension ortostatica. Tolerancia y dependencia. Sindrome de abstinencia.",
        "contraindicaciones": "Depresion respiratoria severa, asma aguda severa, obstruccion intestinal, traumatismo craneoencefalico con HIC, feocromocitoma. Precaucion en insuficiencia renal, hepatica, apnea del sueno.",
    },
    "sulfato_ferroso": {
        "nombre": "Sulfato Ferroso",
        "clase": "Hematinico / Antianemico (Suplemento de Hierro)",
        "descripcion": "Suplemento de hierro divalente (Fe2+) para prevencion y tratamiento de la anemia ferropenica. Forma mas biodisponible y economica de hierro oral.",
        "indicaciones": "Anemia ferropenica (tratamiento y prevencion), deficiencia de hierro en lactantes, adolescentes, embarazo, post-hemorragia, ERC, enfermedad inflamatoria intestinal, post-bypass gastrico.",
        "mecanismo": "Aporte de hierro elemental para sintesis de hemoglobina, mioglobina, citocromos y otras enzimas hem y no-hem. Absorbido en duodeno y yeyuno proximal via DMT1. Se incorpora a ferritina y transferrina.",
        "beneficios": "Alta biodisponibilidad. Bajo costo. Amplia experiencia. Multiples formulaciones (gotas, jarabe, comprimidos). Eficacia comprobada en anemia ferropenica.",
        "efectos_adversos": "Estreñimiento, heces oscuras (inocuo), nausea, dolor epigastrico, diarrea. Sobredosis: intoxicacion grave (necrosis hepatico, CID, muerte). Tincion dental (liquidos, usar sorbete).",
        "contraindicaciones": "Hemocromatosis, hemosiderosis, anemia hemolitica, talasemia mayor (sin sobrecarga de hierro), ulcera peptica activa, transfusiones repetidas. Precaucion en enfermedad inflamatoria intestinal.",
    },
    "vancomicina": {
        "nombre": "Vancomicina",
        "clase": "Antibiótico Glicopéptido",
        "descripcion": "Antibiotico triciclico glicopeptido. Bactericida contra Gram-positivos aerobios y anaerobios. Farmaco de eleccion para infecciones por SAMR.",
        "indicaciones": "Infecciones por SAMR (bacteriemia, neumonia, osteomielitis, endocarditis, infecciones de piel complejas), colitis pseudomembranosa por C. difficile (oral), profilaxis quirurgica (alergia a betalactamicos), meningitis por Gram-positivos resistentes.",
        "mecanismo": "Inhibicion de la sintesis de pared celular por union al terminal D-Ala-D-Ala del precursor peptidoglicano, bloqueando la transglucosilacion y transpeptidacion. Bactericida lento, tiempo-dependiente.",
        "beneficios": "Farmaco de eleccion para SAMR. Alternativa en alergia a betalactamicos. Activo contra C. difficile (via oral no absorbible). Larga experiencia clinica.",
        "efectos_adversos": "Nefrotoxicidad (especialmente con aminoglucosidos), Sd. de Red Man (liberacion de histamina por infusion rapida), ototoxicidad (raro), neutropenia, tromboflebitis, nausea (oral). Requiere monitoreo de niveles.",
        "contraindicaciones": "Alergia conocida. Precaucion: insuficiencia renal (ajustar dosis y monitorizar niveles), uso concomitante de otros nefrotoxicos/ototoxicos, embarazo (categoria C). No IM.",
    },
    "metronidazol": {
        "nombre": "Metronidazol",
        "clase": "Antibiótico Nitroimidazol / Antiparasitario",
        "descripcion": "Antibiotico y antiparasitario del grupo de los nitroimidazoles. Activo contra bacterias anaerobias y protozoos. Cruza BHE y barrera placentaria.",
        "indicaciones": "Infecciones anaerobicas (intraabdominales, pelvicas, odontogenicas, abscesos), colitis por C. difficile, vaginosis bacteriana, tricomoniasis, giardiasis, amebiasis, erradicacion de H. pylori (combinacion), rosacea (topico).",
        "mecanismo": "Reduccion del grupo nitro intracelular por ferredoxina bacteriana, formando metabolitos radicales toxicos que dañan el ADN bacteriano. Selectivo para celulas anaerobias. Bactericida.",
        "beneficios": "Excelente cobertura anaerobica. Activo contra protozoos. Alta biodisponibilidad oral. Buena penetracion tisular (incluyendo SNC y abscesos). Bajo costo.",
        "efectos_adversos": "Sabor metalico, nausea, glositis, estomatitis. Neuropatia periferica (uso prolongado/dosis altas). Reaccion tipo disulfiram con alcohol (nausea, vomito, flushing, taquicardia). Oscurecimiento de orina.",
        "contraindicaciones": "Alergia a nitroimidazoles. Primer trimestre embarazo (evitar). Lactancia. Precaucion: enfermedad hepatica severa (ajustar dosis), neuropatia activa o historia de discrasias sanguineas.",
    },
    "midazolam": {
        "nombre": "Midazolam",
        "clase": "Benzodiazepina de acción ultracorta / Sedante / Ansiolítico",
        "descripcion": "Benzodiazepina de accion ultracorta (vida media 1.5-3.5hs). Potente sedante, ansiolitico, amnesico y anticonvulsivante. Hidrosoluble, se ioniza a pH fisiologico.",
        "indicaciones": "Sedacion consciente para procedimientos (endoscopia, broncoscopia, cirugia menor), induccion anestesica, estatus epileptico refractario (segunda linea), premedicacion anestesica, sedacion en UCI.",
        "mecanismo": "Modulacion alosterica positiva de receptores GABA-A (subunidades α1, γ2), potenciando la accion del GABA. Apertura de canales de Cl- y hiperpolarizacion neuronal. Accion rapida y corta.",
        "beneficios": "Inicio de accion ultra-rapido (1-3 min EV, 10-15 min IM/intranasal). Vida media corta (ideal para procedimientos). Potente amnesia anterograda. Reversible con flumazenilo. Multiples vias.",
        "efectos_adversos": "Depresion respiratoria (dosis-dependiente, riesgo elevado con opioides), hipotension, nausea/vomitos, hipo, sedacion prolongada en UCI. Tolerancia con uso cronico. Paradoja: agitacion/agresividad (raro en ninos).",
        "contraindicaciones": "Miastenia gravis no tratada, glaucoma de angulo cerrado no tratado, insuficiencia respiratoria severa, shock, hipersensibilidad a benzodiazepinas. <6 meses (precaucion, excepto UCI neonatal).",
    },
    "fenitoina": {
        "nombre": "Fenitoína",
        "clase": "Anticonvulsivante estabilizante de membrana (Hidantoína)",
        "descripcion": "Anticonvulsivante clasico del grupo de las hidantoinas. Estabiliza membranas neuronales limitando la propagacion de descargas epilepticas. Farmacocinetica no lineal.",
        "indicaciones": "Crisis focales y tonicoclonica generalizada (segunda linea), estatus epileptico, prevencion de crisis post-TEC o neurocirugia, neuralgia del trigemino (segunda linea).",
        "mecanismo": "Bloqueo de canales de Na+ voltaje-dependientes en estado de inactivacion, prolongando el periodo refractario y limitando la propagacion de descargas epilepticas. Estabilizacion de membrana neuronal.",
        "beneficios": "Amplia experiencia historica. Alternativa en estatus epileptico cuando fenobarbital no disponible. Costo bajo. Via oral y EV (lento, no IM).",
        "efectos_adversos": "Nistagmo, ataxia, mareos, somnolencia (dosis-dependente). Hiperplasia gingival, hirsutismo, rash. Sd. de Steven-Johnson (raro). Hepatotoxicidad. Osteoporosis (uso cronico). Teratogenico (Sd. fetal hidantoina).",
        "contraindicaciones": "Alergia a hidantoinas. Bradicardia sinusal, bloqueo AV (especialmente EV). Precaucion: insuficiencia hepatica, porfiria, embarazo (categoria D). Interacciones multiples (inductor CYP450).",
    },
    "naloxona": {
        "nombre": "Naloxona",
        "clase": "Antagonista Opioide μ (MOR) de acción rápida",
        "descripcion": "Antagonista competitivo de receptores opioides μ, κ y δ. Revierte rapidamente los efectos de los opioides incluyendo depresion respiratoria, sedacion e hipotension.",
        "indicaciones": "Reversion de sobredosis de opioides (depresion respiratoria, coma), reversion de depresion respiratoria neonatal por opioides maternos, diagnostico de dependencia opioide, reversion de efectos adversos opioides postoperatorios.",
        "mecanismo": "Antagonismo competitivo de receptores opioides μ > κ > δ. Desplaza a los opioides del receptor, revirtiendo todos los efectos (analgesia, depresion respiratoria, miosis, sedacion). Vida media corta (30-60 min).",
        "beneficios": "Farmaco salvador en sobredosis de opioides. Accion ultra-rapida (1-2 min EV, 3-5 min IM/intranasal). Amplio margen de seguridad. Formulacion nasal disponible (autoinyector). Reversible.",
        "efectos_adversos": "Sindrome de abstinencia opioide agudo (si dependencia: agitacion, vomitos, diarrea, midriasis, taquicardia, HTA). Arritmias. Edema pulmonar agudo (raro). Hiperalgesia. Corta duracion (puede requerir redosificacion).",
        "contraindicaciones": "Alergia conocida. Precaucion: dependencia opioide conocida (producir abstinencia severa), patologia cardiovascular (arritmias, HTA). Monitorizar por re-narcotizacion (vida media menor que la mayoria de opioides).",
    },
    "ketamina": {
        "nombre": "Ketamina",
        "clase": "Anestésico Disociativo / Antagonista NMDA",
        "descripcion": "Anestesico general disociativo con potente efecto analgesico. Bloquea receptores NMDA. Produce anestesia disociativa (el paciente parece despierto pero no responde).",
        "indicaciones": "Induccion anestesica, sedacion para procedimientos dolorosos (curaciones, fracturas, desbridamientos), analgesia en dolor agudo severo (dosis subdisociativas), estatus epileptico refractario, depresion resistente a tratamiento (dosis bajas, uso off-label).",
        "mecanismo": "Antagonismo no competitivo de receptores NMDA (glutamato) en SNC y asta dorsal medular. Bloqueo de canales ionicos asociados. Interaccion con receptores opioides μ y σ. Modulacion de monoaminas.",
        "beneficios": "Preserva reflejos protectores de via aerea y respiracion espontanea (dosis sedantes). Potente analgesia. Inicio rapido. Sin depresion cardiovascular (aumenta PA y FC). Util en hemodinamicamente inestables.",
        "efectos_adversos": "Alucinaciones/emergencia disociativa (pesadillas, ilusiones), nistagmo, sialorrea, HTA, taquicardia, nausea/vomitos. Hipertension intracraneal (dosis altas). Laringoespasmo (raro). Dependencia psicologica con uso cronico.",
        "contraindicaciones": "HTA no controlada severa, preeclampsia/eclampsia, aneurisma, HIC significativa (precaucion), glaucoma de angulo cerrado, hipertiroidismo, psicosis activa, alergia conocida.",
    },
    "fluconazol": {
        "nombre": "Fluconazol",
        "clase": "Antifúngico Triazólico",
        "descripcion": "Antifungico triazolico de amplio espectro. Activo contra la mayoria de especies de Candida y Cryptococcus. Alta biodisponibilidad oral. Buena penetracion a SNC y tejidos.",
        "indicaciones": "Candidiasis oral, esofagica, vaginal y sistémica, candidemia, criptococosis (meningea y pulmonar), profilaxis antifungica en inmunocomprometidos (HIV, trasplante, QT prolongada). Dermatofitosis (tiña, pitiriasis versicolor).",
        "mecanismo": "Inhibicion de la 14α-demetilasa fungica (lanosterol 14α-demetilasa, CYP51), bloqueando la conversion de lanosterol en ergosterol, componente esencial de la membrana celular fungica. Fungistatico.",
        "beneficios": "Excelente biodisponibilidad oral (90%). Buena penetracion a SNC (60-80% niveles plasmaticos). Dosis unica diaria (larga vida media ~30hs). Bien tolerado. Variedad de formulaciones (oral, EV).",
        "efectos_adversos": "Nausea, cefalea, rash, dolor abdominal, elevacion reversible de transaminasas. Hepatitis (raro, 1:10.000). Alopecia (uso prolongado). Prolongacion QT (raro). Sindrome de Stevens-Johnson (raro).",
        "contraindicaciones": "Alergia a azoles. Uso concomitante con terfenadina, cisaprida, astemizol, quinidina (prolongacion QT). Precaucion en insuficiencia hepatica y renal. Embarazo (categoria D, altas dosis).",
    },
    "aciclovir": {
        "nombre": "Aciclovir",
        "clase": "Antiviral (Análogo de Nucleósido)",
        "descripcion": "Antiviral analogo de la guanosina. Activo contra virus herpes simplex (HSV-1, HSV-2), varicela zoster (VZV) y Epstein-Barr (EBV). Requiere activacion por timidina quinasa viral.",
        "indicaciones": "Herpes simple genital y labial, varicela (iniciar dentro 24hs del rash), herpes zoster, encefalitis herpetica, infecciones neonatales por HSV, queratitis herpetica, profilaxis CMV en trasplante.",
        "mecanismo": "Fosforilacion selectiva por timidina quinasa viral a aciclovir monofosfato, luego a trifosfato por enzimas celulares. Inhibicion competitiva de ADN polimerasa viral e incorporacion al ADN viral (terminacion de cadena).",
        "beneficios": "Altamente selectivo para celulas infectadas (baja toxicidad celular). Eficaz contra HSV y VZV. Bien tolerado. Formulaciones oral, topica, EV, oftalmica. Seguridad en embarazo (categoria B).",
        "efectos_adversos": "Nausea, diarrea, cefalea, rash. EV: flebitis, nefrotoxicidad por precipitacion tubular (administrar hidratacion, infusion lenta 1h). Neurotoxicidad (dosis altas, IR). Raro: Sd. hemolitico-uremico.",
        "contraindicaciones": "Alergia conocida. Precaucion en insuficiencia renal (ajustar por CrCl), deshidratacion, neuropatia. Embarazo: categoria B (seguro, beneficio > riesgo). Lactancia: compatible.",
    },
    "oseltamivir": {
        "nombre": "Oseltamivir",
        "clase": "Antiviral (Inhibidor de Neuraminidasa)",
        "descripcion": "Antiviral especifico contra influenza A y B. Inhibidor de la neuraminidasa viral. Profarmaco que se convierte en oseltamivir carboxilato activo en higado.",
        "indicaciones": "Tratamiento de influenza A y B (iniciar dentro 48hs de sintomas), profilaxis post-exposicion en contactos cercanos, profilaxis estacional en poblaciones de riesgo (inmunocomprometidos, no vacunados).",
        "mecanismo": "Inhibicion competitiva y selectiva de la neuraminidasa viral (NA), impidiendo la liberacion de viriones de la celula infectada y su propagacion a celulas vecinas. Reduce duracion y severidad de sintomas.",
        "beneficios": "Reduce duracion de influenza en 1-2 dias si se inicia temprano. Reduce complicaciones (otitis, neumonia, hospitalizacion). Profilaxis efectiva. Formulacion liquida pediatrica disponible.",
        "efectos_adversos": "Nausea, vomitos (mas frecuente en ninos, tomar con alimentos), cefalea. Broncoespasmo. Raro: eventos neuropsiquiatricos (delirio, alucinaciones, convulsiones, principalmente en ninos en Japon, causa no establecida).",
        "contraindicaciones": "Alergia conocida. Insuficiencia renal severa (CrCl <10 ml/min, ajustar dosis). Precaucion: embarazo (categoria C, beneficio > riesgo en pandemia), lactancia.",
    },
}

# ============================================================
# ATOMIZACION PARA BUSQUEDA INTELIGENTE
# ============================================================
# Mapa de nombres alternativos, marcas y variantes al nombre canonico
_ALIASES: dict[str, str] = {
    "paracetamol": "acetaminofen",
    "acetaminofeno": "acetaminofen",
    "tylenol": "acetaminofen",
    "panadol": "acetaminofen",
    "amoxidal": "amoxicilina",
    "amoxil": "amoxicilina",
    "augmentin": "amoxicilina_clavulanico",
    "amoxiclav": "amoxicilina_clavulanico",
    "clavulin": "amoxicilina_clavulanico",
    "azitromax": "azitromicina",
    "albuterol": "salbutamol",
    "ventolin": "salbutamol",
    "decadron": "dexametasona",
    "fortecortin": "dexametasona",
    "metamizol": "dipirona",
    "novalgina": "dipirona",
    "dalsy": "ibuprofeno",
    "advil": "ibuprofeno",
    "motrin": "ibuprofeno",
    "rocephin": "ceftriaxona",
    "zofran": "ondansetron",
    "valium": "diazepam",
    "losec": "omeprazol",
    "meprazol": "omeprazol",
    "omal": "omeprazol",
    "lasix": "furosemida",
    "renitec": "enalapril",
    "enalaprilato": "enalapril",
    "plasil": "metoclopramida",
    "cloridrato": "metoclopramida",
    "claritine": "loratadina",
    "loratadina": "loratadina",
    "epinefrina": "adrenalina",
    "prednisona": "prednisolona",
    "keflex": "cefalexina",
    "dalacin": "clindamicina",
    "cleocin": "clindamicina",
    "keppra": "levetiracetam",
    "epanutin": "fenitoina",
    "dilantin": "fenitoina",
    "narcan": "naloxona",
    "ketalar": "ketamina",
    "diflucan": "fluconazol",
    "zovirax": "aciclovir",
    "tamiflu": "oseltamivir",
}


def normalizar_medicamento(texto: str) -> Optional[str]:
    """Busca un medicamento en el texto y devuelve la clave canonica en FARMACOPEA.
    Ej: 'que es ibuprofeno' -> 'ibuprofeno', 'para que sirve el omeprazol' -> 'omeprazol'
    """
    tl = texto.lower().strip()
    # Busqueda directa
    for clave in FARMACOPEA:
        if clave in tl:
            return clave
    # Busqueda por nombre mas largo primero para evitar matches parciales
    nombres = sorted(FARMACOPEA.keys(), key=len, reverse=True)
    for clave in nombres:
        nombre = FARMACOPEA[clave]["nombre"].lower()
        if nombre in tl:
            return clave
    # Busqueda por alias
    for alias, clave in _ALIASES.items():
        if alias in tl:
            return clave
    return None


def buscar_medicamento(consulta: str) -> Optional[dict]:
    """Busca informacion de medicamento en la consulta. Devuelve dict con info formateada si encuentra."""
    clave = normalizar_medicamento(consulta)
    if not clave:
        return None
    med = FARMACOPEA[clave]
    return {
        "clave": clave,
        "nombre": med["nombre"],
        "clase": med["clase"],
        "descripcion": med["descripcion"],
        "indicaciones": med["indicaciones"],
        "mecanismo": med["mecanismo"],
        "beneficios": med["beneficios"],
        "efectos_adversos": med["efectos_adversos"],
        "contraindicaciones": med["contraindicaciones"],
    }


def formatear_info_medicamento(info: dict) -> str:
    """Formatea la informacion de un medicamento para mostrar en el chat."""
    return (
        f"**{info['nombre']}** ({info['clase']})\n\n"
        f"**Descripcion:** {info['descripcion']}\n\n"
        f"**Indicaciones:** {info['indicaciones']}\n\n"
        f"**Mecanismo de accion:** {info['mecanismo']}\n\n"
        f"**Beneficios:** {info['beneficios']}\n\n"
        f"**Efectos adversos:** {info['efectos_adversos']}\n\n"
        f"**Contraindicaciones:** {info['contraindicaciones']}"
    )
