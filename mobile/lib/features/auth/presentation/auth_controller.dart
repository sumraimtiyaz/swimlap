import 'package:flutter/foundation.dart';

import '../../../core/network/api_exception.dart';
import '../data/auth_repository.dart';
import '../domain/app_user.dart';

class AuthController extends ChangeNotifier {
  AuthController(this._repo);

  final AuthRepository _repo;

  AppUser? user;
  bool loading = false;
  String? error;

  Future<bool> restore() async => _repo.restoreSession();

  Future<bool> login(String username, String password) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      user = await _repo.login(username.trim(), password);
      return true;
    } on ApiException catch (e) {
      error = switch (e.code) {
        'AUTH_INVALID_CREDENTIALS' => 'Incorrect login id or password.',
        'AUTH_ACCOUNT_DISABLED' => 'This account has been deactivated. Contact your coordinator.',
        'AUTH_LOCKED' => 'Too many attempts. Wait a few minutes and try again.',
        _ => e.message,
      };
      return false;
    } finally {
      loading = false;
      notifyListeners();
    }
  }
}
