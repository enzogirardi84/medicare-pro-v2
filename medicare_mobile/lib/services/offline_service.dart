import 'dart:async';
import 'dart:convert';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:medicare_mobile/models/patient.dart';
import 'package:medicare_mobile/models/evolution.dart';
import 'package:medicare_mobile/models/vitals.dart';
import 'package:medicare_mobile/services/api_service.dart';

class OfflineService {
  final ApiService _api;
  final Connectivity _connectivity;
  StreamSubscription<List<ConnectivityResult>>? _subscription;
  bool _online = true;

  static const _pendingEvolutionsKey = 'pending_evolutions';
  static const _pendingVitalsKey = 'pending_vitals';
  static const _cachedPatientsKey = 'cached_patients';

  bool get isOnline => _online;
  Stream<bool> get onConnectivityChanged => _connectivity.onConnectivityChanged
      .map((results) => !results.contains(ConnectivityResult.none));

  OfflineService({
    required ApiService api,
    Connectivity? connectivity,
  })  : _api = api,
        _connectivity = connectivity ?? Connectivity();

  Future<void> init() async {
    final results = await _connectivity.checkConnectivity();
    _online = !results.contains(ConnectivityResult.none);
    _subscription = _connectivity.onConnectivityChanged.listen((results) {
      _online = !results.contains(ConnectivityResult.none);
    });
  }

  Future<int> get pendingCount async {
    final prefs = await SharedPreferences.getInstance();
    final evos = jsonDecode(prefs.getString(_pendingEvolutionsKey) ?? '[]') as List;
    final vitals = jsonDecode(prefs.getString(_pendingVitalsKey) ?? '[]') as List;
    return evos.length + vitals.length;
  }

  Future<List<Patient>> getCachedPatients() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_cachedPatientsKey);
    if (raw == null) return [];
    final list = jsonDecode(raw) as List;
    return list.map((e) => Patient.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> cachePatients(List<Patient> patients) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_cachedPatientsKey, jsonEncode(patients.map((p) => p.toJson()).toList()));
  }

  Future<void> saveEvolutionOffline(EvolutionCreate evolution) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_pendingEvolutionsKey) ?? '[]';
    final list = jsonDecode(raw) as List;
    list.add(evolution.toJson());
    await prefs.setString(_pendingEvolutionsKey, jsonEncode(list));
  }

  Future<void> saveVitalsOffline(VitalsCreate vitals) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_pendingVitalsKey) ?? '[]';
    final list = jsonDecode(raw) as List;
    list.add(vitals.toJson());
    await prefs.setString(_pendingVitalsKey, jsonEncode(list));
  }

  Future<int> syncPending() async {
    if (!_online) return 0;
    int synced = 0;
    synced += await _syncList(_pendingEvolutionsKey, (item) => _api.post('/v1/evolutions', item));
    synced += await _syncList(_pendingVitalsKey, (item) => _api.post('/v1/vitals', item));
    return synced;
  }

  Future<int> _syncList(
    String key,
    Future<Map<String, dynamic>> Function(Map<String, dynamic>) syncFn,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw == '[]') return 0;

    final list = jsonDecode(raw) as List;
    if (list.isEmpty) return 0;

    int synced = 0;
    final remaining = <Map<String, dynamic>>[];

    for (final item in list) {
      try {
        await syncFn(item as Map<String, dynamic>);
        synced++;
      } on ApiException {
        remaining.add(item);
      }
    }
    await prefs.setString(key, jsonEncode(remaining));
    return synced;
  }

  void dispose() {
    _subscription?.cancel();
  }
}
