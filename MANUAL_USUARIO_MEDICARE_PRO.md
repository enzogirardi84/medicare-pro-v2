# Manual de Usuario — MediCare Enterprise PRO

> **Versión:** Build 2026-04-26  
> **Dirigido a:** Personal de clínicas, centros de salud y empresas de salud  
> **Propósito:** Explicar qué hace la aplicación, cómo funciona y cómo usar cada módulo.

---

## 1. ¿Qué es MediCare Enterprise PRO?

MediCare Enterprise PRO es un **sistema integral de gestión clínica y administrativa** desarrollado para clínicas, centros de salud, consultorios y redes de profesionales médicos.

Está construido como una aplicación web moderna que corre en el navegador (Google Chrome, Firefox, Edge, Safari) y permite operar desde computadoras de escritorio, notebooks, tablets y celulares.

### Objetivo principal
Centralizar toda la información de una institución de salud en un solo lugar:
- **Pacientes** y su historia clínica
- **Turnos y agenda** de profesionales
- **Evoluciones y estudios** médicos
- **Recetas y medicación**
- **Inventario, materiales y caja**
- **Personal y roles**
- **Auditoría y cumplimiento legal**

---

## 2. Arquitectura y Funcionamiento General

### 2.1. Tecnología base
- **Frontend:** Streamlit (interfaz web responsiva)
- **Backend:** Python + Supabase (PostgreSQL en la nube)
- **Modo offline:** Si falla internet, la app puede seguir funcionando con datos locales y sincronizar cuando vuelva la conexión.
- **Seguridad:** Contraseñas encriptadas, roles y permisos, doble factor de autenticación (2FA) por correo electrónico opcional.

### 2.2. Flujo de datos
```
Usuario → Navegador → App MediCare → Supabase (nube)
                              ↓
                         JSON local (respaldo/offline)
```

- Los datos se guardan principalmente en **Supabase** (base de datos en la nube segura).
- Si no hay conexión, se activa **modo local** y los cambios se almacenan temporalmente en el equipo.
- Al volver la conexión, el sistema sincroniza automáticamente.

### 2.3. Autenticación y sesiones
1. El usuario ingresa con **usuario** y **contraseña**.
2. Si la cuenta tiene email configurado, puede recibir un **código de 6 dígitos** por correo (2FA).
3. También existe la opción **"Nueva contraseña con PIN"** para quienes olvidaron su clave y tienen un PIN de 4 dígitos cargado por coordinación.
4. La sesión tiene **tiempo de inactividad**: si no se usa la app por unos minutos, se cierra automáticamente por seguridad.

---

## 3. Roles de Usuario y Permisos

Cada usuario tiene un **rol** que define qué puede ver y hacer.

| Rol | Qué puede hacer |
|-----|----------------|
| **SuperAdmin** | Control total. Gestiona clínicas, usuarios, suspender/reactivar cuentas, ver todo. |
| **Admin** | Gestión avanzada. Puede ver datos de todas las clínicas si está configurado para multiclínica. |
| **Coordinador** | Gestiona el equipo de su clínica: crea usuarios, edita emails, suspende cuentas. |
| **Médico** | Acceso clínico completo: evoluciones, recetas, estudios, diagnósticos, historial. Puede borrar evoluciones y estudios. |
| **Enfermería** | Acceso clínico: registra evoluciones, administra dosis, cargar materiales, escalas clínicas. |
| **Operativo** | Acceso mixto: admisión de pacientes, agenda, recetas (cargar/recibir), materiales, caja, balance. |
| **Administrativo** | Gestión: inventario, caja, RRHH, asistencia, auditoría, reportes. |
| **Auditoría** | Solo lectura y reportes: dashboard, historial, PDFs, auditoría legal. |

### Reglas importantes
- Un médico **no puede** crear usuarios ni ver la caja de otra clínica.
- Un operativo **no puede** borrar evoluciones ni estudios (solo médicos).
- SuperAdmin y Coordinador son los únicos que pueden **eliminar o suspender** cuentas de equipo.
- En modo **multiclínica**, cada clínica tiene su base separada. Los usuarios globales (admin, superadmin) pueden operar entre clínicas.

---

## 4. Módulos de la Aplicación

A continuación se describe cada módulo del menú lateral, ordenado por área funcional.

---

### 4.1. 📍 Visitas y Agenda
**Área:** Atención al paciente / Turnos  
**Quién lo usa:** Operativo, Enfermería, Médico, Administrativo

**Funciones:**
- Ver y gestionar **turnos** de pacientes por profesional.
- Registrar **visitas** presenciales.
- Filtrar por fecha, profesional, clínica o estado (pendiente, atendido, cancelado).
- Agenda visual tipo calendario.

**Tip de uso:** Si trabajás en recepción, este es tu módulo principal para organizar la entrada de pacientes.

---

### 4.2. 📊 Dashboard
**Área:** Reportes y métricas  
**Quién lo usa:** Admin, Coordinador, Administrativo, Auditoría

**Funciones:**
- Métricas de atención: cantidad de pacientes atendidos, turnos del día, evoluciones registradas.
- Gráficos de actividad por clínica y por profesional.
- Alertas operativas (pacientes críticos, vencimientos, stock bajo).

**Tip de uso:** Ideal para la reunión diaria de coordinación o para reportar a dirección.

---

### 4.3. 🏥 Clínicas (panel global)
**Área:** Gestión institucional  
**Quién lo usa:** SuperAdmin, Admin

**Funciones:**
- Ver todas las clínicas/empresas registradas en el sistema.
- Activar o suspender clínicas por morosidad o decisión administrativa.
- Configurar parámetros por clínica.

**Tip de uso:** Solo visible para roles globales. Si no lo ves, es porque tu usuario es de una clínica específica.

---

### 4.4. 🩹 Admisión
**Área:** Registro de pacientes  
**Quién lo usa:** Operativo, Enfermería, Administrativo

**Funciones:**
- **Crear ficha de paciente:** nombre, DNI, fecha de nacimiento, sexo, obra social, teléfono, dirección, alergias, patologías.
- Buscar pacientes existentes.
- Asociar paciente a una empresa/clínica.

**Tip de uso:** Siempre buscá primero si el paciente ya existe para no crear duplicados.

---

### 4.5. 🩺 Clínica
**Área:** Atención médica general  
**Quién lo usa:** Médico, Enfermería, Operativo

**Funciones:**
- Acceso rápido a la ficha del paciente seleccionado.
- Registro de signos vitales, síntomas, observaciones.
- Vista resumida de la historia clínica activa.

---

### 4.6. 👶 Pediatría
**Área:** Atención infantil  
**Quién lo usa:** Médico pediatra, Enfermería pediátrica

**Funciones:**
- Ficha adaptada para menores: peso, talla, percentiles, vacunas, desarrollo.
- Registro de evoluciones pediátricas específicas.

---

### 4.7. ✍️ Evolución
**Área:** Historia clínica / Notas de evolución  
**Quién lo usa:** Médico, Enfermería, Operativo (solo lectura y carga limitada según rol)

**Funciones:**
- **Crear evolución:** texto libre + signos vitales (tensión, frecuencia cardíaca, temperatura, saturación).
- **Adjuntar fotos de heridas** (documentación fotográfica clínica).
- **Ver historial** de evoluciones del paciente con filtro por fecha.
- **Borrar evoluciones:** solo médicos pueden eliminar notas.
- **Descargar PDF** de evoluciones para imprimir o enviar.

**Importante:** Las evoluciones son datos clínicos críticos. Se guardan en Supabase con respaldo automático.

---

### 4.8. 🧪 Estudios
**Área:** Laboratorio e imágenes  
**Quién lo usa:** Médico, Enfermería, Operativo

**Funciones:**
- Registrar estudios solicitados: laboratorio, rayos, ecografía, etc.
- Cargar resultados (texto o valores numéricos).
- Ver historial de estudios por paciente.
- Borrar estudios: solo médicos.

---

### 4.9. 📦 Materiales
**Área:** Consumibles e insumos  
**Quién lo usa:** Operativo, Enfermería, Administrativo

**Funciones:**
- Registrar uso de materiales durante una atención (gasas, jeringas, medicación institucional).
- Vincular consumos a paciente y evolución.
- Reportes de consumo por período.

---

### 4.10. 💊 Recetas
**Área:** Prescripción farmacológica  
**Quién lo usa:** Médico (prescribir), Operativo/Enfermería (cargar/recibir)

**Funciones:**
- **Prescribir:** el médico carga medicamentos, dosis, frecuencia, duración.
- **Cargar receta en papel:** digitalizar una receta física escaneada o fotografiada.
- **Registrar administración de dosis:** enfermería marca qué medicamento le dio al paciente y a qué hora.
- **Cambiar estado:** médico puede anular o modificar una receta.

**Reglas de permisos:**
| Acción | Roles permitidos |
|--------|-----------------|
| Prescribir | Médico |
| Cargar receta papel | Operativo, Enfermería, Médico |
| Registrar dosis | Operativo, Enfermería, Médico |
| Cambiar estado | Médico |

---

### 4.11. 💧 Balance
**Área:** Control hidrico  
**Quién lo usa:** Enfermería, Médico, Operativo

**Funciones:**
- Registro de ingresos (sueros, medicación, alimentación) y egresos (orina, drenajes, vómitos) del paciente.
- Balance diario automático (total ingresos - total egresos).
- Alerta si el balance es negativo o anormal.

---

### 4.12. 🏭 Inventario
**Área:** Stock de insumos  
**Quién lo usa:** Administrativo, Operativo, Enfermería

**Funciones:**
- Stock de medicamentos, material de curación, equipos.
- Entradas (compras) y salidas (consumo).
- Alertas de stock mínimo.
- Vencimientos próximos.

---

### 4.13. 💵 Caja
**Área:** Finanzas / Tesorería  
**Quién lo usa:** Administrativo, Operativo, Coordinador

**Funciones:**
- Registro de movimientos: ingresos (cobros a pacientes, obras sociales) y egresos (pagos a proveedores, sueldos).
- Cierre parcial y total de caja.
- Extracto por fecha y por operador.

---

### 4.14. 🚑 Emergencias y Ambulancia
**Área:** Guardia y traslados  
**Quién lo usa:** Médico, Enfermería, Operativo

**Funciones:**
- Ficha de emergencia rápida: triage, motivo de consulta, clasificación de riesgo.
- Registro de traslados en ambulancia.
- Historial de atenciones de urgencia.

---

### 4.15. 📱 Alertas
**Área:** Notificaciones al paciente  
**Quién lo usa:** Operativo, Enfermería, Médico

**Funciones:**
- Enviar alertas y recordatorios a pacientes vía WhatsApp o notificación.
- Configurar alertas automáticas: turno próximo, medicación, controles pendientes.

**Nota:** Este módulo aparece solo si está habilitado en la configuración de la clínica.

---

### 4.16. 🤝 Red de Profesionales
**Área:** Directorio médico  
**Quién lo usa:** Todos los roles (consulta)

**Funciones:**
- Directorio de médicos, enfermeros, kinesiólogos, fonoaudiólogos, nutricionistas, psicólogos, etc.
- Ficha por profesional: matrícula, especialidad, obras sociales que atiende, contacto.
- Interconsulta: derivar un paciente a otro profesional de la red.

---

### 4.17. 📏 Escalas Clínicas
**Área:** Valoración estandarizada  
**Quién lo usa:** Médico, Enfermería, Operativo

**Funciones:**
- Aplicar escalas de valoración: Glasgow, Braden (úlceras), Norton, Barthel, etc.
- Guardar resultado con fecha y profesional.
- Evolución temporal de las escalas aplicadas.

---

### 4.18. 🗄️ Historial
**Área:** Archivo clínico completo  
**Quién lo usa:** Médico, Enfermería, Operativo, Auditoría

**Funciones:**
- **Vista unificada** de toda la historia del paciente: admisión, evoluciones, estudios, recetas, materiales, balance, escalas.
- Filtros por fecha, tipo de evento y módulo.
- **Descarga de PDF** completo del historial para presentaciones legales o auditoría.

---

### 4.19. 📄 PDF
**Área:** Documentos y reportes  
**Quién lo usa:** Todos los roles según permiso

**Funciones:**
- Exportar historia clínica a PDF profesional.
- Exportar datos a Excel (solo roles administrativos/auditoría).
- Generar respaldo de datos en PDF.
- Guardar y descargar **consentimientos informados** firmados.

**Reglas de permisos:**
| Acción | Roles permitidos |
|--------|-----------------|
| Exportar historia PDF | Operativo, Enfermería, Médico, Auditoría |
| Exportar Excel | Operativo, Auditoría |
| Respaldo PDF | Operativo, Enfermería, Médico, Auditoría |
| Consentimiento | Operativo, Enfermería, Médico |

---

### 4.20. 🎥 Telemedicina
**Área:** Consultas a distancia  
**Quién lo usa:** Médico, Enfermería, Operativo (coordina)

**Funciones:**
- Programar consultas virtuales.
- Integración con videollamada (si está configurada).
- Registro de la consulta remota en la historia clínica.

---

### 4.21. 🧮 Cierre Diario
**Área:** Control operativo diario  
**Quién lo usa:** Administrativo, Coordinador, Operativo

**Funciones:**
- Resumen del día: pacientes atendidos, turnos cumplidos, evoluciones cargadas, consumos, caja.
- Reporte diario automático para dirección.
- Comparación con días anteriores.

---

### 4.22. 👥 Mi Equipo
**Área:** Gestión de usuarios internos  
**Quién lo usa:** Coordinador, Admin, SuperAdmin

**Funciones:**
- Ver todos los usuarios de la clínica.
- **Crear usuario:** asignar nombre, login, rol, email, PIN, empresa.
- **Editar email** de un usuario.
- **Suspender/Reactivar** cuenta.
- **Eliminar usuario** (solo SuperAdmin o Coordinador, con restricciones).

**Reglas de seguridad:**
- No se puede eliminar un SuperAdmin desde una cuenta que no sea SuperAdmin.
- Un Coordinador solo puede suspender/eliminar usuarios de **su misma clínica** y con rol inferior.

---

### 4.23. 🛰️ Asistencia en Vivo
**Área:** Soporte y monitoreo  
**Quién lo usa:** Admin, SuperAdmin, Coordinador

**Funciones:**
- Ver quién está conectado en tiempo real.
- Monitorear actividad del sistema.
- Acceso a diagnóstico de rendimiento (solo administradores).

---

### 4.24. ⏱️ RRHH y Fichajes
**Área:** Recursos Humanos  
**Quién lo usa:** Administrativo, Coordinador, Admin

**Funciones:**
- Fichaje de entrada y salida del personal (reloj laboral).
- Cálculo de horas trabajadas.
- Licencias, ausencias y vacaciones.
- Nómina y sueldos (si está habilitado).

---

### 4.25. 🛠️ Proyecto y Roadmap
**Área:** Desarrollo del sistema  
**Quién lo usa:** SuperAdmin, Admin

**Funciones:**
- Ver funciones planificadas para futuras versiones.
- Reportar bugs o solicitar mejoras.
- Changelog (historial de cambios del sistema).

---

### 4.26. 🔎 Auditoría
**Área:** Logs del sistema  
**Quién lo usa:** Auditoría, Admin, SuperAdmin

**Funciones:**
- Ver todas las acciones realizadas en el sistema: quién hizo qué, cuándo y desde dónde.
- Filtros por fecha, usuario, módulo, paciente.
- **Descarga de PDF profesional** del log completo.

---

### 4.27. ⚖️ Auditoría Legal
**Área:** Traza para juicios o inspecciones  
**Quién lo usa:** Auditoría, Admin, SuperAdmin

**Funciones:**
- Registro firmado de eventos críticos: acceso a historia, modificaciones, borrados, exportaciones.
- Criticidad: baja, media, alta, crítica.
- **Descarga de PDF profesional** con formato legal para presentar en tribunales o auditorías externas.

---

### 4.28. ✅ Diagnósticos
**Área:** Codificación médica  
**Quién lo usa:** Médico, Enfermería, Operativo

**Funciones:**
- Registrar diagnósticos con código (CIE-10/CIE-11 si está configurado).
- Vincular diagnóstico a evolución y paciente.
- Estadísticas de morbilidad.

---

## 5. Navegación y Uso Básico

### 5.1. Primeros pasos
1. Abrí la app en tu navegador (la URL te la da tu coordinador o aparece en el QR de bienvenida).
2. Ingresá tu **usuario** y **contraseña**.
3. Si te piden un código de 6 dígitos, revisá tu correo electrónico (o pedile a coordinación que configure tu email).
4. Una vez dentro, vas a ver el **menú lateral izquierdo** con los módulos disponibles para tu rol.

### 5.2. Seleccionar paciente
En el sidebar (panel izquierdo) aparece:
- Un **buscador de pacientes**.
- Alertas clínicas (alergias, patologías críticas) del paciente seleccionado.
- El contexto clínico actual.

**Importante:** Muchos módulos (Evolución, Estudios, Recetas, Balance) funcionan sobre el **paciente seleccionado**. Si no elegís uno primero, la app te va a pedir que lo hagas.

### 5.3. Cambiar de módulo
Hacé clic en cualquier ítem del menú lateral. La app carga el módulo sin cerrar la sesión ni perder el paciente seleccionado.

### 5.4. Cerrar sesión
En la parte superior del sidebar hay un botón **"Cerrar sesión"**. Usalo siempre antes de irte, especialmente si compartís la computadora.

---

## 6. Datos, Respaldo y Seguridad

### 6.1. ¿Dónde se guardan los datos?
- **Primario:** Supabase (base PostgreSQL en la nube, con encriptación SSL).
- **Secundario:** Archivo JSON local en el servidor donde corre la app (modo offline).
- **Copia de seguridad:** Se recomienda descargar periódicamente el PDF de Auditoría Legal y el respaldo del módulo PDF.

### 6.2. Modo offline
Si ves el mensaje **"Modo local activo"**, significa que la app no pudo conectarse a Supabase. Podés seguir trabajando, pero:
- Los cambios se guardan localmente.
- Cuando vuelva la conexión, se sincronizan automáticamente.
- No envíes códigos 2FA ni esperes notificaciones por email en modo offline.

### 6.3. Auditoría y trazabilidad
- **Toda acción queda registrada:** quién, cuándo, qué hizo, sobre qué paciente.
- Los registros de Auditoría Legal tienen **valor probatorio**.
- No se pueden borrar logs (ni siquiera SuperAdmin).

---

## 7. Preguntas Frecuentes (FAQ)

**¿Qué hago si olvidé mi contraseña?**
> Andá a la pantalla de login, seleccioná **"Nueva contraseña con PIN"**, ingresá tu usuario y el PIN de 4 dígitos que te asignó coordinación. Si no tenés PIN, pedile una nueva contraseña a tu coordinador.

**¿Por qué no veo todos los módulos?**
> Tu rol determina qué módulos se muestran. Si necesitás acceso a uno que no ves, pedilo a tu coordinador.

**¿Puedo usar la app desde el celular?**
> Sí. La app se adapta automáticamente a pantallas chicas. Algunos módulos complejos (como PDF o Dashboard) se ven mejor en computadora.

**¿Qué pasa si borro una evolución por error?**
> Solo un médico puede borrar evoluciones. El borrado queda registrado en Auditoría Legal con criticidad **Crítica**. Si fue un error, comunicalo inmediatamente a coordinación.

**¿Cómo sé si mis datos están seguros?**
> Las contraseñas están encriptadas con bcrypt. La conexión a Supabase usa SSL. La sesión se cierra sola por inactividad. Y toda acción queda registrada.

---

## 8. Glosario

| Término | Significado |
|---------|-------------|
| **Supabase** | Base de datos en la nube que usa la app como almacén principal. |
| **Shard / Multiclínica** | Modo donde cada clínica tiene su base separada. |
| **2FA** | Doble factor de autenticación (código por email). |
| **Session state** | Memoria temporal de la app mientras estás conectado. |
| **Evolución** | Nota clínica que describe el estado del paciente en una atención. |
| **Triage** | Clasificación de urgencia en emergencias. |
| **CIE-10/11** | Clasificación internacional de enfermedades. |
| **PIN** | Código numérico de 4 dígitos para recuperación de contraseña. |

---

## 9. Contacto y Soporte

Si encontrás un error o necesitás ayuda:
1. Revisá la sección **"Problemas para ingresar o fallas del sistema"** en la pantalla de login.
2. Si ya estás dentro, andá al módulo **Proyecto y Roadmap** y reportá el bug.
3. Para soporte urgente, contactá a MediCare o a tu coordinador de clínica.

---

*Documento generado automáticamente para usuarios de MediCare Enterprise PRO.*  
*Última actualización: 2026-04-29*
