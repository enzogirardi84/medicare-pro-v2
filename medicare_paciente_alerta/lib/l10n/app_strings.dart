/// Textos de la app (espanol). Un solo lugar para revisar mensajes al usuario.
abstract final class AppStrings {
  static const appTitle = 'MediCare Alerta';
  static const cargando = 'Cargando...';
  static const configErrorTitulo = 'No se pudo leer la configuracion guardada.';
  static const reintentar = 'Reintentar';
  static const configuracion = 'Configuracion';
  static String ajustesTooltipConPendientes(int n) =>
      'Configuracion. Hay $n alertas sin enviar.';
  static const guardado = 'Guardado';
  static const guardar = 'Guardar';
  static const probarConexion = 'Probar conexion a Supabase';
  static const probando = 'Probando...';
  static const conexionOk = 'Conexion correcta con el proyecto Supabase.';
  static const medicare = 'MediCare';
  static String versionEtiqueta(String version) => 'Version $version';

  static const ayudaIntro =
      'Si necesitas ayuda clinica de tu equipo, toca el boton rojo.';
  static const ultimaAlertaTitulo = 'Ultima alerta enviada';
  static const llamarEmergencias = 'Llamar emergencias (107)';
  static const llamarEmergenciasCon = 'Llamar emergencias';
  static String marcarEmergenciasManual(String numero) =>
      'No se pudo abrir el telefono. Si podes, marca $numero a mano.';
  static const disclaimerUrgencias = 'No reemplaza el servicio publico de urgencias.';
  static const necesitoAyudaLabel = 'Necesito ayuda clinica de mi equipo';
  static const necesitoAyudaHint = 'Abre la lista de sintomas para enviar una alerta';
  static const necesitoAyudaBoton = 'NECESITO\nAYUDA';

  static const hola = 'Hola';

  static const sintomasGuia =
      'Toca solo lo que te pasa ahora. Vas a tener unos segundos para cancelar antes de enviar.';
  static const queSentis = 'Que sentis?';

  static const confirmar = 'Confirmar';
  static const cancelar = 'Cancelar';
  static const volver = 'Volver';
  static const enviando = 'Enviando...';
  static const obteniendoUbicacion = 'Obteniendo ubicacion...';
  static const enviandoAlerta = 'Enviando alerta...';
  static const cuentaRegresiva = 'Si tocaste sin querer, volve atras.\nEnvio en';
  static const segundos = 'segundos';
  static const alertaEnviadaTitulo = 'Alerta enviada';
  static const alertaEnviadaSinGps = 'Tu equipo fue avisado. Activa el GPS para proximas veces.';
  static const alertaEnviadaConGps = 'Tu equipo fue avisado con tu ubicacion.';
  static const precisionMetros = 'Precision';
  static const ok = 'OK';
  static const copiarMensaje = 'Copiar mensaje';
  static const copiadoSoporte = 'Mensaje copiado (para enviar a soporte)';
  static const reintentarEnvio = 'Reintentar';

  static const sinRed = 'No hay wifi ni datos moviles. Conectate para poder avisar a tu equipo.';

  static const pendientesTitulo = 'Alertas sin enviar';
  static const pendientesSub = 'Se guardaron cuando fallo la conexion. Conectate y reenvia.';
  static const enviarPendientes = 'Enviar ahora';
  static const descartarPendientes = 'Descartar';
  static const pendientesEnviando = 'Enviando pendientes...';
  static const pendientesListo = 'Alertas pendientes enviadas.';
  static const pendientesParcial = 'Algunas alertas no se pudieron enviar. Reintenta mas tarde.';
  static const pendientesNada = 'No se pudo enviar ninguna. Revisa conexion y configuracion.';
  static const descartarPendientesTitulo = 'Descartar alertas guardadas?';
  static const descartarPendientesBody =
      'No se enviaran. Solo usa esto si ya avisaste por otro medio.';

  static const faltaConfiguracion =
      'Falta configuracion. Abri ajustes y completa los datos.';
  static const errorEnviarGenerico = 'Error al enviar';
  static const guardadoEnCola =
      'Se guardo en la cola para reenviar cuando haya conexion (desde la pantalla principal).';

  static String triajeEtiqueta(String nivelApi) => 'Triage: $nivelApi';

  static String sintomaSemanticsHint(String nivelApi) =>
      'Triage $nivelApi. Toca para confirmar envio';

  static const campoUrlSupabase = 'URL proyecto Supabase';
  static const hintUrlSupabase = 'https://xxxx.supabase.co';
  static const tooltipOcultar = 'Ocultar';
  static const tooltipMostrar = 'Mostrar';
  static const campoClaveAnon = 'Clave anon';
  static const campoSecretoIngesta = 'Secreto de ingesta (Edge Function)';
  static const campoClinica = 'Clinica (minusculas, igual que MediCare)';
  static const campoDni = 'DNI o codigo de paciente';
  static const campoNombre = 'Nombre (opcional)';
  static const campoTelefonoEmergencias =
      'Emergencias telefono (opcional, default 107)';

  static const salirConfirmTitulo = 'Salir del envio?';
  static const salirConfirmBody = 'La alerta todavia no se envio. Si salis, podes elegir otro sintoma.';
  static const salirSi = 'Salir';
  static const salirNo = 'Seguir aqui';
  static const enviandoNoSalir = 'Espera a que termine el envio.';

  static const configDatosClinica =
      'Datos que entrega tu clinica. Sin esto no se puede enviar la alerta a MediCare.';
  static const configClinicaAyuda =
      'La clinica debe coincidir con MediCare en minusculas (ej. clinica girardi).';
  static const urlInvalida = 'URL Supabase invalida (https://xxx.supabase.co)';
  static const dniCorto = 'DNI o codigo de paciente demasiado corto (minimo 3 caracteres).';
  static const textoGrandeTitulo = 'Texto mas grande';
  static const textoGrandeSub = 'Letras mas grandes en toda la app';
  static const cuentaRegresivaTitulo = 'Segundos antes de enviar';
  static const cuentaRegresivaSub = 'Tiempo para cancelar si tocaste sin querer (2 a 8 s).';
  static const altoContrasteTitulo = 'Alto contraste';
  static const altoContrasteSub = 'Bordes y textos mas marcados para leer mejor.';

  static const otroSintoma = 'Otro (no en la lista)';

  /// Etiquetas de sintomas (pantalla y cuerpo enviado al servidor).
  static const sintomaDisnea = 'Dificultad respiratoria';
  static const sintomaDolorPecho = 'Dolor de pecho';
  static const sintomaPerdidaConciencia = 'Perdida de conocimiento';
  static const sintomaConvulsiones = 'Convulsiones';
  static const sintomaAnafilaxia = 'Reaccion alergica grave';
  static const sintomaCaida = 'Caida de su altura';
  static const sintomaHeridaCortante = 'Herida cortante';
  static const sintomaDesmayoOk = 'Desmayo (recuperado)';
  static const sintomaFiebre = 'Fiebre';
  static const sintomaVomitos = 'Vomitos / nauseas';
  static const sintomaDolorGeneral = 'Dolor generalizado';
  static const sintomaDebilidad = 'Debilidad generalizada';

  static String sliderSegundos(int n) => '$n s';

  static String segundosRestantesParaEnviar(int n) => 'Quedan $n segundos para enviar';

  static const triageSeccionRojo = 'RIESGO DE VIDA';
  static const triageSeccionAmarillo = 'URGENCIA';
  static const triageSeccionVerde = 'CONSULTA';

  /// Red / Edge Function (mensajes para el usuario).
  static const sinConexionOTimeout =
      'Sin conexion o tiempo agotado. Revisa wifi o datos e intenta de nuevo.';
  static const noAutorizadoIngesta =
      'No autorizado (401). Verifica el secreto de ingesta en la app y en Supabase.';

  static String servidorRespuestaVacia(int code) =>
      'El servidor respondio $code. Revisa URL, clave anon y secreto de ingesta.';

  static String errorHttpDetalle(int code, String detalle) => 'Error $code: $detalle';

  static const supabaseUrlInvalidaEjemplo =
      'La URL no es valida. Ejemplo: https://abcdefgh.supabase.co';

  static String proyectoRespondioCodigo(int code) =>
      'El proyecto respondio $code. Verifica la URL.';

  static const tiempoAgotadoRed = 'Tiempo agotado. Revisa wifi o datos moviles.';
  static const noSePudoContactarServidor =
      'No se pudo contactar al servidor. Revisa la URL y tu conexion.';

  static const claveAnonRechazada =
      'La clave anon fue rechazada (401/403). Copiala de Supabase (Settings, API).';

  static String apiRestErrorCodigo(int code) =>
      'El API REST respondio error $code. Intenta mas tarde.';

  static const tiempoAgotadoClaveAnon = 'Tiempo agotado al probar la clave anon.';
}
