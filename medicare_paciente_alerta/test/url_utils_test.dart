import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/utils/url_utils.dart';

void main() {
  group('normalizeApiBaseUrl', () {
    test('null o vacio', () {
      expect(normalizeApiBaseUrl(''), isNull);
      expect(normalizeApiBaseUrl('   '), isNull);
    });

    test('agrega https y quita barra final del host', () {
      expect(
        normalizeApiBaseUrl('abcdefgh.supabase.co/'),
        'https://abcdefgh.supabase.co',
      );
    });

    test('acepta https explicito', () {
      expect(
        normalizeApiBaseUrl('https://x.supabase.co'),
        'https://x.supabase.co',
      );
    });

    test('conserva subruta sin barra final redundante', () {
      expect(
        normalizeApiBaseUrl('https://example.com/custom/v1/'),
        'https://example.com/custom/v1',
      );
    });

    test('host invalido', () {
      expect(normalizeApiBaseUrl('https://'), isNull);
      expect(normalizeApiBaseUrl('ftp://x.com'), isNull);
    });
  });
}
