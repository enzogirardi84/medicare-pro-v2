import 'package:flutter/foundation.dart';
import 'package:medicare_mobile/models/auth.dart';
import 'package:medicare_mobile/models/evolution.dart';
import 'package:medicare_mobile/models/vitals.dart';
import 'package:medicare_mobile/services/auth_service.dart';
import 'package:medicare_mobile/services/offline_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _auth;
  AuthStatus _status = AuthStatus.unknown;
  UserSession? _session;

  AuthProvider(this._auth);
  AuthStatus get status => _status;
  UserSession? get session => _session;
  bool get isLoggedIn => _status == AuthStatus.authenticated;
  String? get token => _session?.accessToken;
  bool get isMedico => _session?.rol == 'medico';
  bool get isAdmin => _session?.rol == 'admin';

  Future<void> tryRestore() async {
    final ok = await _auth.tryRestoreSession();
    _status = ok ? AuthStatus.authenticated : AuthStatus.unauthenticated;
    _session = _auth.currentSession;
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    await _auth.login(username, password);
    _status = AuthStatus.authenticated;
    _session = _auth.currentSession;
    notifyListeners();
  }

  Future<void> logout() async {
    await _auth.logout();
    _status = AuthStatus.unauthenticated;
    _session = null;
    notifyListeners();
  }
}

class OfflineProvider extends ChangeNotifier {
  final OfflineService _offline;
  bool _isOnline = true;
  int _pendingSync = 0;

  OfflineProvider(this._offline);

  bool get isOnline => _isOnline;
  int get pendingSync => _pendingSync;

  Future<void> init() async {
    await _offline.init();
    _isOnline = _offline.isOnline;
    await _refreshPending();
    _offline.onConnectivityChanged.listen((online) {
      _isOnline = online;
      if (online) _syncPending();
      notifyListeners();
    });
  }

  Future<void> _refreshPending() async {
    _pendingSync = await _offline.pendingCount;
    notifyListeners();
  }

  Future<void> _syncPending() async {
    final synced = await _offline.syncPending();
    if (synced > 0) await _refreshPending();
  }

  Future<void> saveEvolutionOffline(EvolutionCreate evolution) async {
    await _offline.saveEvolutionOffline(evolution);
    await _refreshPending();
  }

  Future<void> saveVitalsOffline(VitalsCreate vitals) async {
    await _offline.saveVitalsOffline(vitals);
    await _refreshPending();
  }
}
