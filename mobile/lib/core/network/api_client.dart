import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'api_exception.dart';

/// Thin HTTP client around the SwimLap API.
///
/// Single responsibility: attach the base URL + bearer token, encode/decode
/// JSON, and translate error envelopes into [ApiException]. Feature repositories
/// depend on this, not on `package:http` directly.
///
/// **HTTPS only in release** (PRD §4): the app refuses a plain-HTTP endpoint in a
/// release build. Debug builds may use `http://10.0.2.2` for the emulator.
class ApiClient {
  ApiClient({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client() {
    if (kReleaseMode && !baseUrl.startsWith('https://')) {
      throw ArgumentError('Refusing insecure API endpoint in release build: $baseUrl');
    }
  }

  final String baseUrl;
  final http.Client _client;
  String? _token;

  void setToken(String? token) => _token = token;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  Future<dynamic> get(String path) => _send('GET', path);

  Future<dynamic> post(String path, {Object? body}) => _send('POST', path, body: body);

  Future<dynamic> _send(String method, String path, {Object? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    late http.Response res;
    try {
      final req = http.Request(method, uri)..headers.addAll(_headers);
      if (body != null) req.body = jsonEncode(body);
      final streamed = await _client.send(req).timeout(const Duration(seconds: 15));
      res = await http.Response.fromStream(streamed);
    } catch (e) {
      // Network-level failure — surfaced so callers can buffer and retry.
      throw ApiException('NETWORK_ERROR', 'Could not reach the server: $e');
    }

    final isJson = (res.headers['content-type'] ?? '').contains('application/json');
    final decoded = isJson && res.body.isNotEmpty ? jsonDecode(res.body) : null;

    if (res.statusCode >= 200 && res.statusCode < 300) {
      return decoded;
    }
    if (decoded is Map && decoded['code'] != null) {
      throw ApiException(
        decoded['code'] as String,
        (decoded['message'] ?? '') as String,
        status: res.statusCode,
        details: (decoded['details'] as Map?)?.cast<String, dynamic>(),
      );
    }
    throw ApiException('HTTP_${res.statusCode}', 'Request failed', status: res.statusCode);
  }
}
