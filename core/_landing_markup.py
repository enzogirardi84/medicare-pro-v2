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
                  <div class="mc-lp-header-badge">Salud domiciliaria · Operación · Auditoría</div>
                </header>

                <div class="mc-lp-trust" role="region" aria-label="Compromisos de seguridad y soporte">
                  <div class="mc-lp-trust-inner">
                    <span class="mc-lp-trust-item">Cifrado en tránsito (HTTPS)</span>
                    <span class="mc-lp-trust-item">Accesos por rol</span>
                    <span class="mc-lp-trust-item">2FA por correo opcional</span>
                    <span class="mc-lp-trust-item">Soporte con contacto directo</span>
                  </div>
                </div>

                <main class="mc-lp-main">
                <section class="mc-lp-hero mc-lp-fade">
                  <div class="mc-lp-copy">
                    <div class="mc-lp-hero-badge">Enterprise · Salud domiciliaria · Auditoría clínica</div>
                    <p class="mc-lp-kicker">Gestión integral para instituciones de salud y operación domiciliaria</p>
                    <h1 class="mc-lp-h1">Unifique su operación clínica con trazabilidad <em>completa y defendible</em></h1>
                    <p class="mc-lp-lead">
                      <strong>MediCare Enterprise PRO</strong> es una plataforma integral de gestión sanitaria que centraliza
                      historia clínica, agenda de visitas, fichadas con GPS, emergencias, farmacopea, indicaciones médicas,
                      telemedicina, RRHH, inventario, facturación y auditoría legal en un solo entorno web seguro.
                      Diseñada para instituciones de salud domiciliaria, clínicas y equipos multidisciplinarios que necesitan
                      orden operativo, documentación profesional y respaldo auditable sin depender de planillas, capturas
                      sueltas ni sistemas desconectados.
                    </p>

                    <div class="mc-lp-cta-group">
                      <a class="mc-lp-btn-primary" href="#mc-lp-contact" aria-label="Solicitar demo en vivo de MediCare PRO">Solicitar demo en vivo</a>
                      <a class="mc-lp-btn-outline" href="#mc-lp-modulos" aria-label="Ver módulos del sistema">Explorar funcionalidades</a>
                    </div>

                    <div class="mc-lp-pill-row">
                      <span class="mc-lp-pill"><strong>Web</strong> y celular</span>
                      <span class="mc-lp-pill"><strong>Roles</strong> y permisos</span>
                      <span class="mc-lp-pill"><strong>Trazabilidad</strong> total</span>
                      <span class="mc-lp-pill"><strong>App paciente</strong> con triage</span>
                      <span class="mc-lp-pill"><strong>Farmacopea</strong> integrada</span>
                      <span class="mc-lp-pill"><strong>Chatbot</strong> clínico IA</span>
                    </div>

                    <div class="mc-lp-proof-row">
                      <div class="mc-lp-proof">
                        <b>Agenda + GPS + Fichadas</b>
                        <span>Visitas con control geográfico, horario y documentación de cada intervención profesional.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>Historia clínica completa</b>
                        <span>Vitales, evolución, escalas, pediatría, estudios, recetas y planes en un solo flujo clínico.</span>
                      </div>
                      <div class="mc-lp-proof">
                        <b>Auditoría y respaldo legal</b>
                        <span>PDF profesionales, consentimientos informados, recetas firmadas y exportes con trazabilidad lista para presentar.</span>
                      </div>
                    </div>
                  </div>

                  <aside class="mc-lp-board" role="complementary" aria-label="Vista operativa del producto">
                    <div class="mc-lp-board-header">
                      <span class="mc-lp-board-side-label">Vista operativa</span>
                      <div class="mc-lp-status-indicator">Tiempo real</div>
                    </div>
                    <p class="mc-lp-board-title">Tablero unificado para dirección, clínica y operaciones</p>

                    <div class="mc-lp-flow">
                      <div class="mc-lp-flow-card mc-lp-flow-card-active">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-op" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Dashboard ejecutivo</b>
                          <p>KPIs en tiempo real: pacientes activos, visitas del día, urgencias, agenda y balance registrado.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Dirección</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-cli" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Historia clínica digital</b>
                          <p>Indicaciones, evolución, estudios, escalas clínicas, percentilos y adjuntos en un solo lugar.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Clínica</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-leg" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Documentación profesional</b>
                          <p>PDF ejecutivos, consentimientos informados, recetas digitales con firma y trazabilidad legal.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Legal</span>
                      </div>

                      <div class="mc-lp-flow-card">
                        <div class="mc-lp-flow-icon mc-lp-flow-icon-urg" aria-hidden="true"></div>
                        <div class="mc-lp-flow-body">
                          <b>Emergencias + App paciente</b>
                          <p>Triage, alertas, GPS y respuesta coordinada con antecedentes clínicos al instante.</p>
                        </div>
                        <span class="mc-lp-flow-tag">Urgencia</span>
                      </div>
                    </div>

                    <div class="mc-lp-board-footer">
                      <span><strong>Más de 35 módulos</strong> integrados en una misma plataforma web. Acceso por roles, cifrado extremo a extremo, visible desde celular y escritorio.</span>
                    </div>
                  </aside>
                </section>

                <section class="mc-lp-stats mc-lp-fade" aria-labelledby="mc-lp-stats-title">
                  <header class="mc-lp-stats-head">
                    <h2 id="mc-lp-stats-title" class="mc-lp-stats-h2">Una plataforma, todas las áreas de su institución</h2>
                  </header>
                  <div class="mc-lp-stat-grid">
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">35+</span>
                      <div class="mc-lp-stat-body">
                        <h3>Módulos integrados</h3>
                        <p>Dashboard, agenda, visitas, admisión, historia clínica, recetas, estudios, emergencias, telemedicina, inventario, caja, RRHH, auditoría legal y más.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">GPS</span>
                      <div class="mc-lp-stat-body">
                        <h3>Fichadas verificables</h3>
                        <p>Cada visita registra geolocalización, hora de llegada y salida, profesional actuante y documentación asociada.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">IA</span>
                      <div class="mc-lp-stat-body">
                        <h3>Asistente clínico inteligente</h3>
                        <p>Chatbot con acceso a datos del paciente, farmacopea y búsqueda web para respaldo en tiempo real durante la consulta.</p>
                      </div>
                    </div>
                    <div class="mc-lp-stat-item">
                      <span class="mc-lp-stat-num">Roles</span>
                      <div class="mc-lp-stat-body">
                        <h3>Seguridad por perfiles</h3>
                        <p>Administrador, coordinador, clínico, operativo y auditor. Cada usuario accede solo a la información de su responsabilidad.</p>
                      </div>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-section-head">
                  <span class="mc-lp-section-kicker">Propuesta de valor</span>
                  <h2 class="mc-lp-section-title">Menos fricción operativa, más control y credibilidad institucional</h2>
                  <p class="mc-lp-section-sub">
                    Unifique la operación clínica, la coordinación de visitas, la documentación legal y el control de gestión
                    en una sola plataforma. Ideal para dirección médica, supervisión de operaciones y equipos que necesitan
                    presentar resultados ante auditoría, financiadores o familiares con respaldo profesional y trazabilidad completa.
                  </p>
                </section>
            """



_PART_6 = """
                <section id="mc-lp-modulos" class="mc-lp-bento mc-lp-fade">
                  <article class="mc-lp-cell mc-lp-cell-hero">
                    <div class="mc-lp-cell-icon mc-lp-cell-icon-hero">
                      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Coordinación y gestión</span>
                    <h3>Dirección con visibilidad total de la operación</h3>
                    <p>
                      Dashboard ejecutivo con KPIS en tiempo real, agenda de visitas por profesional y paciente, fichadas
                      con GPS, control de guardias, RRHH con presentismo y reportes exportables. La operación completa
                      deja de depender de planillas paralelas, capturas sueltas o acuerdos informales difíciles de auditar.
                    </p>
                    <div class="mc-lp-cell-list">
                      <div class="mc-lp-cell-item"><strong>Dashboard ejecutivo</strong> con KPIs, gráficos semanales y calendario de actividad.</div>
                      <div class="mc-lp-cell-item"><strong>Visitas con fichada GPS</strong> y control de horarios por profesional.</div>
                      <div class="mc-lp-cell-item"><strong>Auditoría legal integrada</strong> con trazabilidad de cada acción del sistema.</div>
                      <div class="mc-lp-cell-item"><strong>Reportes ejecutivos PDF</strong> con resumen de pacientes, facturación y stock.</div>
                    </div>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-wide">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Historia clínica</span>
                    <h3>Registro clínico digital completo y unificado</h3>
                    <p>
                      Admisión de pacientes, signos vitales, evolución diaria, escalas clínicas, percentilos pediátricos,
                      estudios y resultados, indicaciones médicas y recetas digitales con firma. Todo en el mismo recorrido
                      clínico, sin saltar entre pantallas ni sistemas.
                    </p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M10 8v8M14 8v8M8 12h8"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Farmacopea</span>
                    <h3>Medicación segura</h3>
                    <p>Vademécum integrado con 50+ fármacos, calculadora de dosis pediátricas y alertas de interacciones. Indicaciones médicas con plan de administración.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Emergencias</span>
                    <h3>Respuesta coordinada</h3>
                    <p>Triage con niveles de prioridad, traslado, alertas a profesionales y acceso inmediato a antecedentes clínicos del paciente.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">Telemedicina + App</span>
                    <h3>Asistencia remota</h3>
                    <p>Sala de teleconsulta por paciente y día. App del paciente con alertas, GPS, triage y comunicación directa con el equipo.</p>
                  </article>

                  <article class="mc-lp-cell mc-lp-cell-mini">
                    <div class="mc-lp-cell-icon">
                      <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                    </div>
                    <span class="mc-lp-cell-eyebrow">RRHH y caja</span>
                    <h3>Control administrativo</h3>
                    <p>Fichajes, asistencia, inventario de materiales, caja diaria y balance hídrico integrados al mismo ecosistema.</p>
                  </article>
                </section>

                <section class="mc-lp-two-up mc-lp-fade">
                  <div class="mc-lp-panel">
                    <h3>Sin MediCare: cuando la información vive en silos</h3>
                    <p>
                      Historia clínica en papel o PDF suelto, agenda en planillas, visitas sin control horario,
                      recetas a mano, comunicación por WhatsApp, facturación en otro sistema. El resultado:
                      errores, demoras, riesgo legal y costo operativo oculto que crece con cada paciente.
                    </p>
                  </div>

                  <div class="mc-lp-panel">
                    <h3>Con MediCare Enterprise PRO</h3>
                    <div class="mc-lp-checks">
                      <div class="mc-lp-check">Dashboard ejecutivo con KPIs, alertas y calendario de actividad</div>
                      <div class="mc-lp-check">Historia clínica digital con firma, recetas y documentación exportable</div>
                      <div class="mc-lp-check">Visitas con fichada GPS, control horario y geolocalización verificable</div>
                      <div class="mc-lp-check">Auditoría legal con trazabilidad completa de cada acción del sistema</div>
                      <div class="mc-lp-check">Chatbot clínico con IA, farmacopea integrada y calculadora de dosis</div>
                      <div class="mc-lp-check">Emergencias, telemedicina, app paciente y RRHH en un mismo entorno</div>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-mini-grid mc-lp-fade">
                  <div class="mc-lp-mini-card">
                    <b>Dashboard ejecutivo</b>
                    <span>KPIs, gráficos de actividad semanal, calendario heatmap de 30 días y mapa geográfico de visitas con GPS.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Chatbot clínico IA</b>
                    <span>Asistente inteligente con acceso a datos del paciente, farmacopea, búsqueda web y contexto clínico completo.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Calculadora de dosis</b>
                    <span>Dosis pediátricas con 321 medicamentos del vademécum, alertas de seguridad y guía de dilución.</span>
                  </div>
                  <div class="mc-lp-mini-card">
                    <b>Seguridad y cumplimiento</b>
                    <span>Cifrado en tránsito, autenticación por roles, 2FA opcional, rate limiting y sanitización de datos contra XSS.</span>
                  </div>
                </section>
            """



_PART_7 = """
                <section id="mc-lp-contact" class="mc-lp-contact mc-lp-fade">
                  <div class="mc-lp-contact-head">
                    <p>Implementación y soporte directo</p>
                    <h3>Agendemos una demo guiada</h3>
                    <span>Sin compromiso. Recorremos juntos los módulos que necesita su institución, resolvemos dudas técnicas y armamos una propuesta a medida del volumen de operación.</span>
                  </div>

                  <div class="mc-lp-contact-grid">
                    <div class="mc-lp-contact-card">
                      <p class="nm">Enzo N. Girardi</p>
                      <p class="rl">Desarrollo técnico y soporte</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584302024" target="_blank" rel="noopener" aria-label="Contactar a Enzo Girardi por WhatsApp">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:enzogirardi84@gmail.com" aria-label="Enviar email a Enzo Girardi">Email</a>
                      </div>
                    </div>

                    <div class="mc-lp-contact-card">
                      <p class="nm">Dario Lanfranco</p>
                      <p class="rl">Implementación y contratos</p>
                      <div class="mc-lp-btns">
                        <a class="mc-lp-wa" href="https://wa.me/5493584201263" target="_blank" rel="noopener" aria-label="Contactar a Dario Lanfranco por WhatsApp">WhatsApp</a>
                        <a class="mc-lp-em" href="mailto:dariolanfrancoruffener@gmail.com" aria-label="Enviar email a Dario Lanfranco">Email</a>
                      </div>
                    </div>
                  </div>

                  <div class="mc-lp-incident">
                    <p>¿Ya usa MediCare PRO y necesita soporte técnico? Reporte incidencias con captura de pantalla y hora aproximada para atención prioritaria.</p>
                    <div class="mc-lp-btns">
                      <a class="mc-lp-su" href="mailto:enzogirardi84@gmail.com?subject=MediCare%20Enterprise%20-%20Incidencia%20tecnica" rel="noopener" aria-label="Abrir correo para reportar incidencia técnica">Reportar incidencia</a>
                    </div>
                  </div>
                </section>

                <section class="mc-lp-faq mc-lp-fade">
                  <header class="mc-lp-stats-head" style="margin-bottom:20px;">
                    <h2 class="mc-lp-stats-h2">Preguntas frecuentes</h2>
                  </header>
                  <details>
                    <summary>¿Cuánto tiempo lleva la implementación?</summary>
                    <div>La mayoría de las instituciones están operativas en 24-72 horas. La implementación incluye carga inicial de datos (pacientes, profesionales, farmacopea), configuración de roles y permisos, y una capacitación guiada por videollamada. No requiere infraestructura propia ni instalación de software.</div>
                  </details>
                  <details>
                    <summary>¿Puedo acceder desde el celular de los profesionales?</summary>
                    <div>Sí. La plataforma funciona en cualquier navegador moderno (Chrome, Safari, Firefox) tanto en escritorio como en celular. No requiere instalar ninguna aplicación. Los profesionales pueden fichar visitas, ver indicaciones y cargar evolución desde su teléfono personal.</div>
                  </details>
                  <details>
                    <summary>¿Los datos están seguros? ¿Hay cifrado?</summary>
                    <div>Todas las conexiones viajan cifradas con HTTPS. El almacenamiento utiliza cifrado en reposo y las claves de acceso se guardan con hashing bcrypt. La autenticación puede reforzarse con 2FA por correo. Los datos se alojan en servidores cloud con redundancia geográfica y backup diario automatizado.</div>
                  </details>
                  <details>
                    <summary>¿Se puede facturar desde la plataforma?</summary>
                    <div>Sí. El módulo de caja permite registrar cobros, generar comprobantes y llevar un libro diario. Para facturación electrónica con AFIP/ARCA, la plataforma se integra con sistemas externos mediante la API de exportación de datos contables.</div>
                  </details>
                  <details>
                    <summary>¿Hay soporte técnico incluido?</summary>
                    <div>Sí. El soporte está a cargo del equipo de desarrollo con respuesta por WhatsApp y correo electrónico en horario laboral. Las incidencias críticas (plataforma caída, error de acceso) se atienden con prioridad inmediata. Para implementaciones grandes se puede contratar soporte extendido 24/7.</div>
                  </details>
                </section>

                <p class="mc-lp-tagline">
                  <strong>MediCare Enterprise PRO</strong> · Plataforma integral de gestión sanitaria con enfoque en
                  operación clínica, coordinación domiciliaria, trazabilidad documental y auditoría profesional.
                  Acceso exclusivo para personal autorizado. Cifrado HTTPS · Autenticación por roles · 2FA opcional.
                </p>



                <div class="mc-lp-cta-wrap">
                  <p>¿Ya conoce la plataforma?</p>
                  <h3>Ingrese a la demo operativa</h3>
                  <span>Explore módulos, permisos, documentación y herramientas clínicas en un entorno de prueba completo.</span>
                  <br><br>
                  <a class="mc-lp-btn-primary" href="?login=1" style="min-height:52px;padding:0 32px;font-size:1rem;text-transform:uppercase;letter-spacing:0.12em;">�??? Ingresar al sistema</a>
                </div>
                </main>
              </div>
            </div>
            """




