import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:medicare_mobile/config.dart';
import 'package:medicare_mobile/models/patient.dart';
import 'package:medicare_mobile/models/evolution.dart';
import 'package:medicare_mobile/models/vitals.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;
  final bool isNetworkError;
  const ApiException(this.statusCode, this.message, {this.isNetworkError = false});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiService {
  final String baseUrl;
  final http.Client _client;

  String? _token;

  ApiService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        _client = client ?? http.Client();

  void setToken(String? token) => _token = token;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    if (_token != null) 'Authorization': 'Bearer $_token',
  };

  Uri _uri(String path, [Map<String, String>? params]) {
    return Uri.parse('$baseUrl$path').replace(queryParameters: params);
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? params,
  }) async {
    final uri = _uri(path, params);
    final req = http.Request(method, uri)..headers.addAll(_headers);
    if (body != null) req.body = jsonEncode(body);

    http.StreamedResponse streamed;
    try {
      streamed = await _client
          .send(req)
          .timeout(AppConfig.requestTimeout);
    } on SocketException {
      throw const ApiException(0, 'Sin conexión al servidor', isNetworkError: true);
    } on TimeoutException {
      throw const ApiException(0, 'Tiempo de espera agotado', isNetworkError: true);
    } on http.ClientException {
      throw const ApiException(0, 'Error de conexión', isNetworkError: true);
    }

    final response = await http.Response.fromStream(streamed);
    final bodyStr = response.body;

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return bodyStr.isNotEmpty ? jsonDecode(bodyStr) as Map<String, dynamic> : {};
    }

    final detail = _parseError(bodyStr);
    if (response.statusCode == 401) {
      throw const ApiException(401, 'Sesión expirada');
    }
    throw ApiException(response.statusCode, detail);
  }

  String _parseError(String body) {
    if (body.isEmpty) return 'Error del servidor';
    try {
      final json = jsonDecode(body);
      return (json['detail'] ?? json['error'] ?? 'Error desconocido') as String;
    } catch (_) {
      return body.length > 120 ? 'Error del servidor' : body;
    }
  }

  Future<Map<String, dynamic>> get(String path, {Map<String, String>? params}) =>
      _request('GET', path, params: params);

  Future<Map<String, dynamic>> post(String path, Map<String, dynamic> body) =>
      _request('POST', path, body: body);

  Future<Map<String, dynamic>> put(String path, Map<String, dynamic> body) =>
      _request('PUT', path, body: body);

  Future<Map<String, dynamic>> delete(String path) =>
      _request('DELETE', path);

  Future<List<Patient>> getPatients({int page = 1, int pageSize = 50, String? search}) async {
    final params = <String, String>{'page': '$page', 'page_size': '$pageSize'};
    if (search != null && search.length >= 2) params['search'] = search;

    final data = await get(AppConfig.patientsUrl, params: params);
    final rawList = data['patients'] as List? ?? (data['data'] as List? ?? <dynamic>[]);
    return rawList.cast<Map<String, dynamic>>().map((e) => Patient.fromJson(e)).toList();
  }

  Future<Patient> getPatient(String id) async {
    final data = await get(AppConfig.patientUrl(id));
    return Patient.fromJson(data);
  }

  Future<Patient> createPatient(PatientCreate patient) async {
    final data = await post(AppConfig.patientsUrl, patient.toJson());
    return Patient.fromJson(data);
  }

  Future<Evolution> createEvolution(EvolutionCreate evolution) async {
    final data = await post(AppConfig.evolutionsUrl, evolution.toJson());
    return Evolution.fromJson(data);
  }

  Future<Vitals> createVitals(VitalsCreate vitals) async {
    final data = await post(AppConfig.vitalsUrl, vitals.toJson());
    return Vitals.fromJson(data);
  }

  Future<Map<String, dynamic>> search(String query, {String type = 'patient', int limit = 20}) async {
    return get(AppConfig.searchUrl, params: {'q': query, 'type': type, 'limit': '$limit'});
  }

  Future<Map<String, dynamic>> health() async => get(AppConfig.healthUrl);

  void dispose() => _client.close();
}
