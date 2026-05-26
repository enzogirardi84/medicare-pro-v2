import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:local_auth/local_auth.dart';
import 'package:medicare_mobile/config.dart';
import 'package:medicare_mobile/models/auth.dart';
import 'package:medicare_mobile/services/api_service.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthService {
  final ApiService _api;
  final LocalAuthentication _localAuth;

  static const _sessionKey = 'medicare_session';
  static const _biometricKey = 'medicare_biometric_enabled';

  UserSession? _currentSession;
  UserSession? get currentSession => _currentSession;
  AuthStatus get status => _currentSession == null
      ? AuthStatus.unauthenticated
      : _currentSession!.isExpired
          ? AuthStatus.unauthenticated
          : AuthStatus.authenticated;

  bool get isLoggedIn => status == AuthStatus.authenticated;
  String? get token => _currentSession?.accessToken;

  AuthService({
    required ApiService api,
    LocalAuthentication? localAuth,
  })  : _api = api,
        _localAuth = localAuth ?? LocalAuthentication();

  Future<bool> isBiometricAvailable() async {
    try {
      return await _localAuth.canCheckBiometrics;
    } catch (_) {
      return false;
    }
  }

  Future<LoginResponse> login(String username, String password, {String? empresa}) async {
    final data = await _api.post(AppConfig.loginUrl, {
      'username': username,
      'password': password,
      if (empresa != null) 'empresa': empresa,
    });
    final response = LoginResponse.fromJson(data);
    await _saveSession(response);
    return response;
  }

  Future<void> _saveSession(LoginResponse response) async {
    _currentSession = UserSession(
      accessToken: response.accessToken,
      username: response.username,
      rol: response.rol,
      empresa: response.empresa,
      expiresAt: DateTime.now().add(const Duration(seconds: 3600)),
    );
    _api.setToken(response.accessToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_sessionKey, jsonEncode(_currentSession!.toJson()));
  }

  Future<bool> authenticateWithBiometrics({String reason = 'Acceso biométrico a MediCare Pro'}) async {
    try {
      final available = await _localAuth.canCheckBiometrics;
      if (!available) return false;
      final authenticated = await _localAuth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(biometricOnly: true, stickyAuth: true),
      );
      return authenticated;
    } catch (_) {
      return false;
    }
  }

  Future<void> setBiometricEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_biometricKey, enabled);
  }

  Future<bool> isBiometricEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_biometricKey) ?? false;
  }

  Future<void> logout() async {
    _currentSession = null;
    _api.setToken(null);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_sessionKey);
  }

  Future<bool> tryRestoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_sessionKey);
      if (raw == null) return false;

      final json = jsonDecode(raw) as Map<String, dynamic>;
      _currentSession = UserSession.fromJson(json);
      if (_currentSession!.isExpired) {
        await logout();
        return false;
      }
      _api.setToken(_currentSession!.accessToken);
      return true;
    } catch (_) {
      await logout();
      return false;
    }
  }

  bool hasRole(String role) => _currentSession?.rol == role;
  bool get isAdmin => hasRole('admin');
  bool get isMedico => hasRole('medico');
}
