class AppConfig {
  AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String apiPrefix = '/v1';

  static const Duration requestTimeout = Duration(seconds: 15);
  static const int maxRetries = 3;
  static const int sessionExpirySeconds = 3600;

  static const String appName = 'MediCare Pro';
  static const String appVersion = '1.0.0';

  static String get loginUrl => '$apiPrefix/auth/login';
  static String get patientsUrl => '$apiPrefix/patients';
  static String patientUrl(String id) => '$apiPrefix/patients/$id';
  static String get evolutionsUrl => '$apiPrefix/evolutions';
  static String get vitalsUrl => '$apiPrefix/vitals';
  static String get searchUrl => '$apiPrefix/search';
  static String get healthUrl => '$apiPrefix/health';
}
