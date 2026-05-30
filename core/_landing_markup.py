"""HTML markup de la landing pre-login (extraido de _landing_html_parts.py)."""

_PART_5 = """
            <div class="mc-lp">
              <div class="mc-lp-bg"></div>
              <div class="mc-lp-noise" aria-hidden="true"></div>
              <div class="mc-lp-inner">
                <header class="mc-lp-header">
                  <div class="mc-lp-brand">
                    <div class="mc-lp-logo-wrap">__LOGO__</div>
                    <div>
                      <span class="mc-lp-brand-kicker">Plataforma integral</span>
                      <p class="mc-lp-brand-name">MediCare Enterprise PRO</p>
                    </div>
                  </div>
                  <div class="mc-lp-header-badge">Salud domiciliaria Â· OperaciÃ³n Â· AuditorÃ­a</div>
                </header>

                <div class="mc-lp-trust" role="region" aria-label="Compromisos de seguridad y soporte">
                  <div class="mc-lp-trust-inner">
                    <span class="mc-lp-trust-item">Cifrado en trÃ¡nsito (HTTPS)</span>
                    <span class="mc-lp-trust-item">Accesos por rol</span>
                    <span class="mc-lp-trust-item">2FA por correo opcional</span>
                    <span class="mc-lp-trust-item">Soporte con contacto directo</span>
                  </div>
                </div>

                <main class="mc-lp-main">
                <section class="mc-lp-hero mc-lp-fade">
                  <div class="mc-lp-copy">
                    <div class="mc-lp-hero-badge">Enterprise Â· Salud domiciliaria Â· AuditorÃ­a clÃ­nica</div>
                    <p class="mc-lp-kicker">GestiÃ³n integral para instituciones de salud y operaciÃ³n domiciliaria</p>
                    <h1 class="mc-lp-h1">Unifique su operaciÃ³n clÃ­nica con trazabilidad <em>completa y defendible</em></h1>
                    <p class="mc-lp-lead">
                      <strong>MediCare Enterprise PRO</strong> es una plataforma integral de gestiÃ³n sanitaria que centraliza
                      historia clÃ­nica, agenda de visitas, fichadas con GPS, emergencias, farmacopea, indicaciones mÃ©dicas,
                      telemedicina, RRHH, inventario, facturaciÃ³n y auditorÃ­a legal en un solo entorno web seguro.
                      DiseÃ±ada para instituciones de salud domiciliaria, clÃ­nicas y equipos multidisciplinarios que necesitan
                      orden operativo, documentaciÃ³n profesional y respaldo auditable sin depender de planillas, capturas
                      sueltas ni sistemas desconectados.
                    </p>

                    <div class="mc-lp-cta-group">
                      <a class="mc-lp-btn-primary" href="#mc-lp-contact" aria-label="Solicitar demo en vivo de MediCare PRO">Solicitar demo en vivo</a>
                      <a class="mc-lp-btn-outline" href="#mc-lp-modulos" aria-label="Ver mÃ³dulos del sistema">Explorar funcionalidades</a>
                    </div>

                    <div class="mc-lp-pill-row">
                      <span class="mc-lp-pill"><strong>Web</strong> y celular</span>
                      <span class="mc-lp-pill"><strong>Roles</strong> y permisos</span>
                      <span class="mc-lp-pill"><strong>Trazabilidad</strong> total</span>
                      <span class="mc-lp-pill"><strong>App paciente</strong> con triage</span>
                      <span class="mc-lp-pill"><strong>Farmacopea</strong> integrada</span>
                      <span class="mc-lp-pill"><strong>Chatbot</strong> clÃ­nico IA</span>
                    </div>

                    <div class="mc-lp-proof-row">
                      <div class="mc-lp-proof">
                        <b>Agenda + GPS + Fichadas</b>
                        <span>Visitas con control geogrÃ¡fico, horario y documentaciÃ³n de cada intervenciÃ³n profesional.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>Historia clÃ­nica completa</b>
                        <span>Vitales, evoluciÃ³n, escalas, pediatrÃ­a, estudios, recetas y planes en un solo flujo clÃ­nico.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>AuditorÃ­a y respaldo legal</b>
                        <span>PDF profesionales, consentimientos informados, recetas firmadas y exportes con trazabilidad lista para presentar.</span>
                      </div>
                    </div>
                  </div>

                  <aside class="mc-lp-board" role="complementary" aria-label="Vista operativa del producto">
                    <div class="mc-lp-board-header">
                      <span class="mc-lp-board-side-label">Vista operativa</span>
                      <div class="mc-lp-status-indicator">Tiempo real</div>
                    </div>
                    <p class="mc-lp-board-title">Tablero unificado para direcciÃ³n, clÃ­nica y operaciones</p>

                    <div class="mc-lp-flow">
                      <div class="mc-lp-flow-card mc-lp-flow-card-active">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-op" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Dashboard ejecutivo</b>
                          <p>KPIs en tiempo real: pacientes activos, visitas del dÃ­a, urgencias, agenda y balance registrado.</p>
                        </div>
                        <span class="mc-lp-flow-tag">DirecciÃ³n</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-cli" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Historia clÃ­nica digital</b>
                          <p>Indicaciones, evoluciÃ³n, estudios, escalas clÃ­nicas, percentilos y adjuntos en un solo lugar.</p>
                        </div>
                        <span class="mc-lp-flow-tag">ClÃ­nica</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-leg" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>DocumentaciÃ³n profesional</b>
                          <p>PDF ejecutivos, consentimientos informados, recetas digitales con firma y trazabilidad legal.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Legal</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-urg" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Emergencias + App paciente</b>
                          <p>Triage, alertas, GPS y respuesta coordinada con antecedentes clÃ­nicos al instante.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Urgencia</span>
                      </div>
                    </div>

                    <div class="mc-lp-board-footer">
                      <span><strong>MÃ¡s de 35 mÃ³dulos</strong> integrados en una misma plataforma web. Acceso por roles, cifrado extremo a extremo, visible desde celular y escritorio.</span>
                    </div>
                  </aside>
                </section>

                <section class="mc-lp-stats mc-lp-fade" aria-labelledby="mc-lp-stats-title">
                  <header class="mc-lp-stats-head">
                    <h2 id="mc-lp-stats-title" class="mc-lp-stats-h2">Una plataforma, todas las Ã¡reas de su instituciÃ³n</h2>
                  </header>
                  <div class="mc-lp-stat-grid">
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">35+</span>
                      <div class="mc-lp-stat-body">
                        <h3>MÃ³dulos integrados</h3>
                        <p>Dashboard, agenda, visitas, admisiÃ³n, historia clÃ­nica, recetas, estudios, emergencias, telemedicina, inventario, caja, RRHH, auditorÃ­a legal y mÃ¡s.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">GPS</span>
                      <div class="mc-lp-stat-body">
                        <h3>Fichadas verificables</h3>
                        <p>Cada visita registra geolocalizaciÃ³n, hora de llegada y salida, profesional actuante y documentaciÃ³n asociada.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">IA</span>
                      <div class="mc-lp-stat-body">
                        <h3>Asistente clÃ­nico inteligente</h3>
                        <p>Chatbot con acceso a datos del paciente, farmacopea y bÃºsqueda web para respaldo en tiempo real durante la consulta.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">Roles</span>
                      <div class="mc-lp-stat-body">
                        <h3>Seguridad por perfiles</h3>
                        <p>Administrador, coordinador, clÃ­nico, operativo y auditor. Cada usuario accede solo a la informaciÃ³n de su responsabilidad.</p>
                      </div>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-section-head">
                  <span class="mc-lp-section-kicker">Propuesta de valor</span>
                  <h2 class="mc-lp-section-title">Menos fricciÃ³n operativa, mÃ¡s control y credibilidad institucional</h2>
                  <p class="mc-lp-section-sub">
                    Unifique la operaciÃ³n clÃ­nica, la coordinaciÃ³n de visitas, la documentaciÃ³n legal y el control de gestiÃ³n
                    en una sola plataforma. Ideal para direcciÃ³n mÃ©dica, supervisiÃ³n de operaciones y equipos que necesitan
                    presentar resultados ante auditorÃ­a, financiadores o familiares con respaldo profesional y trazabilidad completa.
                  </p>
                </section>
            """



_PART_6 = """
                <section id="mc-lp-modulos" class="mc-lp-bento mc-lp-fade">
                  <article class="mc-lp-cell mc-lp-cell-hero">
                    <div class="mc-lp-cell-icon mc-lp-cell-icon-hero">
                      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">CoordinaciÃ³n y gestiÃ³n</span>
                    <h3>DirecciÃ³n con visibilidad total de la operaciÃ³n</h3>
                    <p>
                      Dashboard ejecutivo con KPIS en tiempo real, agenda de visitas por profesional y paciente, fichadas
                      con GPS, control de guardias, RRHH con presentismo y reportes exportables. La operaciÃ³n completa
                      deja de depender de planillas paralelas, capturas sueltas o acuerdos informales difÃ­ciles de auditar.
                    </p>
                    <div class="mc-lp-cell-list">
                      <div class="mc-lp-cell-item"><strong>Dashboard ejecutivo</strong> con KPIs, grÃ¡ficos semanales y calendario de actividad.</div>
                      <div class="mc-lp-cell-item"><strong>Visitas con fichada GPS</strong> y control de horarios por profesional.</div>
                      <div class="mc-lp-cell-item"><strong>AuditorÃ­a legal integrada</strong> con trazabilidad de cada acciÃ³n del sistema.</div>
                      <div class="mc-lp-cell-item"><strong>Reportes ejecutivos PDF</strong> con resumen de pacientes, facturaciÃ³n y stock.</div>
                    </div>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-wide">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Historia clÃ­nica</span>
                    <h3>Registro clÃ­nico digital completo y unificado</h3>
                    <p>
                      AdmisiÃ³n de pacientes, signos vitales, evoluciÃ³n diaria, escalas clÃ­nicas, percentilos pediÃ¡tricos,
                      estudios y resultados, indicaciones mÃ©dicas y recetas digitales con firma. Todo en el mismo recorrido
                      clÃ­nico, sin saltar entre pantallas ni sistemas.
                    </p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M10 8v8M14 8v8M8 12h8"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Farmacopea</span>
                    <h3>MedicaciÃ³n segura</h3>
                    <p>VademÃ©cum integrado con 50+ fÃ¡rmacos, calculadora de dosis pediÃ¡tricas y alertas de interacciones. Indicaciones mÃ©dicas con plan de administraciÃ³n.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Emergencias</span>
                    <h3>Respuesta coordinada</h3>
                    <p>Triage con niveles de prioridad, traslado, alertas a profesionales y acceso inmediato a antecedentes clÃ­nicos del paciente.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Telemedicina + App</span>
                    <h3>Asistencia remota</h3>
                    <p>Sala de teleconsulta por paciente y dÃ­a. App del paciente con alertas, GPS, triage y comunicaciÃ³n directa con el equipo.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">RRHH y caja</span>
                    <h3>Control administrativo</h3>
                    <p>Fichajes, asistencia, inventario de materiales, caja diaria y balance hÃ­drico integrados al mismo ecosistema.</p>
                  </article>
                </section>

                <section class="mc-lp-two-up mc-lp-fade">
                  <div class="mc-lp-panel">
                    <h3>Sin MediCare: cuando la informaciÃ³n vive en silos</h3>
                    <p>
                      Historia clÃ­nica en papel o PDF suelto, agenda en planillas, visitas sin control horario,
                      recetas a mano, comunicaciÃ³n por WhatsApp, facturaciÃ³n en otro sistema. El resultado:
                      errores, demoras, riesgo legal y costo operativo oculto que crece con cada paciente.
                    </p>
                  </div>

                  <div class="mc-lp-panel">
                    <h3>Con MediCare Enterprise PRO</h3>
                    <div class="mc-lp-checks">
                      <div class="mc-lp-check">Dashboard ejecutivo con KPIs, alertas y calendario de actividad</div>
                      <div class="mc-lp-check">Historia clÃ­nica digital con firma, recetas y documentaciÃ³n exportable</div>
                      <div class="mc-lp-check">Visitas con fichada GPS, control horario y geolocalizaciÃ³n verificable</div>
                      <div class="mc-lp-check">AuditorÃ­a legal con trazabilidad completa de cada acciÃ³n del sistema</div>
                      <div class="mc-lp-check">Chatbot clÃ­nico con IA, farmacopea integrada y calculadora de dosis</div>
                      <div class="mc-lp-check">Emergencias, telemedicina, app paciente y RRHH en un mismo entorno</div>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-mini-grid mc-lp-fade">
                  <div class="mc-lp-mini-card">
                    <b>Dashboard ejecutivo</b>
                    <span>KPIs, grÃ¡ficos de actividad semanal, calendario heatmap de 30 dÃ­as y mapa geogrÃ¡fico de visitas con GPS.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Chatbot clÃ­nico IA</b>
                    <span>Asistente inteligente con acceso a datos del paciente, farmacopea, bÃºsqueda web y contexto clÃ­nico completo.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Calculadora de dosis</b>
                    <span>Dosis pediÃ¡tricas con 321 medicamentos del vademÃ©cum, alertas de seguridad y guÃ­a de diluciÃ³n.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Seguridad y cumplimiento</b>
                    <span>Cifrado en trÃ¡nsito, autenticaciÃ³n por roles, 2FA opcional, rate limiting y sanitizaciÃ³n de datos contra XSS.</span>
                  </div>
                </section>
            """



_PART_7 = """
                <section id="mc-lp-contact" class="mc-lp-contact mc-lp-fade">
                  <div class="mc-lp-contact-head">
                    <p>ImplementaciÃ³n y soporte directo</p>
                    <h3>Agendemos una demo guiada</h3>
                    <span>Sin compromiso. Recorremos juntos los mÃ³dulos que necesita su instituciÃ³n, resolvemos dudas tÃ©cnicas y armamos una propuesta a medida del volumen de operaciÃ³n.</span>
                  </div>

                  <div class="mc-lp-contact-grid">
                    <div class="mc-lp-contact-card">
                      <p class="nm">Enzo N. Girardi</p>
                      <p class="rl">Desarrollo tÃ©cnico y soporte</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584302024" target="_blank" rel="noopener" aria-label="Contactar a Enzo Girardi por WhatsApp">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:enzogirardi84@gmail.com" aria-label="Enviar email a Enzo Girardi">Email</a>
                      </div>
                    </div>

                    <div class="mc-lp-contact-card">
                      <p class="nm">Dario Lanfranco</p>
                      <p class="rl">ImplementaciÃ³n y contratos</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584201263" target="_blank" rel="noopener" aria-label="Contactar a Dario Lanfranco por WhatsApp">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:dariolanfrancoruffener@gmail.com" aria-label="Enviar email a Dario Lanfranco">Email</a>
                      </div>
                    </div>
                  </div>

                  <div class="mc-lp-incident">
                    <p>Â¿Ya usa MediCare PRO y necesita soporte tÃ©cnico? Reporte incidencias con captura de pantalla y hora aproximada para atenciÃ³n prioritaria.</p>
                    <div class="mc-lp-btns">
                      <a class="mc-lp-su" href="mailto:enzogirardi84@gmail.com?subject=MediCare%20Enterprise%20-%20Incidencia%20tecnica" rel="noopener" aria-label="Abrir correo para reportar incidencia tÃ©cnica">Reportar incidencia</a>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-faq mc-lp-fade">
                  <header class="mc-lp-stats-head" style="margin-bottom:20px;">
                    <h2 class="mc-lp-stats-h2">Preguntas frecuentes</h2>
                  </header>
                  <details>
                    <summary>Â¿CuÃ¡nto tiempo lleva la implementaciÃ³n?</summary>
                    <div>La mayorÃ­a de las instituciones estÃ¡n operativas en 24-72 horas. La implementaciÃ³n incluye carga inicial de datos (pacientes, profesionales, farmacopea), configuraciÃ³n de roles y permisos, y una capacitaciÃ³n guiada por videollamada. No requiere infraestructura propia ni instalaciÃ³n de software.</div>
                  </details>
                  <details>
                    <summary>Â¿Puedo acceder desde el celular de los profesionales?</summary>
                    <div>SÃ­. La plataforma funciona en cualquier navegador moderno (Chrome, Safari, Firefox) tanto en escritorio como en celular. No requiere instalar ninguna aplicaciÃ³n. Los profesionales pueden fichar visitas, ver indicaciones y cargar evoluciÃ³n desde su telÃ©fono personal.</div>
                  </details>
                  <details>
                    <summary>Â¿Los datos estÃ¡n seguros? Â¿Hay cifrado?</summary>
                    <div>Todas las conexiones viajan cifradas con HTTPS. El almacenamiento utiliza cifrado en reposo y las claves de acceso se guardan con hashing bcrypt. La autenticaciÃ³n puede reforzarse con 2FA por correo. Los datos se alojan en servidores cloud con redundancia geogrÃ¡fica y backup diario automatizado.</div>
                  </details>
                  <details>
                    <summary>Â¿Se puede facturar desde la plataforma?</summary>
                    <div>SÃ­. El mÃ³dulo de caja permite registrar cobros, generar comprobantes y llevar un libro diario. Para facturaciÃ³n electrÃ³nica con AFIP/ARCA, la plataforma se integra con sistemas externos mediante la API de exportaciÃ³n de datos contables.</div>
                  </details>
                  <details>
                    <summary>Â¿Hay soporte tÃ©cnico incluido?</summary>
                    <div>SÃ­. El soporte estÃ¡ a cargo del equipo de desarrollo con respuesta por WhatsApp y correo electrÃ³nico en horario laboral. Las incidencias crÃ­ticas (plataforma caÃ­da, error de acceso) se atienden con prioridad inmediata. Para implementaciones grandes se puede contratar soporte extendido 24/7.</div>
                  </details>
                </section>

                <p class="mc-lp-tagline">
                  <strong>MediCare Enterprise PRO</strong> Â· Plataforma integral de gestiÃ³n sanitaria con enfoque en
                  operaciÃ³n clÃ­nica, coordinaciÃ³n domiciliaria, trazabilidad documental y auditorÃ­a profesional.
                  Acceso exclusivo para personal autorizado. Cifrado HTTPS Â· AutenticaciÃ³n por roles Â· 2FA opcional.
                </p>



                <div class="mc-lp-cta-wrap">
                  <p>Â¿Ya conoce la plataforma?</p>
                  <h3>Ingrese a la demo operativa</h3>
                  <span>Explore mÃ³dulos, permisos, documentaciÃ³n y herramientas clÃ­nicas en un entorno de prueba completo.</span>
                  <br><br>
                  <a class="mc-lp-btn-primary" href="?login=1" style="min-height:52px;padding:0 32px;font-size:1rem;text-transform:uppercase;letter-spacing:0.12em;">ðŸš€ Ingresar al sistema</a>
                </div>
                </main>
              </div>
            </div>
            """




