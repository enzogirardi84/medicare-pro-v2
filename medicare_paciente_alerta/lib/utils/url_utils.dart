/// Normaliza la URL base (https si falta, sin barra final). Conserva subrutas tipo /v1.
String? normalizeApiBaseUrl(String raw) {
  var s = raw.trim();
  if (s.isEmpty) return null;
  if (!RegExp(r'^https?://', caseSensitive: false).hasMatch(s)) {
    s = 'https://$s';
  }
  final uri = Uri.tryParse(s);
  if (uri == null || uri.host.isEmpty) return null;
  if (uri.scheme != 'http' && uri.scheme != 'https') return null;

  final origin = uri.origin;
  var path = uri.path;
  if (path.length > 1 && path.endsWith('/')) {
    path = path.substring(0, path.length - 1);
  }
  if (path.isEmpty || path == '/') {
    return origin;
  }
  return '$origin$path';
}
