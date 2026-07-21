import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../../core/network/api_client.dart';
import '../domain/app_user.dart';

/// Owns login + token persistence. The token is stored in the platform secure
/// store (iOS keychain / Android keystore), **not** plain preferences (PRD §4),
/// and restored on launch so a timer is not forced to sign in every practice.
class AuthRepository {
  AuthRepository(this._api, {FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final ApiClient _api;
  final FlutterSecureStorage _storage;
  static const _tokenKey = 'swimlap.token';

  Future<AppUser> login(String username, String password) async {
    final res = await _api.post('/auth/login', body: {'username': username, 'password': password});
    final token = res['token'] as String;
    _api.setToken(token);
    await _storage.write(key: _tokenKey, value: token);
    return AppUser.fromJson((res['user'] as Map).cast<String, dynamic>());
  }

  Future<bool> restoreSession() async {
    final token = await _storage.read(key: _tokenKey);
    if (token == null) return false;
    _api.setToken(token);
    return true;
  }

  Future<void> logout() async {
    _api.setToken(null);
    await _storage.delete(key: _tokenKey);
  }
}
